#!/usr/bin/env node
/**
 * test_screenshot_detect.js
 * 测试 detectFixedRegions —— 长图拼接时固定头部/底部的识别。
 *
 * 判据是「找会动的」：img1 是 img0 向下滚 delta 后的截图，
 * 能按 delta 找到对应行的就是滚动内容，其余是固定区域。
 * 因此**不要求固定元素像素级稳定** —— 半透明导航栏、跳变的状态栏时钟
 * 都不会让它失效，而旧的「找没变的」判据在这些场景下会直接返回 0。
 *
 * 用法: node tests/test_screenshot_detect.js
 */

'use strict';

const path = require('path');
const {
    detectFixedRegions,
} = require(path.join(__dirname, '..', 'src', 'wechat_devtools_mcp', 'scripts', 'screenshot.js'));

// ===== 模拟图片对象 =====
function createMockImage(width, height, pixelFn) {
    const data = new Uint32Array(width * height);
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            data[y * width + x] = pixelFn(x, y);
        }
    }
    return {
        bitmap: { width, height },
        getPixelColor(x, y) { return data[y * width + x]; },
    };
}

function rgba(r, g, b, a) {
    return ((r & 0xFF) << 24) | ((g & 0xFF) << 16) | ((b & 0xFF) << 8) | (a & 0xFF);
}

/**
 * 构造一对「滚动前 / 滚动后」截图。
 *
 * @param opts.header    固定头部高度
 * @param opts.footer    固定底部高度
 * @param opts.delta     滚动距离
 * @param opts.headerFn  (x,y,phase) => color 头部像素；phase 0=滚动前 1=滚动后
 * @param opts.footerFn  同上
 * @param opts.contentFn (x, absoluteY) => color 内容像素（按页面绝对坐标，
 *                       因此滚动后自然发生位移）
 */
function makePair(W, H, opts) {
    const { header = 0, footer = 0, delta = 200 } = opts;
    const contentFn = opts.contentFn
        || ((x, ay) => rgba((ay * 3) % 256, (x * 7) % 256, (ay + x) % 256, 255));
    const headerFn = opts.headerFn || (() => rgba(30, 60, 45, 255));
    const footerFn = opts.footerFn || (() => rgba(80, 80, 80, 255));

    const build = (phase, scrollTop) => createMockImage(W, H, (x, y) => {
        if (y < header) return headerFn(x, y, phase);
        if (y >= H - footer) return footerFn(x, y - (H - footer), phase);
        // 内容区：屏幕行 y 对应页面绝对行 scrollTop + y
        return contentFn(x, scrollTop + y);
    });

    return { img0: build(0, 0), img1: build(1, delta), delta };
}

let passed = 0, failed = 0;
function assert(condition, msg) {
    if (condition) { passed++; console.log(`  ✅ ${msg}`); }
    else { failed++; console.log(`  ❌ ${msg}`); }
}
// 边界允许 ±RUN 的检测误差（RUN=3 的判定窗口所致）
function near(actual, expected, slack = 4) {
    return Math.abs(actual - expected) <= slack;
}

// ---------- Test 1: 基本情形 ----------
console.log('\nTest 1: 不透明固定头(120) + 固定底(90)');
{
    const { img0, img1, delta } = makePair(100, 600, { header: 120, footer: 90, delta: 200 });
    const r = detectFixedRegions(img0, img1, delta);
    assert(near(r.headerHeight, 120), `headerHeight = ${r.headerHeight}（期望 ≈120）`);
    assert(near(r.footerHeight, 90), `footerHeight = ${r.footerHeight}（期望 ≈90）`);
    assert(r.confident === true, `confident = ${r.confident}（期望 true）`);
}

// ---------- Test 2: 半透明导航栏（旧判据在此必挂）----------
console.log('\nTest 2: 半透明头部 —— 每一行都随下方内容变化');
{
    // 头部像素随 phase 改变（模拟透出下方滚动内容），旧判据从第 0 行就判负 → 返回 0
    const { img0, img1, delta } = makePair(100, 600, {
        header: 130, footer: 0, delta: 200,
        headerFn: (x, y, phase) => rgba(30 + phase * 25, 60 + phase * 25, 45 + phase * 25, 255),
    });
    const r = detectFixedRegions(img0, img1, delta);
    assert(near(r.headerHeight, 130), `headerHeight = ${r.headerHeight}（期望 ≈130，旧判据会得 0）`);
}

