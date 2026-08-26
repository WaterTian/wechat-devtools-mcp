#!/usr/bin/env node
/**
 * test_screenshot_scroll.js
 * 测试 waitForScrollComplete —— 长图被截断的根因就在这里。
 *
 * 旧实现只要连续两次读数相同就返回。若 pageScrollTo 尚未生效（渲染层滞后
 * 超过一次轮询间隔），两次读到的都还是滚动前的位置，函数返回旧值，
 * 调用方算出 actualDelta <= 0 判定「已到底部」直接 break —— 长图被截断在
 * 前两屏，而且不报任何错。
 *
 * 用法: node tests/test_screenshot_scroll.js
 */

'use strict';

const path = require('path');
const {
    waitForScrollComplete,
} = require(path.join(__dirname, '..', 'src', 'wechat_devtools_mcp', 'scripts', 'screenshot.js'));

/**
 * 构造假的 miniProgram：按预设序列依次返回 scrollTop。
 * 序列耗尽后一直返回最后一个值。
 */
function mockMiniProgram(readings) {
    let i = 0;
    return {
        calls: 0,
        async evaluate() {
            this.calls++;
            const v = readings[Math.min(i, readings.length - 1)];
            i++;
            return v;
        },
    };
}

let passed = 0;
let failed = 0;

function assert(condition, msg) {
    if (condition) {
        passed++;
        console.log(`  ✅ ${msg}`);
    } else {
        failed++;
        console.log(`  ❌ ${msg}`);
    }
}

(async () => {
    // ---------- Test 1: 慢启动（回归测试，旧实现在此必挂）----------
    console.log('\nTest 1: 滚动慢启动 —— 前两次读数仍是旧位置，之后才动');
    {
        // 从 0 滚向 600：前两拍还停在 0（旧实现会在此返回 0 → 判定到底 → 截断），
        // 第三拍开始移动并稳定在 600
        const mp = mockMiniProgram([0, 0, 600, 600]);
        const result = await waitForScrollComplete(mp, 600, 0);

        assert(result === 600,
            `返回 ${result}（期望 600，若为 0 即为旧实现的截断 bug）`);
    }

    // ---------- Test 2: 真到底部 ----------
    console.log('\nTest 2: 已在底部 —— 无论怎么滚都不动，应在 minSettle 后认可');
    {
        // 页面已到底，读数恒为 1200（= fromScrollTop），永远不会移动
        const mp = mockMiniProgram([1200]);
        const t0 = Date.now();
        const result = await waitForScrollComplete(mp, 1800, 1200);
        const elapsed = Date.now() - t0;

        assert(result === 1200, `返回 ${result}（期望 1200，调用方据此判定到底）`);
        assert(elapsed >= 500, `等待 ${elapsed}ms（应 ≥ minSettle 500ms 才认可静止）`);
        assert(elapsed < 1500, `等待 ${elapsed}ms（不应耗到 maxWait 上限）`);
    }

    // ---------- Test 3: 正常滚动 ----------
    console.log('\nTest 3: 正常滚动 —— 立刻移动并稳定');
    {
        const mp = mockMiniProgram([600, 600]);
        const t0 = Date.now();
        const result = await waitForScrollComplete(mp, 600, 0);
        const elapsed = Date.now() - t0;

        assert(result === 600, `返回 ${result}（期望 600）`);
        assert(elapsed < 500, `等待 ${elapsed}ms（已确认移动，不必等满 minSettle）`);
    }

    // ---------- Test 4: 滚动未到位（页面剩余高度不足）----------
    console.log('\nTest 4: 滚动量不足 —— 目标 600 但只能滚到 350');
    {
        const mp = mockMiniProgram([350, 350]);
        const result = await waitForScrollComplete(mp, 600, 0);

        assert(result === 350,
            `返回 ${result}（期望 350，实际滚动量由调用方据此算真实重叠）`);
    }

    // ---------- Test 5: evaluate 抛异常时降级 ----------
    console.log('\nTest 5: evaluate 抛异常 —— 应降级返回目标值而非卡死');
    {
        const mp = { async evaluate() { throw new Error('Cannot find context'); } };
        const result = await waitForScrollComplete(mp, 600, 0);

        assert(result === 600, `返回 ${result}（期望降级为目标值 600）`);
    }

    // ---------- Test 6: fromScrollTop 缺省时保持旧行为 ----------
    console.log('\nTest 6: 不传 fromScrollTop —— 兼容旧调用，两次相同即返回');
    {
        const mp = mockMiniProgram([900, 900]);
        const t0 = Date.now();
        const result = await waitForScrollComplete(mp, 900);
        const elapsed = Date.now() - t0;

        assert(result === 900, `返回 ${result}（期望 900）`);
        assert(elapsed < 500, `等待 ${elapsed}ms（缺省时不应触发 minSettle 等待）`);
    }

    console.log(`\n========================================`);
    console.log(`Total: ${passed + failed}  Passed: ${passed}  Failed: ${failed}`);
    process.exit(failed > 0 ? 1 : 0);
})();
