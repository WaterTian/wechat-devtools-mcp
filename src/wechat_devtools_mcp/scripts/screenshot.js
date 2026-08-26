/**
 * screenshot.js
 * 小程序截图脚本，支持多屏滚动拼接（使用纯 JS 的 jimp 库，可被 ncc 完整打包）。
 *
 * 导出 { handle, parseArgs } 供 daemon 调用。
 *
 * 核心策略：
 *   1. 截取前两屏后，通过像素比对自动检测固定头部（导航栏）和固定底部（tab 栏）
 *   2. 拼接时从每段中只提取可滚动内容区域，避免固定元素重复
 *   3. 最终图片 = 头部(仅1份) + 所有内容条带 + 底部(仅1份)
 *   4. 根据实际截图尺寸推算真实 DPR，确保裁剪精度
 *   5. 每次滚动后验证实际 scrollTop，动态计算真实重叠量
 */

'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');

function parseArgs(argv) {
    const args = { port: 9420, output: '', overlap: 50, fullPage: true, scrollTop: null, page: '' };
    for (let i = 2; i < argv.length; i++) {
        switch (argv[i]) {
            case '--port':    args.port    = parseInt(argv[++i], 10); break;
            case '--output':  args.output  = argv[++i]; break;
            case '--overlap': args.overlap = parseInt(argv[++i], 10); break;
            case '--no-full-page': args.fullPage = false; break;
            case '--scroll-top': args.scrollTop = parseInt(argv[++i], 10); break;
            case '--page': args.page = argv[++i]; break;
        }
    }
    return args;
}

/**
 * 等待滚动完成，返回实际的 scrollTop（逻辑像素）
 */
async function waitForScrollComplete(miniProgram, targetScrollY, maxWait = 1000) {
    const startTime = Date.now();
    let lastScrollTop = -1;

    while (Date.now() - startTime < maxWait) {
        await new Promise(r => setTimeout(r, 100));
        try {
            const scrollTop = await miniProgram.evaluate(function () {
                return new Promise(function (resolve) {
                    var query = wx.createSelectorQuery();
                    query.selectViewport().scrollOffset().exec(function (res) {
                        resolve(res && res[0] ? res[0].scrollTop : 0);
                    });
                });
            });

            if (scrollTop === lastScrollTop) {
                return scrollTop;
            }
            lastScrollTop = scrollTop;
        } catch (e) {
            await new Promise(r => setTimeout(r, 200));
            return targetScrollY;
        }
    }

    return lastScrollTop >= 0 ? lastScrollTop : targetScrollY;
}

/**
 * 判断两个像素颜色是否在容差范围内相近（忽略亚像素渲染差异）。
 * Jimp 的 getPixelColor 返回 32 位 RGBA 整数。
 */
function pixelsClose(c1, c2, tolerance) {
    if (c1 === c2) return true;
    const r1 = (c1 >>> 24) & 0xFF, r2 = (c2 >>> 24) & 0xFF;
    const g1 = (c1 >>> 16) & 0xFF, g2 = (c2 >>> 16) & 0xFF;
    const b1 = (c1 >>> 8)  & 0xFF, b2 = (c2 >>> 8)  & 0xFF;
    return Math.abs(r1 - r2) <= tolerance
        && Math.abs(g1 - g2) <= tolerance
        && Math.abs(b1 - b2) <= tolerance;
}

/**
 * 判断一行像素是否匹配（允许少量像素不同）。
 * @param {number} matchRatio - 匹配阈值，默认 0.98（允许 2% 像素不同）
 */
function rowMatches(img0, img1, y, width, tolerance, matchRatio) {
    let matched = 0;
    for (let x = 0; x < width; x++) {
        if (pixelsClose(img0.getPixelColor(x, y), img1.getPixelColor(x, y), tolerance)) {
            matched++;
        }
    }
    return (matched / width) >= matchRatio;
}

/**
 * 通过像素比对检测固定头部和固定底部的物理像素高度。
 * 比较两张不同滚动位置的截图，从顶部/底部逐行比对，连续相同的行即为固定区域。
 *
 * v0.5.0 改进：
 *   - 使用颜色容差（tolerance=3）代替精确匹配，兼容亚像素渲染差异
 *   - 行级匹配阈值 98%，允许少量边缘像素不同
 *   - 底部检测跳过安全区域（最底部 6px），避免 Home Indicator 干扰
 *   - 允许最多 2 行连续不匹配后继续扫描（应对分割线/阴影渲染差异）
 */