// ---------- Test 3: 状态栏时钟跳变 ----------
console.log('\nTest 3: 头部含跳变时钟（局部像素变化）');
{
    const { img0, img1, delta } = makePair(200, 600, {
        header: 140, footer: 0, delta: 200,
        headerFn: (x, y, phase) => {
            // 第 20~50 行、x 在 10~40 之间模拟时钟数字，滚动后内容不同
            if (y >= 20 && y < 50 && x >= 10 && x < 40) {
                return rgba(255, 255, 255 - phase * 120, 255);
            }
            return rgba(30, 60, 45, 255);
        },
    });
    const r = detectFixedRegions(img0, img1, delta);
    assert(near(r.headerHeight, 140), `headerHeight = ${r.headerHeight}（期望 ≈140，不应被时钟打断）`);
}

// ---------- Test 4: 无固定区域 ----------
console.log('\nTest 4: 整页滚动，无固定头尾');
{
    const { img0, img1, delta } = makePair(100, 600, { header: 0, footer: 0, delta: 200 });
    const r = detectFixedRegions(img0, img1, delta);
    assert(r.headerHeight === 0, `headerHeight = ${r.headerHeight}（期望 0）`);
    assert(r.footerHeight === 0, `footerHeight = ${r.footerHeight}（期望 0）`);
}

// ---------- Test 5: 纯色内容不应被误判为固定区 ----------
console.log('\nTest 5: 内容区是大片纯色 —— 旧判据会误判为固定区');
{
    const { img0, img1, delta } = makePair(100, 600, {
        header: 100, footer: 0, delta: 200,
        contentFn: () => rgba(250, 250, 250, 255),   // 纯白内容，滚动前后逐行相同
    });
    const r = detectFixedRegions(img0, img1, delta);
    // 纯色内容按 delta 位移后仍然匹配 → 正确归入内容区，头部边界仍在 100 附近
    assert(r.headerHeight <= 110, `headerHeight = ${r.headerHeight}（期望 ≤110，不应吞掉纯色内容）`);
}

// ---------- Test 6: delta 非法时明确表示测不准 ----------
console.log('\nTest 6: delta 缺失 / 超过视口高度');
{
    const { img0, img1 } = makePair(100, 600, { header: 120, footer: 90, delta: 200 });
    for (const [d, label] of [[0, '0'], [undefined, 'undefined'], [600, '=视口高']]) {
        const r = detectFixedRegions(img0, img1, d);
        assert(r.confident === false && r.headerHeight === 0,
            `delta=${label} → confident=${r.confident}, header=${r.headerHeight}（期望 false/0）`);
    }
}

// ---------- Test 7: 亚像素错位容忍 ----------
console.log('\nTest 7: 真实位移比 delta 少 1px（dpr 取整误差）');
{
    const W = 100, H = 600, header = 120, realShift = 199, reported = 200;
    const contentFn = (x, ay) => rgba((ay * 3) % 256, (x * 7) % 256, (ay + x) % 256, 255);
    const img0 = createMockImage(W, H, (x, y) =>
        y < header ? rgba(30, 60, 45, 255) : contentFn(x, y));
    const img1 = createMockImage(W, H, (x, y) =>
        y < header ? rgba(30, 60, 45, 255) : contentFn(x, y + realShift));
    const r = detectFixedRegions(img0, img1, reported);
    assert(near(r.headerHeight, header), `headerHeight = ${r.headerHeight}（期望 ≈${header}，±1px 错位应被吸收）`);
}

// ---------- Test 8: 内容既不稳定也不位移 → 不自信 ----------
console.log('\nTest 8: 内容随机变化（模拟懒加载）—— 应识别为测不准');
{
    const W = 100, H = 600;
    const img0 = createMockImage(W, H, (x, y) => rgba((y * 3) % 256, (x * 7) % 256, 0, 255));
    const img1 = createMockImage(W, H, (x, y) => rgba((y * 11 + 77) % 256, (x * 5 + 33) % 256, 99, 255));
    const r = detectFixedRegions(img0, img1, 200);
    assert(r.confident === false, `confident = ${r.confident}（期望 false，不该硬猜）`);
}

console.log(`\n========================================`);
console.log(`Total: ${passed + failed}  Passed: ${passed}  Failed: ${failed}`);
process.exit(failed > 0 ? 1 : 0);
