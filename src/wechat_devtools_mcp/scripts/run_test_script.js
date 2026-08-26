/**
 * run_test_script.js
 * 连接微信开发者工具自动化端口，执行用户提供的自动化测试脚本文件，
 * 同步收集执行期间的所有 console/exception 事件，以 JSON 格式返回。
 *
 * 导出 { handle, parseArgs } 供 daemon 调用。
 *
 * 测试脚本 API：
 *   脚本导出一个 async function，接收 miniProgram 对象，返回任意结果。
 *   示例脚本:
 *   module.exports = async function(miniProgram) {
 *     const page = await miniProgram.navigateTo('/pages/index/index');
 *     await page.waitFor(1000);
 *     const el = await page.$('.my-button');
 *     await el.tap();
 *     return { tapped: true };
 *   };
 */

'use strict';

const path = require('path');
const fs = require('fs');

function parseArgs(argv) {
    const args = { port: 9420, script: '', timeout: 30 };
    for (let i = 2; i < argv.length; i++) {
        switch (argv[i]) {
            case '--port':
                args.port = parseInt(argv[++i], 10);
                break;
            case '--script':
                args.script = argv[++i];
                break;
            case '--timeout':
                args.timeout = Math.min(Math.max(parseInt(argv[++i], 10), 5), 300);
                break;
        }
    }
    return args;
}

function formatTime(ts) {
    const d = new Date(ts);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}.${String(d.getMilliseconds()).padStart(3, '0')}`;
}

async function handle(miniProgram, args) {
    const { timeout } = args;
    let { script } = args;

    // 验证脚本文件
    if (!script) {
        return { success: false, error: '必须指定 --script 参数' };
    }

    script = path.resolve(script);
    if (!fs.existsSync(script)) {
        return { success: false, error: `脚本文件不存在: ${script}` };
    }

    // 加载测试脚本
    let testFn;
    try {
        testFn = require(script);
        if (typeof testFn !== 'function') {
            return { success: false, error: '脚本必须导出一个函数: module.exports = async function(miniProgram) { ... }' };
        }
    } catch (loadErr) {
        return { success: false, error: `加载脚本失败: ${loadErr.message}` };
    }

    const consoleLogs = [];
    const exceptions = [];
    let scriptResult = null;
    let scriptError = null;

    // 注册事件监听
    miniProgram.on('console', (msg) => {
        const ts = Date.now();
        consoleLogs.push({
            time: formatTime(ts),
            timestamp: ts,
            type: msg.type || 'log',
            args: msg.args || [],
        });
    });

    miniProgram.on('exception', (err) => {
        const ts = Date.now();
        exceptions.push({
            time: formatTime(ts),
            timestamp: ts,
            message: err.message || String(err),
            stack: err.stack || '',
        });
    });

    // 执行测试脚本（带超时）
    const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error(`脚本执行超时（${timeout}秒）`)), timeout * 1000)
    );

    try {
        scriptResult = await Promise.race([testFn(miniProgram), timeoutPromise]);
    } catch (err) {
        scriptError = { message: err.message || String(err), stack: err.stack || '' };
    }

    return {
        success: scriptError === null,
        port: args.port,
        script,
        timeout,
        console_logs: consoleLogs,
        exceptions: exceptions,
        script_result: scriptResult,
        script_error: scriptError,
        summary: {
            total_logs: consoleLogs.length,
            errors: consoleLogs.filter(l => l.type === 'error').length,
            warnings: consoleLogs.filter(l => l.type === 'warn').length,
            exceptions: exceptions.length,
        },
    };
}

module.exports = { handle, parseArgs };
