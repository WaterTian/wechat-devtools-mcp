#!/usr/bin/env node
/**
 * test_evaluate_modes.js
 * 测试 ui_debug.js 的 evaluate 分支：
 *   - fn_source 路径：完整函数源码 + args，函数体多语句、显式 return
 *   - expression 路径：单表达式 / 声明语句 / 多语句 / 字符串字面量内含分号
 *
 * 根因回归：旧实现拼 `return a(); b(); c()` 语法合法，只执行第一条且不报错。
 * 新实现先本地编译 `return (code)`，多语句必然 SyntaxError → 退回语句模式，三条都执行。
 *
 * 用法: node tests/test_evaluate_modes.js
 */

'use strict';

const path = require('path');
const { handle, parseArgs } = require(path.join(
    __dirname, '..', 'src', 'wechat_devtools_mcp', 'scripts', 'ui_debug.js'));

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

// 假 miniProgram：与 automator 一致，evaluate(fn, ...args) 在“逻辑层”执行 fn
const calls = [];
const fakeMiniProgram = {
    evaluate(fn, ...args) { return Promise.resolve(fn(...args)); },
};
// 供多语句用例调用的全局函数
global.a = () => calls.push('a');
global.b = () => calls.push('b');
global.c = () => { calls.push('c'); return 'c-done'; };

function argsFor(list) { return parseArgs(['node', 'daemon.js', '--port', '9420', '--action', 'evaluate', ...list]); }

(async () => {
    console.log('Test 1: parseArgs 识别 --fn-source / --args');
    {
        const args = argsFor(['--fn-source', '(x)=>x', '--args', '[1]']);
        assert(args.fnSource === '(x)=>x', `fnSource = ${args.fnSource}`);
        assert(args.args === '[1]', `args = ${args.args}`);
    }

    console.log('\nTest 2: 单表达式 → mode=expression');
    {
        const r = await handle(fakeMiniProgram, argsFor(['--code', '1 + 2']));
        assert(r.result === 3, `result = ${r.result}（期望 3）`);
        assert(r.mode === 'expression', `mode = ${r.mode}（期望 expression）`);
    }

    console.log('\nTest 3: 声明语句 + return → mode=statement');
    {
        const r = await handle(fakeMiniProgram, argsFor(['--code', 'const p = [1,2,3]; return p.length']));
        assert(r.result === 3, `result = ${r.result}（期望 3）`);
        assert(r.mode === 'statement', `mode = ${r.mode}（期望 statement）`);
    }

    console.log('\nTest 4: 多语句 a(); b(); c() → 三条都执行（根因回归）');
    {
        calls.length = 0;
        const r = await handle(fakeMiniProgram, argsFor(['--code', 'a(); b(); c()']));
        assert(calls.join(',') === 'a,b,c', `calls = ${calls.join(',')}（期望 a,b,c）`);
        assert(r.mode === 'statement', `mode = ${r.mode}（期望 statement）`);
        assert(r.result === undefined || r.result === null, `未 return 时 result = ${r.result}（期望空）`);
    }

    console.log('\nTest 5: 字符串字面量内含分号 → 仍是单表达式');
    {
        const r = await handle(fakeMiniProgram, argsFor(['--code', '"a;b".length']));
        assert(r.result === 3, `result = ${r.result}（期望 3）`);
        assert(r.mode === 'expression', `mode = ${r.mode}（期望 expression）`);
    }

    console.log('\nTest 6: fn_source + args');
    {
        const src = 'function(x, y){ const s = x + y; return s * 2; }';
        const r = await handle(fakeMiniProgram, argsFor(['--fn-source', src, '--args', '[3, 4]']));
        assert(r.result === 14, `result = ${r.result}（期望 14）`);
        assert(r.mode === 'function', `mode = ${r.mode}（期望 function）`);
    }
    {
        const r = await handle(fakeMiniProgram, argsFor(['--fn-source', '() => 7']));
        assert(r.result === 7, `无 args 的箭头函数 result = ${r.result}（期望 7）`);
    }

    console.log('\nTest 7: fn_source 非函数 / args 非 JSON 数组 → 明确报错');
    await expectThrow(() => handle(fakeMiniProgram, argsFor(['--fn-source', '1 + 1'])),
        /fn_source 必须是一个函数的源码/, '非函数源码报错');
    await expectThrow(() => handle(fakeMiniProgram, argsFor(['--fn-source', '()=>1', '--args', '{bad'])),
        /args/, 'args 解析失败报错');
    await expectThrow(() => handle(fakeMiniProgram, argsFor(['--fn-source', '()=>1', '--args', '{"k":1}'])),
        /数组/, 'args 非数组报错');

    console.log('\nTest 8: 运行期非 SyntaxError 原样抛出（不误退回语句模式）');
    await expectThrow(() => handle(fakeMiniProgram, argsFor(['--code', 'undefinedFn()'])),
        /undefinedFn is not defined/, 'ReferenceError 原样抛出');

    console.log(`\n========================================`);
    console.log(`Total: ${passed + failed}  Passed: ${passed}  Failed: ${failed}`);
    process.exit(failed > 0 ? 1 : 0);
})();
