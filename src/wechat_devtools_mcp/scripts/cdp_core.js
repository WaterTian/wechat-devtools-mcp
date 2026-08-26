'use strict';
/**
 * cdp_core.js
 * CDP 连接共享模块：供 cdp_listener.js 和 navigate_capture.js 复用。
 *
 * 导出：
 *   getTargets(cdpPort)            - HTTP 获取 /json/list
 *   attachTarget(target, logs)     - WebSocket 连接 + enable 协议
 *   startDiscovery(cdpPort, logs)  - 持续发现新 target（setInterval）
 *   stopDiscovery(timer)           - 停止发现（clearInterval）
 */

const WebSocket = require('./node_modules/ws');
const http = require('http');

/**
 * 通过 HTTP 获取 CDP targets 列表。
 * @param {number} cdpPort - CDP 调试端口
 * @returns {Promise<Array>}
 */
async function getTargets(cdpPort) {
    return new Promise((resolve, reject) => {
        const req = http.get(`http://127.0.0.1:${cdpPort}/json/list`, (res) => {
            let data = '';
            res.on('data', (chunk) => data += chunk);
            res.on('end', () => {
                try { resolve(JSON.parse(data)); }
                catch (_) { resolve([]); }
            });
        });
        req.on('error', reject);
        req.end();
    });
}

/**
 * 将日志记录推入 logs 数组。
 * @param {Array} logs - 日志数组（引用传入）
 * @param {string} type - 日志类型（CONSOLE/RUNTIME_CONSOLE/EXCEPTION）
 * @param {string} targetUrl - target URL
 * @param {string} targetType - target type
 * @param {*} data - 日志内容
 */
function addLog(logs, type, targetUrl, targetType, data) {
    logs.push({
        timestamp: new Date().toISOString(),
        type,
        url: targetUrl,
        targetType,
        content: data,
    });
}

/**
 * 序列化 CDP RemoteObject 为可读字符串。
 * 优先级：value → preview → description（非 [object Object]）→ JSON.stringify 兜底
 */
function serializeArg(a) {
    // 1. 原始类型
    if (a.value !== undefined) return a.value;

    // 2. 对象预览（零成本，CDP 事件自带）
    if (a.preview && a.preview.properties) {
        const pairs = a.preview.properties.map(p => `${p.name}: ${p.value}`);
        const overflow = a.preview.overflow ? ', ...' : '';
        return `{${pairs.join(', ')}${overflow}}`;
    }

    // 3. description（排除无用的 [object Object]）
    if (a.description && a.description !== '[object Object]') {
        return a.description;
    }

    // 4. 兜底：序列化整个 RemoteObject 结构
    try {
        const { objectId, ...rest } = a;  // 排除 objectId（无意义长字符串）
        const s = JSON.stringify(rest);
        if (s && s !== '{}') return s;
    } catch (_) {}

    return 'unserializable';
}

/**
 * 判断 target 是否属于 IDE 自身界面（应排除，不是小程序业务日志）。
 *
 * 实测 IDE 2.x(Electron 36 / 2.02.2607271) 的 target 构成：
 *   webview  http://127.0.0.1:<port>/__pageframe__/pages/...        ← 渲染层，要采
 *   webview  http://127.0.0.1:<port>/appservice/s0/.../mainframe    ← 逻辑层，要采
 *   webview  devtools://devtools/bundled/devtools_app.html          ← IDE 调试器前端
 *   iframe   chrome-extension://<id>/devtools/devtools.html         ← IDE 扩展页
 *   page     file:///.../app.asar/html/electron-{entrance,project}.html ← IDE 外壳
 *
 * 两处历史缺陷：
 *   1. 旧规则写作 `if (isIdeUI && target.type !== 'webview') return`，
 *      而 devtools:// 的 type 恰好就是 webview，于是从缝里漏了进来；
 *   2. file:// 外壳页是 2.x 新增的，旧规则完全没有覆盖，实测占采集量六成。
 *
 * @param {Object} target - CDP target 对象
 * @returns {boolean}
 */
