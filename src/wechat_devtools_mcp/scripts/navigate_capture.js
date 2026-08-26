'use strict';
/**
 * navigate_capture.js
 * 连接微信开发者工具自动化端口，跳转到指定页面，
 * 同时通过 CDP 采集高清日志，等待指定毫秒后返回 JSON。
 *
 * 导出 { handle, parseArgs } 供 daemon 调用。
 * 注意：CDP 连接是短暂的，不通过 daemon 缓存，由脚本内部管理。
 */

const { getTargets, attachTarget, startDiscovery, stopDiscovery, getTimestamp } = require('./cdp_core');

function parseArgs(argv) {
    const args = { port: 9420, page: '', wait: 2000, cdpPort: 9222, clearLogs: true, useSwitchTab: false };
    for (let i = 2; i < argv.length; i++) {
        switch (argv[i]) {
            case '--port':           args.port      = parseInt(argv[++i], 10); break;
            case '--page':           args.page      = argv[++i]; break;
            case '--wait':           args.wait      = Math.min(Math.max(parseInt(argv[++i], 10), 100), 30000); break;
            case '--cdp-port':       args.cdpPort   = parseInt(argv[++i], 10); break;
            case '--clear-logs':     args.clearLogs = argv[++i] !== 'false'; break;
            case '--use-switch-tab': args.useSwitchTab = true; break;
        }
    }
    return args;
}

async function handle(miniProgram, args) {
    const { page, wait, cdpPort, clearLogs, useSwitchTab } = args;

    if (!page) {
        return { success: false, error: '必须指定 --page 参数' };
    }

    const cdpLogs = [];
    const activeConnections = new Map();
    let currentPageInfo = null;
    let pageData = null;
    let cdpAvailable = false;
    let currentPageTimeout = false;
    let navigationMismatch = false;

    // ── 1. 启动 CDP 日志采集（在跳转前开始监听）────────────────
    try {
        const targets = await getTargets(cdpPort);
        if (targets.length > 0) {
            cdpAvailable = true;
            for (const target of targets) {
                attachTarget(target, cdpLogs, activeConnections);
            }
        }
    } catch (_) {
        // CDP 不可用，后续仍可完成跳转
    }

    // 持续发现新 target（页面跳转后可能产生新 target）
    let discoveryTimer = null;
    if (cdpAvailable) {
        discoveryTimer = startDiscovery(cdpPort, cdpLogs, activeConnections, 500);
        // 给 CDP 连接一点时间建立
        await new Promise(r => setTimeout(r, 300));
    }

    // 记录采集起点时间戳（在跳转前，CDP 连接建立后）
    const t0 = clearLogs ? getTimestamp() : null;

    // ── 2. 通过 automator 跳转页面 ──────────────────────────────
    try {
        const pagePath = page.startsWith('/') ? page : `/${page}`;

        const NAV_TIMEOUT = 8000;
        if (useSwitchTab) {
            // TabBar 页面必须用 switchTab，reLaunch/navigateTo 会失败
            try {
                await Promise.race([
                    miniProgram.switchTab(pagePath.split('?')[0]),
                    new Promise((_, reject) =>
                        setTimeout(() => reject(new Error('switchTab_timeout')), NAV_TIMEOUT)
                    ),
                ]);
            } catch (_) {
                // switchTab 超时 — 继续等待，页面可能已在切换中
            }
        } else {
            // reLaunch 带 query 参数时可能卡死，用 Promise.race 加独立超时
            try {
                await Promise.race([
                    miniProgram.reLaunch(pagePath),
                    new Promise((_, reject) =>
                        setTimeout(() => reject(new Error('reLaunch_timeout')), NAV_TIMEOUT)
                    ),
                ]);
            } catch (navErr) {
                // reLaunch 超时时 fallback 到 navigateTo
                if (navErr.message === 'reLaunch_timeout' && pagePath.includes('?')) {
                    try {
                        await Promise.race([
                            miniProgram.navigateTo(pagePath),
                            new Promise((_, reject) =>
                                setTimeout(() => reject(new Error('navigateTo_timeout')), NAV_TIMEOUT)
                            ),
                        ]);
                    } catch (_) {
                        // navigateTo 也超时 — 继续等待，可能页面已在加载中
                    }
                }
                // 非超时错误或无 query 的超时 — 继续等待，不中断流程
            }
        }

        // 等待页面稳定 + CDP 采集日志
        await new Promise(r => setTimeout(r, wait));

        // 轮询获取 currentPage（页面栈可能未就绪）
        currentPageTimeout = false;
        const POLL_INTERVAL = 500;
        const MAX_POLLS = 8;
        const POLL_CALL_TIMEOUT = 2000;
        for (let i = 0; i < MAX_POLLS; i++) {
            try {
                const currentPage = await Promise.race([
                    miniProgram.currentPage(),
                    new Promise((_, reject) =>
                        setTimeout(() => reject(new Error('poll_timeout')), POLL_CALL_TIMEOUT)
                    ),
                ]);
                if (currentPage) {
                    currentPageInfo = {
                        path: currentPage.path,
                        query: currentPage.query || {},
                    };
                    try {
                        pageData = await currentPage.data();
                    } catch (_) {}
                    break;
                }
            } catch (_) { }
            if (i < MAX_POLLS - 1) {
                await new Promise(r => setTimeout(r, POLL_INTERVAL));
            } else {
                currentPageTimeout = true;
            }
        }

        // ── 页面路径验证：确认跳转是否真正生效 ──
        if (currentPageInfo && currentPageInfo.path) {
            const requestedPath = page.replace(/^\//, '').split('?')[0];
            const actualPath = currentPageInfo.path.replace(/^\//, '').split('?')[0];
            if (requestedPath !== actualPath) {
                navigationMismatch = true;
            }
        }

    } catch (err) {
        stopDiscovery(discoveryTimer);

        return {
            success: false,
            error: err.message || String(err),
            port: args.port, page, wait_ms: wait, cdp_port: cdpPort,
            cdp_available: cdpAvailable,
            current_page: currentPageInfo,
            current_page_timeout: currentPageTimeout || false,
            page_data: pageData,
            cdp_logs: cdpLogs,
            logs_since: t0,
            filtered_before_navigation: 0,
        };
    }

    // ── 3. 停止采集，输出结果 ────────────────────────────────────
    stopDiscovery(discoveryTimer);

    // 过滤 T0 之前的旧日志
    let filteredLogs = cdpLogs;
    let filteredCount = 0;
    if (t0) {
        filteredLogs = cdpLogs.filter(log => log.timestamp >= t0);
        filteredCount = cdpLogs.length - filteredLogs.length;
    }

    const result = {
        success: !navigationMismatch,
        port: args.port, page, wait_ms: wait, cdp_port: cdpPort,
        cdp_available: cdpAvailable,
        current_page: currentPageInfo,
        current_page_timeout: currentPageTimeout,
        navigation_mismatch: navigationMismatch,
        page_data: pageData,
        cdp_logs: filteredLogs,
        logs_since: t0,
        filtered_before_navigation: filteredCount,
    };
    if (navigationMismatch) {
        result.error = `页面跳转未生效：期望 ${page}，实际停留在 ${currentPageInfo.path}`;
    }
    return result;
}

module.exports = { handle, parseArgs };