function detectFixedRegions(img0, img1) {
    const width = img0.bitmap.width;
    const height = img0.bitmap.height;
    const maxScan = Math.floor(height / 3); // 最多扫描 1/3 视口
    const TOLERANCE = 3;       // RGB 通道容差
    const MATCH_RATIO = 0.98;  // 行内像素匹配阈值
    const MAX_GAP = 2;         // 允许连续不匹配行数（应对阴影/分割线）
    const SAFE_AREA_SKIP = 6;  // 底部安全区域跳过像素数（Home Indicator）

    // 检测固定头部：从顶部逐行比较
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

    // 检测固定底部：从底部逐行比较，跳过安全区域
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

    // 修正：如果跳过了安全区域，将其加入 footer 高度
    if (footerHeight > 0) {
        footerHeight += SAFE_AREA_SKIP;
    }

    return { headerHeight, footerHeight };
}

/**
 * 智能拼接：自动处理固定头部/底部，仅拼接可滚动内容区域。
 * 最终图片 = header(1份) + 所有 content 条带 + footer(1份)
 *
 * @param {Array<{path: string, physicalOverlap: number}>} segments
 * @param {string} outputPath
 * @param {number} headerHeight - 固定头部物理像素高度
 * @param {number} footerHeight - 固定底部物理像素高度
 */
async function stitchImages(segments, outputPath, headerHeight, footerHeight) {
    const { Jimp } = require('jimp');

    if (segments.length === 1) {
        fs.copyFileSync(segments[0].path, outputPath);
        const img = await Jimp.read(segments[0].path);
        return { width: img.bitmap.width, height: img.bitmap.height };
    }

    const images = await Promise.all(segments.map(s => Jimp.read(s.path)));
    const width = images[0].bitmap.width;
    const imgHeight = images[0].bitmap.height;

    // 无固定元素时退化为简单模式
    const hasFixedRegions = headerHeight > 0 || footerHeight > 0;

    if (!hasFixedRegions) {
        // 简单模式：与之前逻辑一致
        let totalHeight = imgHeight;
        for (let i = 1; i < images.length; i++) {
            const h = images[i].bitmap.height;
            const cropTop = Math.min(segments[i].physicalOverlap, h - 1);
            totalHeight += h - cropTop;
        }

        const canvas = new Jimp({ width, height: totalHeight, color: 0xffffffff });
        canvas.composite(images[0], 0, 0);
        let yOffset = imgHeight;

        for (let i = 1; i < images.length; i++) {
            const h = images[i].bitmap.height;
            const cropTop = Math.min(segments[i].physicalOverlap, h - 1);
            const cropped = images[i].clone().crop({ x: 0, y: cropTop, w: width, h: h - cropTop });
            canvas.composite(cropped, 0, yOffset);
            yOffset += h - cropTop;
        }

        await canvas.write(outputPath);
        return { width, height: totalHeight };
    }

    // ===== 智能模式：处理固定头部/底部 =====

    // 从每段中提取内容条带（去掉 header 和 footer）
    const contentStrips = [];

    for (let i = 0; i < images.length; i++) {
        const h = images[i].bitmap.height;
        const contentTop = headerHeight;
        const contentBottom = h - footerHeight;
        const contentHeight = contentBottom - contentTop;

        if (contentHeight <= 0) {
            // 极端情况：header + footer >= 整个视口，跳过
            continue;
        }

        // 提取内容区域
        const strip = images[i].clone().crop({
            x: 0,
            y: contentTop,
            w: width,
            h: contentHeight,
        });

        if (i === 0) {
            // 第一段内容完整保留
            contentStrips.push(strip);
        } else {
            // 后续段：裁掉内容重叠区域
            // 内容重叠 = 视口总重叠 - 头部 - 底部（固定区域在重叠区内各占一份）
            const contentOverlap = Math.max(0, segments[i].physicalOverlap - headerHeight - footerHeight);
            const cropTop = Math.min(contentOverlap, strip.bitmap.height - 1);

            if (cropTop > 0) {
                const cropped = strip.crop({
                    x: 0,
                    y: cropTop,
                    w: width,
                    h: strip.bitmap.height - cropTop,
                });
                contentStrips.push(cropped);
            } else {
                contentStrips.push(strip);
            }
        }
    }

    // 计算总高度 = header + 所有内容条带 + footer
    let totalContentHeight = 0;
    for (const strip of contentStrips) {
        totalContentHeight += strip.bitmap.height;
    }
    const totalHeight = headerHeight + totalContentHeight + footerHeight;

    // 创建画布
    const canvas = new Jimp({ width, height: totalHeight, color: 0xffffffff });

    // 1. 贴 header（从第一段截取）
    if (headerHeight > 0) {
        const header = images[0].clone().crop({ x: 0, y: 0, w: width, h: headerHeight });
        canvas.composite(header, 0, 0);
    }

    // 2. 贴所有内容条带
    let yOffset = headerHeight;
    for (const strip of contentStrips) {
        canvas.composite(strip, 0, yOffset);
        yOffset += strip.bitmap.height;
    }

    // 3. 贴 footer（从最后一段截取）
    if (footerHeight > 0) {
        const lastImg = images[images.length - 1];
        const footer = lastImg.clone().crop({
            x: 0,
            y: lastImg.bitmap.height - footerHeight,
            w: width,
            h: footerHeight,
        });
        canvas.composite(footer, 0, yOffset);
    }

    await canvas.write(outputPath);
    return { width, height: totalHeight };
}