function isIdeShellTarget(target) {
    const url = (target && target.url) || '';

    // IDE 自身 UI：调试器前端与扩展页，无论 type 一律排除
    if (url.startsWith('devtools://') || url.startsWith('chrome-extension://')) {
        return true;
    }

    // IDE 2.x(Electron) 外壳页：应用代码打在 app.asar 内，以 file:// 加载
    if (url.startsWith('file://') &&
        (url.indexOf('/app.asar/') !== -1 || url.indexOf('/Contents/Resources/') !== -1)) {
        return true;
    }

    // 1.x 遗留：url 字段偶尔就是窗口标题。保留原先的 webview 例外，避免误伤渲染层
    if (url === '微信开发者工具' && target.type !== 'webview') return true;

    return false;
}

/**
 * 连接到 CDP target，开启 Console/Runtime/Log 协议并监听日志。
 * @param {Object} target - CDP target 对象
 * @param {Array} logs - 日志数组（引用传入）
 * @param {Map} activeConnections - 已连接 target 的 Map
 */
function attachTarget(target, logs, activeConnections) {
    if (activeConnections.has(target.id)) return;

    if (isIdeShellTarget(target)) return;

    activeConnections.set(target.id, true);

    try {
        const ws = new WebSocket(target.webSocketDebuggerUrl);

        ws.on('open', () => {
            ws.send(JSON.stringify({ id: 1, method: 'Console.enable' }));
            ws.send(JSON.stringify({ id: 2, method: 'Runtime.enable' }));
            ws.send(JSON.stringify({ id: 3, method: 'Log.enable' }));
        });

        ws.on('message', (data) => {
            try {
                const msg = JSON.parse(data);
                const method = msg.method;
                const params = msg.params;
                if (!method) return;

                if (method === 'Console.messageAdded') {
                    addLog(logs, 'CONSOLE', target.url, target.type, params.message);
                } else if (method === 'Runtime.consoleAPICalled') {
                    const logType = params.type === 'assert' ? 'ASSERT' : 'RUNTIME_CONSOLE';
                    addLog(logs, logType, target.url, target.type, {
                        type: params.type,
                        args: params.args.map(serializeArg),
                    });
                } else if (method === 'Runtime.exceptionThrown') {
                    addLog(logs, 'EXCEPTION', target.url, target.type, params.exceptionDetails);
                } else if (method === 'Log.entryAdded') {
                    addLog(logs, 'LOG_ENTRY', target.url, target.type, params.entry);
                }
            } catch (_) { }
        });

        ws.on('close', () => activeConnections.delete(target.id));
        ws.on('error', () => activeConnections.delete(target.id));
    } catch (_) {
        activeConnections.delete(target.id);
    }
}

/**
 * 启动 target 持续发现，每隔 intervalMs 轮询一次。
 * @param {number} cdpPort
 * @param {Array} logs
 * @param {Map} activeConnections
 * @param {number} [intervalMs=1000]
 * @returns {NodeJS.Timeout} 定时器句柄，用于 stopDiscovery
 */
function startDiscovery(cdpPort, logs, activeConnections, intervalMs = 1000) {
    return setInterval(async () => {
        try {
            const targets = await getTargets(cdpPort);
            for (const target of targets) {
                attachTarget(target, logs, activeConnections);
            }
        } catch (_) { }
    }, intervalMs);
}

/**
 * 停止 target 持续发现。
 * @param {NodeJS.Timeout} timer
 */
function stopDiscovery(timer) {
    if (timer) clearInterval(timer);
}

/**
 * 返回当前 ISO 8601 时间戳（与 addLog 格式一致）。
 */
function getTimestamp() {
    return new Date().toISOString();
}

module.exports = {
    getTargets, attachTarget, startDiscovery, stopDiscovery, getTimestamp,
    isIdeShellTarget,
};
