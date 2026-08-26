'use strict';
/**
 * 采集 CDP Network 事件。Network 使用独立 target 连接，不影响 cdp_listener。
 */
const {
    getTargets, attachTargetNetwork, startNetworkDiscovery, stopDiscovery, closeConnections,
} = require('./cdp_core');

function parseArgs(argv) {
    const args = {
        port: null, duration: 10, cdpPort: 9222, appserviceOnly: true,
    };
    for (let i = 2; i < argv.length; i++) {
        switch (argv[i]) {
            case '--duration': args.duration = parseInt(argv[++i], 10) || 10; break;
            case '--cdp-port': args.cdpPort = parseInt(argv[++i], 10) || 9222; break;
            case '--appservice-only': args.appserviceOnly = argv[++i] !== 'false'; break;
        }
    }
    return args;
}

async function handle(_miniProgram, args) {
    const events = [];
    const activeConnections = new Map();
    const state = { networkEnabledTargets: 0, networkErrors: [] };
    let targets;
    try {
        targets = await getTargets(args.cdpPort);
    } catch (err) {
        return {
            success: false, code: 'CDP_UNAVAILABLE',
            error: err.message || String(err),
        };
    }

    for (const target of targets) {
        attachTargetNetwork(target, events, activeConnections, state, {
            appserviceOnly: args.appserviceOnly,
        });
    }
    const timer = startNetworkDiscovery(
        args.cdpPort, events, activeConnections, state,
        { appserviceOnly: args.appserviceOnly },
    );
    await new Promise(resolve => setTimeout(resolve, args.duration * 1000));
    stopDiscovery(timer);
    closeConnections(activeConnections);

    if (state.networkEnabledTargets === 0 && state.networkErrors.length > 0) {
        return {
            success: false, code: 'NETWORK_DOMAIN_UNSUPPORTED',
            error: state.networkErrors[0],
        };
    }
    return {
        events,
        network_enabled_targets: state.networkEnabledTargets,
    };
}

module.exports = { handle, parseArgs };
