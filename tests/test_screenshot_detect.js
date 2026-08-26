#!/usr/bin/env node
/**
 * test_screenshot_detect.js
 * 测试 detectFixedRegions 的像素比对逻辑（模糊匹配 + 安全区跳过 + 间隙容忍）
 *
 * 用法: node tests/test_screenshot_detect.js
 */

'use strict';

// 直接从源码中提取核心函数进行测试
function pixelsClose(c1, c2, tolerance) {
    if (c1 === c2) return true;
    const r1 = (c1 >>> 24) & 0xFF, r2 = (c2 >>> 24) & 0xFF;
    const g1 = (c1 >>> 16) & 0xFF, g2 = (c2 >>> 16) & 0xFF;
    const b1 = (c1 >>> 8)  & 0xFF, b2 = (c2 >>> 8)  & 0xFF;
    return Math.abs(r1 - r2) <= tolerance
        && Math.abs(g1 - g2) <= tolerance
        && Math.abs(b1 - b2) <= tolerance;
}

function rowMatches(img0, img1, y, width, tolerance, matchRatio) {
    let matched = 0;
    for (let x = 0; x < width; x++) {
        if (pixelsClose(img0.getPixelColor(x, y), img1.getPixelColor(x, y), tolerance)) {
            matched++;
        }
    }
    return (matched / width) >= matchRatio;
}

function detectFixedRegions(img0, img1) {
    const width = img0.bitmap.width;
    const height = img0.bitmap.height;
    const maxScan = Math.floor(height / 3);
    const TOLERANCE = 3;
    const MATCH_RATIO = 0.98;
    const MAX_GAP = 2;
    const SAFE_AREA_SKIP = 6;

    let headerHeight = 0;
    let headerGap = 0;
    for (let y = 0; y < maxScan; y++) {
        if (rowMatches(img0, img1, y, width, TOLERANCE, MATCH_RATIO)) {
            headerHeight = y + 1;
            headerGap = 0;
        } else {
            headerGap++;
            if (headerGap > MAX_GAP) break;
        }
    }

    let footerHeight = 0;
    let footerGap = 0;
    const bottomStart = height - 1 - SAFE_AREA_SKIP;
    for (let y = bottomStart; y >= height - maxScan; y--) {
        if (rowMatches(img0, img1, y, width, TOLERANCE, MATCH_RATIO)) {
            footerHeight = height - y;
            footerGap = 0;
        } else {
            footerGap++;
            if (footerGap > MAX_GAP) break;
        }
    }

    if (footerHeight > 0) {
        footerHeight += SAFE_AREA_SKIP;
    }

    return { headerHeight, footerHeight };
}

