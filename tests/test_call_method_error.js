#!/usr/bin/env node
/**
 * test_call_method_error.js
 * 回归：callMethod 调用不存在的页面方法时，抛出的错误必须带上当前页面路径。
 *
 * 背景（2026-09-03 真机）：automation.js 旧实现先 `page.callMethod()` 再 `result.path = page.path`，
 * 方法不存在时在第一步就抛错，path 永远取不到；daemon 的 respondError 只回错误串，
 * 于是「失败时带页面路径」这条文档承诺落空。改为先取 path，再 try/catch 把 path 嵌进 message。
 *
 * 用法: node tests/test_call_method_error.js
 */
'use strict';
const path = require('path');
const { handle } = require(path.join(
    __dirname, '..', 'src', 'wechat_devtools_mcp', 'scripts', 'automation.js'));

let passed = 0, failed = 0;
function assert(cond, msg) {
    if (cond) { passed++; console.log(`  ✓ ${msg}`); }
    else { failed++; console.log(`  ✗ ${msg}`); }
}
async function expectThrow(fn, re, msg) {
    try { await fn(); failed++; console.log(`  ✗ ${msg}（未抛错）`); }
    catch (e) {
        if (re.test(e.message)) { passed++; console.log(`  ✓ ${msg}`); }
        else { failed++; console.log(`  ✗ ${msg}（错误信息不符: ${e.message}）`); }
    }
}

function fakePage(pagePath, methodImpl) {
    return { path: pagePath, callMethod: methodImpl };
}
function fakeMini(page) {
    return { currentPage: async () => page };
}

(async () => {
    console.log('callMethod 错误路径:');

    // 1. 方法不存在：错误信息必须含当前页面路径
    await expectThrow(
        () => handle(fakeMini(fakePage('pages/quiz/index', async () => {
            throw new Error('page.__noSuch not exists');
        })), { action: 'callMethod', method: '__noSuch', args: '' }),
        /当前页面: pages\/quiz\/index/,
        '方法不存在时错误带页面路径',
    );

    // 2. 方法内部抛业务错误：同样带路径，且保留原始信息
    await expectThrow(
        () => handle(fakeMini(fakePage('pages/home/index', async () => {
            throw new Error('boom inside handler');
        })), { action: 'callMethod', method: 'onSubmit', args: '' }),
        /boom inside handler.*当前页面: pages\/home\/index/,
        '业务错误保留原信息并带路径',
    );

    // 3. 正常调用：返回 path / method / returnValue
    // 真实契约：page.callMethod(methodName, ...args)，第一个参数是方法名
    const ok = await handle(fakeMini(fakePage('pages/home/index', async (name, a, b) => a + b)),
        { action: 'callMethod', method: 'sum', args: '[2,3]' });
    assert(ok.path === 'pages/home/index', '成功返回 path');
    assert(ok.method === 'sum', '成功返回 method');
    assert(ok.returnValue === 5, '成功返回 returnValue（入参已展开）');

    console.log(`\nTotal: ${passed + failed}  Passed: ${passed}  Failed: ${failed}`);
    process.exit(failed ? 1 : 0);
})();
