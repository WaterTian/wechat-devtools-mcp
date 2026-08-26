'use strict';
/**
 * cdp_listener.js
 * 采集 CDP 日志：启动 → 等待 duration 秒 → 返回日志数组。
 *
 * 导出 { handle, parseArgs } 供 daemon 调用。
 * 注意：此脚本不使用 automator，handle 接收的 miniProgram 参数为 null。
 * parseArgs 返回 port: null 以通知 daemon 不创建 automator 连接。
 */

const { getTargets, attachTarget, startDiscovery, stopDiscovery } = require('./cdp_core');

function parseArgs(argv) {
    const args = { port: null, duration: 15, cdpPort: 9222 };
    let hasFlags = false;
    for (let i = 2; i < argv.length; i++) {
        switch (argv[i]) {
            case '--duration':
                args.duration = parseInt(argv[++i], 10) || 15;
                hasFlags = true;
                break;
            case '--cdp-port':
                args.cdpPort = parseInt(argv[++i], 10) || 9222;
                hasFlags = true;
                break;
        }
    }
    // 兼容旧的位置参数模式: <duration> [cdp_port]
    if (!hasFlags) {
        if (argv[2]) args.duration = parseInt(argv[2], 10) || 15;
        if (argv[3]) args.cdpPort = parseInt(argv[3], 10) || 9222;
    }
    return args;
}

async function handle(_miniProgram, args) {
    const { duration, cdpPort } = args;
    const logs = [];
    const activeConnections = new Map();

    process.stderr.write(`CDP capture for ${duration}s on port ${cdpPort}...\n`);

    // 初始扫描
    try {
        const targets = await getTargets(cdpPort);
        for (const t of targets) attachTarget(t, logs, activeConnections);
    } catch (_) { }

    // 持续发现新 target
    const timer = startDiscovery(cdpPort, logs, activeConnections);

    // duration 到期后停止采集并返回
    await new Promise((resolve) => {
        setTimeout(() => {
            stopDiscovery(timer);
            resolve();
        }, duration * 1000);
    });

    return logs;
}

module.exports = { handle, parseArgs };