async function handle(miniProgram, args) {
    const { output, overlap, fullPage, scrollTop, page: targetPage } = args;

    if (!output) {
        return { success: false, error: '缺失 --output 参数' };
    }

    const outputDir = path.dirname(path.resolve(output));
    if (!fs.existsSync(outputDir)) {
        try { fs.mkdirSync(outputDir, { recursive: true }); } catch (e) { /* ignore */ }
    }

    // 检查 jimp 是否可用
    let jimpAvailable = false;
    try { require('jimp').Jimp; jimpAvailable = true; } catch (e) { /* 降级单屏 */ }

    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'wechat_screenshot_'));

    try {
        // 获取窗口尺寸和设备像素比
        let windowHeight = 667;
        let windowWidth = 375;
        let pixelRatio = 1;
        try {
            const sysInfo = await miniProgram.systemInfo();
            windowHeight = sysInfo.windowHeight || 667;
            windowWidth = sysInfo.windowWidth || 375;
            pixelRatio = sysInfo.pixelRatio || 1;
        } catch (e) { /* ignore */ }

        let page = await miniProgram.currentPage();

        // 如果指定了目标页面且当前页面不匹配，自动跳转
        const stripIndex = (p) => (p || '').replace(/\/index$/, '');
        if (targetPage && page && stripIndex(page.path) !== stripIndex(targetPage.replace(/^\//, '').split('?')[0])) {
            const pagePath = '/' + targetPage.replace(/^\//, '');
            const navPath = pagePath.split('?')[0];
            try {
                try {
                    await miniProgram.switchTab(navPath);
                } catch (_) {
                    await miniProgram.navigateTo(pagePath);
                }
                await new Promise(r => setTimeout(r, 2000));
                page = await miniProgram.currentPage();

                // 验证导航是否真正生效
                const actual = stripIndex(page.path);
                const expected = stripIndex(targetPage.replace(/^\//, '').split('?')[0]);
                if (actual !== expected) {
                    return {
                        success: false,
                        error: `跳转失败：期望 ${targetPage}，实际停留在 ${page.path}`,
                        hint: '请确认页面路径正确。提示：末尾可能需要 /index（如 pages/foo/index）',
                    };
                }
            } catch (e) {
                return {
                    success: false,
                    error: `跳转异常: ${e.message || e}`,
                    hint: '请确认页面路径正确，小程序页面是否已在 app.json 注册',
                };
            }
        }

        // 获取页面内容高度（逻辑像素）
        let contentHeight = windowHeight;
        try {
            const sz = await page.size();
            if (sz && sz.height > 0) contentHeight = sz.height;
        } catch (e) { /* ignore */ }

        // 检测 scroll-view 页面：page.size() ≈ windowHeight 但实际有 scroll-view 内滚动
        // 注意：automator 的 screenshot() 无法捕获 scroll-view 内部滚动后的渲染帧，
        // 因此 scroll-view 页面无法做长图拼接，仅截取当前视口并提示调用方。
        let isScrollViewPage = false;
        if (contentHeight <= windowHeight * 1.05) {
            try {
                const sv = await page.$('scroll-view');
                if (sv) {
                    const sh = await sv.scrollHeight();
                    if (sh > windowHeight * 1.05) {
                        isScrollViewPage = true;
                    }
                }
            } catch (e) { /* ignore */ }
        }

        const absOutput = path.resolve(output);

        // segments 数组：记录每段的路径和需要裁剪的顶部物理像素数
        const segments = [];

        // 长图模式：先滚到顶部确保起始位置正确（视口模式跳过，保留 scrollTop 位置）
        if (fullPage) {
            try {
                await miniProgram.pageScrollTo(0);
                await new Promise(r => setTimeout(r, 300));
            } catch (e) { /* ignore */ }
        }

        // 截图前滚动到指定位置（视口模式 scrollTop）
        if (scrollTop !== null && !fullPage) {
            try {
                await miniProgram.pageScrollTo(scrollTop);
                await new Promise(r => setTimeout(r, 300));
            } catch (e) { /* ignore */ }
        }

        // 截第一屏
        const seg0Path = path.join(tmpDir, 'seg_0.png');
        await miniProgram.screenshot({ path: seg0Path });
        if (!fs.existsSync(seg0Path)) {
            throw new Error('截图失败：未获取到第一屏图片');
        }
        segments.push({ path: seg0Path, physicalOverlap: 0 });

        // 从第一屏截图中获取实际物理像素高度，推算真实 DPR
        if (jimpAvailable) {
            try {
                const { Jimp } = require('jimp');
                const firstImg = await Jimp.read(seg0Path);
                const actualPhysicalHeight = firstImg.bitmap.height;
                const measuredDPR = actualPhysicalHeight / windowHeight;
                if (measuredDPR > 0.5 && measuredDPR < 5) {
                    pixelRatio = measuredDPR;
                }
            } catch (e) { /* 使用 systemInfo 的 pixelRatio */ }
        }

        const needsScroll = fullPage && jimpAvailable && contentHeight > windowHeight * 1.05;

        // 固定区域检测结果（截取第二段后检测）
        let headerHeight = 0;
        let footerHeight = 0;

        if (needsScroll) {
            let effectiveStep = Math.max(1, windowHeight - overlap);
            const maxSegments = Math.min(Math.ceil(contentHeight / effectiveStep) + 2, 30);
            let prevScrollTop = 0;

            for (let i = 1; i < maxSegments; i++) {
                const targetScrollY = prevScrollTop + effectiveStep;

                try {
                    await miniProgram.pageScrollTo(targetScrollY);
                } catch (e) {
                    break;
                }

                // 等待滚动完成并获取实际滚动位置
                const actualScrollTop = await waitForScrollComplete(miniProgram, targetScrollY);

                // 实际滚动距离（逻辑像素）
                const actualDelta = actualScrollTop - prevScrollTop;

                // 如果没有实际滚动（已到底部），停止
                if (actualDelta <= 0) {
                    break;
                }

                const segPath = path.join(tmpDir, `seg_${i}.png`);
                await miniProgram.screenshot({ path: segPath });
                if (!fs.existsSync(segPath)) break;

                // 计算本段需要裁剪的物理像素
                const logicalOverlap = windowHeight - actualDelta;
                const physicalOverlap = Math.round(logicalOverlap * pixelRatio);

                segments.push({ path: segPath, physicalOverlap: Math.max(0, physicalOverlap) });

                // 第二段截取后，检测固定头部和底部
                if (i === 1 && segments.length === 2) {
                    try {
                        const { Jimp } = require('jimp');
                        const img0 = await Jimp.read(segments[0].path);
                        const img1 = await Jimp.read(segments[1].path);
                        const fixed = detectFixedRegions(img0, img1);
                        headerHeight = fixed.headerHeight;
                        footerHeight = fixed.footerHeight;

                        // 固定区域可能吃掉所有重叠，导致内容缺口
                        // 动态调大步长使内容区有足够重叠（至少 20px）
                        const fixedTotal = Math.round((headerHeight + footerHeight) / pixelRatio);
                        const minContentOverlap = 20;
                        const neededLogicalOverlap = fixedTotal + minContentOverlap;
                        if (overlap < neededLogicalOverlap) {
                            effectiveStep = Math.max(1, windowHeight - neededLogicalOverlap);
                        }
                    } catch (e) { /* 检测失败，按无固定区域处理 */ }
                }

                // 如果实际滚动距离远小于预期，说明接近底部了
                if (actualDelta < effectiveStep * 0.5) {
                    break;
                }

                prevScrollTop = actualScrollTop;
            }

            // 滚回顶部
            try {
                await miniProgram.pageScrollTo(0);
                await new Promise(r => setTimeout(r, 200));
            } catch (e) { /* ignore */ }
        }

        if (segments.length === 0) {
            throw new Error('截图失败：未获取到任何分段图片');
        }

        let finalWidth = 0, finalHeight = 0;

        if (jimpAvailable && segments.length > 1) {
            const dims = await stitchImages(segments, absOutput, headerHeight, footerHeight);
            finalWidth = dims.width;
            finalHeight = dims.height;
        } else {
            fs.copyFileSync(segments[0].path, absOutput);
            if (jimpAvailable) {
                try {
                    const { Jimp } = require('jimp');
                    const img = await Jimp.read(absOutput);
                    finalWidth = img.bitmap.width;
                    finalHeight = img.bitmap.height;
                } catch (e) { /* ignore */ }
            }
        }

        return {
            success: true,
            path: absOutput,
            width: finalWidth,
            height: finalHeight,
            segments: segments.length,
            fixedHeader: headerHeight,
            fixedFooter: footerHeight,
            isScrollViewPage: isScrollViewPage || undefined,
        };

    } finally {
        try {
            const files = fs.readdirSync(tmpDir);
            for (const f of files) fs.unlinkSync(path.join(tmpDir, f));
            fs.rmdirSync(tmpDir);
        } catch (e) { /* ignore */ }
    }
}

module.exports = { handle, parseArgs };