// ===== 模拟图片对象 =====
function createMockImage(width, height, pixelFn) {
    // pixelFn(x, y) => 32-bit RGBA color
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

// RGBA helper: pack into 32-bit
function rgba(r, g, b, a) {
    return ((r & 0xFF) << 24) | ((g & 0xFF) << 16) | ((b & 0xFF) << 8) | (a & 0xFF);
}

// ===== 测试用例 =====
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

// ---------- Test 1: 精确匹配 - 有 header 和 footer ----------
console.log('\nTest 1: 精确匹配检测 header(40px) + footer(50px)');
{
    const W = 100, H = 300;
    const HEADER = 40, FOOTER = 50;

    const img0 = createMockImage(W, H, (x, y) => {
        if (y < HEADER) return rgba(200, 200, 200, 255);       // 固定 header
        if (y >= H - FOOTER) return rgba(100, 100, 100, 255);  // 固定 footer
        return rgba(y * 2 % 256, x % 256, 0, 255);             // 可滚动内容
    });

    const img1 = createMockImage(W, H, (x, y) => {
        if (y < HEADER) return rgba(200, 200, 200, 255);       // 固定 header（相同）
        if (y >= H - FOOTER) return rgba(100, 100, 100, 255);  // 固定 footer（相同）
        return rgba((y * 2 + 50) % 256, (x + 30) % 256, 0, 255); // 不同的滚动内容
    });

    const result = detectFixedRegions(img0, img1);
    assert(result.headerHeight === HEADER, `headerHeight = ${result.headerHeight} (expected ${HEADER})`);
    // footer 会加上 SAFE_AREA_SKIP(6)，所以检测到的 footerHeight = FOOTER + 6
    // 但实际上由于安全区跳过，我们从 H-1-6 开始扫描，匹配到 H-FOOTER 行
    // footerHeight = H - (H-FOOTER) = FOOTER，然后 +6 = 56
    assert(result.footerHeight === FOOTER + 6, `footerHeight = ${result.footerHeight} (expected ${FOOTER + 6})`);
}

// ---------- Test 2: 无固定区域 ----------
console.log('\nTest 2: 完全不同的图片 - 无固定区域');
{
    const W = 50, H = 200;
    const img0 = createMockImage(W, H, (x, y) => rgba((y * 7 + 50) % 256, 0, 0, 255));
    const img1 = createMockImage(W, H, (x, y) => rgba(0, (y * 13 + 100) % 256, 0, 255));

    const result = detectFixedRegions(img0, img1);
    assert(result.headerHeight === 0, `headerHeight = ${result.headerHeight} (expected 0)`);
    assert(result.footerHeight === 0, `footerHeight = ${result.footerHeight} (expected 0)`);
}

// ---------- Test 3: 模糊匹配 - 亚像素渲染差异 ----------
console.log('\nTest 3: 底部导航栏有 ±2 的亚像素差异（应仍能检测）');
{
    const W = 100, H = 300;
    const FOOTER = 60;

    const img0 = createMockImage(W, H, (x, y) => {
        if (y >= H - FOOTER) return rgba(50, 50, 50, 255);
        return rgba(y % 256, x % 256, 100, 255);
    });

    const img1 = createMockImage(W, H, (x, y) => {
        if (y >= H - FOOTER) {
            // 引入 ±2 的渲染差异
            const jitter = (x % 5 === 0) ? 2 : 0;
            return rgba(50 + jitter, 50 - jitter, 50 + jitter, 255);
        }
        return rgba((y + 40) % 256, (x + 20) % 256, 150, 255);
    });

    const result = detectFixedRegions(img0, img1);
    assert(result.headerHeight === 0, `headerHeight = ${result.headerHeight} (expected 0)`);
    assert(result.footerHeight > 0, `footerHeight = ${result.footerHeight} (expected > 0, got ${result.footerHeight})`);
}

// ---------- Test 4: 旧版精确匹配会失败的情况 - 单像素差异 ----------
console.log('\nTest 4: footer 中有 1% 像素差异（旧版精确匹配会失败，新版应成功）');
{
    const W = 200, H = 400;
    const FOOTER = 65;

    const img0 = createMockImage(W, H, (x, y) => {
        if (y >= H - FOOTER) return rgba(80, 80, 80, 255);
        return rgba(y % 256, x % 256, 0, 255);
    });

    const img1 = createMockImage(W, H, (x, y) => {
        if (y >= H - FOOTER) {
            // 每行只有 1 个像素不同（0.5%）
            if (x === 0) return rgba(255, 0, 0, 255); // 完全不同的像素
            return rgba(80, 80, 80, 255);
        }
        return rgba((y + 100) % 256, (x + 50) % 256, 200, 255);
    });

    const result = detectFixedRegions(img0, img1);
    assert(result.footerHeight > 0, `footerHeight = ${result.footerHeight} (expected > 0 with 98% threshold)`);
}

// ---------- Test 5: 底部安全区像素不同但 tab 栏相同 ----------
console.log('\nTest 5: 底部 6px 安全区不同，但 tab 栏 50px 相同（应跳过安全区检测到 tab 栏）');
{
    const W = 100, H = 300;
    const TAB_HEIGHT = 50;

    const img0 = createMockImage(W, H, (x, y) => {
        if (y >= H - 6) return rgba(10, 10, 10, 255);                         // 安全区
        if (y >= H - 6 - TAB_HEIGHT) return rgba(150, 150, 150, 255);         // tab 栏
        return rgba(y % 256, x % 256, 0, 255);
    });

    const img1 = createMockImage(W, H, (x, y) => {
        if (y >= H - 6) return rgba(20, 20, 20, 255);                         // 安全区（不同！）
        if (y >= H - 6 - TAB_HEIGHT) return rgba(150, 150, 150, 255);         // tab 栏（相同）
        return rgba((y + 80) % 256, (x + 40) % 256, 100, 255);
    });

    const result = detectFixedRegions(img0, img1);
    assert(result.footerHeight >= TAB_HEIGHT, `footerHeight = ${result.footerHeight} (expected >= ${TAB_HEIGHT})`);
}

// ---------- Test 6: 间隙容忍 - header 中有 1 行阴影差异 ----------
console.log('\nTest 6: header 中第 20 行有阴影渲染差异（应被间隙容忍跳过）');
{
    const W = 100, H = 300;
    const HEADER = 40;

    const img0 = createMockImage(W, H, (x, y) => {
        if (y < HEADER) return rgba(200, 200, 200, 255);
        return rgba(y % 256, x % 256, 0, 255);
    });

    const img1 = createMockImage(W, H, (x, y) => {
        if (y < HEADER) {
            if (y === 20) return rgba(0, 0, 0, 255); // 第 20 行完全不同（阴影）
            return rgba(200, 200, 200, 255);
        }
        return rgba((y + 60) % 256, (x + 30) % 256, 50, 255);
    });

    const result = detectFixedRegions(img0, img1);
    // MAX_GAP=2，所以 1 行不匹配应该被跳过，继续检测到 HEADER
    assert(result.headerHeight >= HEADER - 1, `headerHeight = ${result.headerHeight} (expected >= ${HEADER - 1})`);
}

// ===== 汇总 =====
console.log(`\n========================================`);
console.log(`Total: ${passed + failed}  Passed: ${passed}  Failed: ${failed}`);
if (failed > 0) {
    process.exit(1);
} else {
    console.log('All tests passed!');
    process.exit(0);
}
