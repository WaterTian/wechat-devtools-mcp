'use strict';
/**
 * daemon.js
 * 常驻 Node 进程：通过 stdin/stdout NDJSON 协议与 Python MCP Server 通信。
 * 管理 automator WebSocket 连接池，路由请求到各 handler。
 */

const readline = require('readline');
const automator = require('miniprogram-automator');

// ── Handler 注册 ─────────────────────────────────────────────────
const handlers = {
    automation:       require('./automation'),
    console_listener: require('./console_listener'),
    cdp_listener:     require('./cdp_listener'),
    network_listener: require('./network_listener'),
    navigate_capture: require('./navigate_capture'),
    screenshot:       require('./screenshot'),
    ui_debug:         require('./ui_debug'),
    run_test_script:  require('./run_test_script'),
};

// ── 连接管理 ─────────────────────────────────────────────────────
const connections = new Map(); // port → { miniProgram, connectedAt }

// 健康检查：轮询 currentPage()，每次 3s 超时。
// 缓存连接只重试 2 次（快速判死）；新连接重试 5 次（给页面加载留时间）。
async function healthCheck(miniProgram, maxRetries) {
    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            await Promise.race([
                miniProgram.currentPage(),
                new Promise((_, reject) =>
                    setTimeout(() => reject(new Error('timeout')), 3000)
                ),
            ]);
            return;
        } catch (_) {
            if (attempt < maxRetries - 1) {
                await new Promise(r => setTimeout(r, 1500));
            }
        }
    }
    throw new Error('health_check_exhausted');
}

async function getConnection(port) {
    const cached = connections.get(port);
    if (cached) {
        try {
            await healthCheck(cached.miniProgram, 2);
            return cached.miniProgram;
        } catch (_) {
            try { cached.miniProgram.disconnect(); } catch (_) { }
            connections.delete(port);
        }
    }

    const miniProgram = await automator.connect({
        wsEndpoint: `ws://localhost:${port}`,
    });
    try {
        await healthCheck(miniProgram, 5);
    } catch (_) {
        try { miniProgram.disconnect(); } catch (_) { }
        throw new Error('Connection not ready: health check failed after connect');
    }
    connections.set(port, { miniProgram, connectedAt: Date.now() });
    return miniProgram;
}

function respond(id, data) {
    const msg = { id };
    if (data && typeof data === 'object' && !Array.isArray(data)) {
        msg.success = data.success !== undefined ? data.success : true;
        msg.data = data;
    } else {
        msg.success = true;
        msg.data = data;
    }
    process.stdout.write(JSON.stringify(msg) + '\n');
}

function respondError(id, error, code) {
    process.stdout.write(JSON.stringify({
        id,
        success: false,
        error: String(error),
        code: code || 'HANDLER_ERROR',
    }) + '\n');
}

async function onMessage(msg) {
    const { id, script, args: rawArgs } = msg;

    if (!id) return;

    // ── 内置命令：invalidate（清除指定端口的缓存连接）──
    if (script === 'invalidate') {
        const port = rawArgs && rawArgs.length > 0 ? parseInt(rawArgs[0], 10) : null;
        if (port && connections.has(port)) {
            const conn = connections.get(port);
            try { conn.miniProgram.disconnect(); } catch (_) { }
            connections.delete(port);
            respond(id, { invalidated: true, port });
        } else {
            respond(id, { invalidated: false, port, reason: 'no_cached_connection' });
        }
        return;
    }

    const handler = handlers[script];
    if (!handler) {
        respondError(id, `未知 script: ${script}`, 'UNKNOWN_SCRIPT');
        return;
    }

    const fakeArgv = ['node', 'daemon.js', ...(rawArgs || [])];
    const args = handler.parseArgs(fakeArgv);

    try {
        const needsConnection = args.port !== null && args.port !== undefined;
        let miniProgram = null;

        if (needsConnection) {
            try {
                miniProgram = await getConnection(args.port);
            } catch (connErr) {
                // 首次连接失败，等 1s 后重试（compile 后 automator 可能还在初始化）
                await new Promise(r => setTimeout(r, 1000));
                try {
                    miniProgram = await getConnection(args.port);
                } catch (retryErr) {
                    const errMsg = retryErr.message || String(retryErr);
                    const isTimeout = errMsg.includes('health_check_timeout');
                    respondError(id, `连接失败: ${errMsg}`,
                        isTimeout ? 'HEALTH_CHECK_TIMEOUT' : 'CONNECTION_ERROR');
                    return;
                }
            }
        }

        const result = await handler.handle(miniProgram, args);
        respond(id, result);

    } catch (err) {
        const errorMsg = err.message || String(err);

        if (isConnectionError(errorMsg) && args.port) {
            connections.delete(args.port);
        }

        respondError(id, errorMsg, isConnectionError(errorMsg) ? 'CONNECTION_ERROR' : 'HANDLER_ERROR');
    }
}

function isConnectionError(msg) {
    const lower = msg.toLowerCase();
    return lower.includes('connection closed') ||
           lower.includes('connection refused') ||
           lower.includes('econnrefused') ||
           lower.includes('econnreset') ||
           lower.includes('health_check_timeout');
}

// ── 生命周期 ─────────────────────────────────────────────────────

const watchdog = setInterval(() => {
    try { process.kill(process.ppid, 0); }
    catch (_) { cleanup().then(() => process.exit(0)); }
}, 5000);

process.stdin.on('end', async () => {
    clearInterval(watchdog);
    await cleanup();
    process.exit(0);
});

process.on('uncaughtException', (err) => {
    process.stderr.write(`[daemon] uncaughtException: ${err.message}\n`);
});

process.on('unhandledRejection', (reason) => {
    process.stderr.write(`[daemon] unhandledRejection: ${reason}\n`);
});

async function cleanup() {
    for (const [port, conn] of connections) {
        try { conn.miniProgram.disconnect(); } catch (_) { }
    }
    connections.clear();
}

// ── 启动 ─────────────────────────────────────────────────────────

const rl = readline.createInterface({ input: process.stdin });

rl.on('line', (line) => {
    const trimmed = line.trim();
    if (!trimmed) return;

    let msg;
    try {
        msg = JSON.parse(trimmed);
    } catch (_) {
        process.stderr.write(`[daemon] invalid JSON: ${trimmed}\n`);
        return;
    }

    onMessage(msg).catch((err) => {
        if (msg && msg.id) {
            respondError(msg.id, `内部错误: ${err.message}`, 'INTERNAL_ERROR');
        }
    });
});

// 就绪信号
process.stdout.write(JSON.stringify({ ready: true }) + '\n');
