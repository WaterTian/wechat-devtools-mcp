#!/usr/bin/env node
/**
 * test_call_wx_sync.js
 * callWx 对同步返回的 wx API（getSystemSetting / getWindowInfo / *Sync / create* / *Manager）
 * 必须改经 miniProgram.evaluate 直调；异步 API 仍走 callWxMethod。
 *
 * 根因（真机 2026-10-26，FanTown 空闲复测）：miniprogram-automator 的 callWxMethod 会等 success
 * 回调，而同步 API 永远不回调 → 固定 10s "timeout waiting for automator response"；
 * 同一 API 用 evaluate 直调 0.0s 返回。
 *
 * 用法: node tests/test_call_wx_sync.js
 */
'use strict';
const path = require('path');
const { handle, parseArgs, isSyncWxApi } = require(path.join(
    __dirname, '..', 'src', 'wechat_devtools_mcp', 'scripts', 'automation.js'));

let passed = 0, failed = 0;
function assert(cond, msg) {
    if (cond) { passed++; console.log(`  ✓ ${msg}`); }
    else { failed++; console.log(`  ✗ ${msg}`); }
}

// 假逻辑层：evaluate(fn, ...args) 在带 wx 全局的环境里执行；callWxMethod 记录调用并返回异步结果
global.wx = {
    getSystemSetting: () => ({ bluetoothEnabled: true }),
    getWindowInfo: () => ({ pixelRatio: 3 }),
    getStorageSync: (k) => `v:${k}`,
    canIUse: (s) => s === 'button.open-type.share',
    getUpdateManager: () => ({ onCheckForUpdate() {} }),
    createSelectorQuery: () => ({ select() {} }),
};
const calls = { callWxMethod: [], evaluate: 0 };
const fakeMP = {
    evaluate(fn, ...args) { calls.evaluate++; return Promise.resolve(fn(...args)); },
    callWxMethod(method, ...args) { calls.callWxMethod.push([method, args]); return Promise.resolve({ errMsg: `${method}:ok` }); },
};
function argsFor(method, jsonArgs) {
    const argv = ['node', 'x', '--port', '9420', '--action', 'callWx', '--method', method];
    if (jsonArgs) argv.push('--args', jsonArgs);
    return parseArgs(argv);
}

(async () => {
    console.log('isSyncWxApi 判定：');
    assert(isSyncWxApi('getSystemSetting'), '白名单：getSystemSetting');
    assert(isSyncWxApi('getStorageSync'), 'Sync 后缀：getStorageSync');
    assert(isSyncWxApi('createSelectorQuery'), 'create* 前缀');
    assert(isSyncWxApi('getUpdateManager'), '*Manager 后缀');
    assert(!isSyncWxApi('getNetworkType'), '异步 API 不在内：getNetworkType');
    assert(!isSyncWxApi('getSystemInfo'), '异步 API 不在内：getSystemInfo（有回调版）');
    assert(!isSyncWxApi('request'), '异步 API 不在内：request');

    console.log('callWx 路由：');
    let r = await handle(fakeMP, argsFor('getSystemSetting'));
    assert(r.sync === true && r.returnValue.bluetoothEnabled === true, '同步 API 走 evaluate 并带 sync:true');
    assert(calls.callWxMethod.length === 0, '同步 API 不碰 callWxMethod');

    r = await handle(fakeMP, argsFor('getStorageSync', '["token"]'));
    assert(r.returnValue === 'v:token', '*Sync 带参数经 evaluate 透传');

    r = await handle(fakeMP, argsFor('canIUse', '["button.open-type.share"]'));
    assert(r.returnValue === true, 'canIUse 参数透传');

    r = await handle(fakeMP, argsFor('getUpdateManager'));
    assert(r.sync === true && typeof r.returnValue === 'object', 'Manager 对象可序列化为普通对象，不抛错');

    const before = calls.evaluate;
    r = await handle(fakeMP, argsFor('getNetworkType'));
    assert(r.sync === undefined && r.returnValue.errMsg === 'getNetworkType:ok', '异步 API 仍走 callWxMethod');
    assert(calls.callWxMethod.length === 1 && calls.evaluate === before, '异步 API 不走 evaluate');

    let threw = false;
    try { await handle(fakeMP, argsFor('getNotExistSync')); } catch (e) { threw = /not a function/.test(e.message); }
    assert(threw, '不存在的同步 API 报 not a function，而不是静默');

    console.log(`\nTotal: ${passed + failed}  Passed: ${passed}  Failed: ${failed}`);
    process.exit(failed ? 1 : 0);
})();
