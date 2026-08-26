/**
 * screenshot.js
 * 小程序截图脚本，支持多屏滚动拼接（使用纯 JS 的 jimp 库，可被 ncc 完整打包）。
 *
 * 导出 { handle, parseArgs } 供 daemon 调用。
 *
 * 核心策略：
 *   1. 首步用保守步长（半屏）起步 —— 此时尚不知固定头尾多高，步长偏小只多些
 *      重叠（会被裁掉），步长偏大则造成无法追补的内容缺口，代价不对等
 *   2. 拍完第二段后识别固定头部/底部，再把步长放宽到真实所需
 *   3. 识别判据是「找会动的」：img1 是 img0 滚动 delta 后的图，能按 delta 找到
 *      对应行的即滚动内容，其余为固定区域。不要求固定元素像素级稳定，
 *      因此半透明导航栏、跳变的状态栏时钟都不会使其失效
 *   4. 拼接时每段只取内容条带，最终图 = 头部(1份) + 所有内容条带 + 底部(1份)
 *   5. 根据实际截图尺寸推算真实 DPR，确保裁剪精度
 *   6. 每次滚动后验证实际 scrollTop，动态计算真实重叠量
 *   7. 拍不全或测不准时如实上报（truncated / contentGaps / detectionConfident /
 *      isScrollViewPage），绝不让调用方以为拿到了完整长图
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
 * 等待滚动完成，返回实际的 scrollTop（逻辑像素）。
 *
 * @param {number} fromScrollTop - 本次滚动前的位置，用于区分「还没动」与「到底了」
 * @param {number} minSettle - 未观测到位移时，至少等待多久才认可当前值（毫秒）
 *
 * 为什么需要 fromScrollTop：旧实现只要连续两次读数相同就返回。若 pageScrollTo
 * 尚未生效（渲染层滞后 >100ms），两次读到的都还是**滚动前**的位置，于是返回旧值，
 * 调用方算出 actualDelta <= 0 判定「已到底部」直接 break —— 长图就这样被截断在
 * 前两屏，且没有任何报错。现在要求「确认动过」或「等够 minSettle」才认可稳定值：
 * 真到底部时静止读数会在 minSettle 后被接受，行为不变；只是慢启动不再被误判。
 */
async function waitForScrollComplete(miniProgram, targetScrollY, fromScrollTop = -1, maxWait = 1500, minSettle = 500) {
    const startTime = Date.now();
    let lastScrollTop = -1;
    let moved = false;

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

            if (fromScrollTop < 0 || scrollTop !== fromScrollTop) {
                moved = true;
            }

            if (scrollTop === lastScrollTop && (moved || Date.now() - startTime >= minSettle)) {
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

/** 跨图、跨行比较：imgA 的第 yA 行 与 imgB 的第 yB 行是否为同一内容。 */
function rowsAlike(imgA, yA, imgB, yB, width, tolerance, matchRatio) {
    if (yA < 0 || yA >= imgA.bitmap.height) return false;
    if (yB < 0 || yB >= imgB.bitmap.height) return false;
    let matched = 0;
    for (let x = 0; x < width; x++) {
        if (pixelsClose(imgA.getPixelColor(x, yA), imgB.getPixelColor(x, yB), tolerance)) {
            matched++;
        }
    }
    return (matched / width) >= matchRatio;
}

// 检测参数。相较旧版放宽了单行容差与匹配率：新判据靠「是否按 delta 位移」定性，
// 不再要求固定元素像素级稳定，因此不需要靠严阈值来压误判。
const TOLERANCE = 6;        // RGB 通道容差（吸收抗锯齿差异）
const MATCH_RATIO = 0.95;   // 行内像素匹配率
const RUN = 3;              // 连续多少行判为内容，才认定内容区已开始
const SHIFT_JITTER = 2;     // delta 取整误差的搜索半径

/**
 * 判断某行是否为「滚动内容」——即它能在另一张图里按 delta 找到对应行。
 *
 * 为什么要 ±SHIFT_JITTER：delta 由 round(逻辑位移 × dpr) 得到，而 dpr 常是
 * 非整数（实测 724/375 ≈ 1.93），真实位移未必是整数物理像素，直接按 delta
 * 对齐会整行错开一两像素、全是抗锯齿差异。这里在邻域内取最优对齐。
 */
function isMovedRow(imgA, yA, imgB, baseYB, width) {
    for (let d = -SHIFT_JITTER; d <= SHIFT_JITTER; d++) {
        if (rowsAlike(imgA, yA, imgB, baseYB + d, width, TOLERANCE, MATCH_RATIO)) return true;
    }
    return false;
}

/**
 * 检测固定头部/底部的物理像素高度。
 *
 * 判据是「找会动的」，而不是旧版的「找没变的」：
 *
 *   img1 是 img0 向下滚动 delta 后的截图，因此
 *     · img1 第 y 行若是滚动内容，它应等于 img0 的第 y+delta 行
 *     · img0 第 y 行若是滚动内容，它应等于 img1 的第 y-delta 行
 *   「按 delta 位移」是滚动内容的定义性特征，与它长什么样无关。
 *   于是从顶部向下扫，第一处稳定出现的内容行就是内容区起点，其上皆为固定头部；
 *   底部对称处理。
 *
 * 为什么不再沿用旧判据（逐行比对、相同即固定）：
 *   旧判据要求固定元素**像素级稳定**，而现实中固定元素经常不稳定——半透明/毛玻璃
 *   导航栏会透出下方滚动内容、滚动时加阴影或标题渐显、状态栏还带会跳变的时钟。
 *   任一情况都会让它从第 0 行就判负，直接返回 headerHeight=0，导航栏被当作内容
 *   重复拼进每一段。旧版为此堆了 MAX_GAP（容忍分割线）和 SAFE_AREA_SKIP（躲开
 *   Home Indicator）两个补丁，每个补丁都绑死了一种设备/设计假设。
 *   新判据不依赖固定元素稳定，这两个补丁的存在理由随之消失。
 *
 * @param {Object} img0 - 滚动前截图
 * @param {Object} img1 - 滚动后截图
 * @param {number} delta - 两张图之间的滚动距离（物理像素，正数）
 * @returns {{headerHeight:number, footerHeight:number, confident:boolean}}
 *          confident=false 表示无法可靠判定（如懒加载导致内容既不稳定也不位移），
 *          调用方应据此告警而不是把结果当真。
 */
function detectFixedRegions(img0, img1, delta) {
    const width = img0.bitmap.width;
    const height = img0.bitmap.height;

    // delta 不合法（未传、非正、大于等于视口高度=无重叠）时无从判断
    if (!delta || delta <= 0 || delta >= height) {
        return { headerHeight: 0, footerHeight: 0, confident: false };
    }

    // ── 头部：扫 img1 顶部，找第一处连续 RUN 行的滚动内容 ──
    const headerScanLimit = Math.min(Math.floor(height * 0.5), height - delta);
    let headerHeight = 0;
    let headerFound = false;
    let run = 0;
    for (let y = 0; y < headerScanLimit; y++) {
        if (isMovedRow(img1, y, img0, y + delta, width)) {
            if (++run >= RUN) {
                headerHeight = y - RUN + 1;
                headerFound = true;
                break;
            }
        } else {
            run = 0;
        }
    }

    // ── 底部：扫 img0 底部，找最后一处连续 RUN 行的滚动内容 ──
    const footerScanFloor = Math.max(Math.ceil(height * 0.5), delta);
    let footerHeight = 0;
    let footerFound = false;
    run = 0;
    for (let y = height - 1; y >= footerScanFloor; y--) {
        if (isMovedRow(img0, y, img1, y - delta, width)) {
            if (++run >= RUN) {
                footerHeight = height - 1 - (y + RUN - 1);
                footerFound = true;
                break;
            }
        } else {
            run = 0;
        }
    }

    return {
        headerHeight: Math.max(0, headerHeight),
        footerHeight: Math.max(0, footerHeight),
        confident: headerFound && footerFound,
    };
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
    // 内容缺口计数：固定区域吃光滚动重叠时，两段之间的内容是真的丢了。
    // 旧实现用 Math.max(0, ...) 把负重叠夹到 0，缺口被无声吞掉，
    // 拼出来的图看着连续、实则少了一截。这里如实统计并上报。
    let contentGaps = 0;

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
            const rawContentOverlap = segments[i].physicalOverlap - headerHeight - footerHeight;
            if (rawContentOverlap < 0) contentGaps++;
            const contentOverlap = Math.max(0, rawContentOverlap);
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
    return { width, height: totalHeight, contentGaps };
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
        let detectionConfident = true;
        // 页面长到撞上分段上限 —— 拍到的不是完整长图，必须让调用方知道
        let truncated = false;

        if (needsScroll) {
            // 首步刻意保守：此刻还不知道固定头尾有多高，用半屏步长（50% 重叠）起步。
            // 步长偏小只会多一点重叠（重叠会被裁掉，不影响成图），而步长偏大会直接
            // 造成内容缺口且无法追补 —— 两种偏差的代价完全不对等，故向安全一侧取。
            // 第二段拍完、固定区域测出来后，立刻放宽到真实所需步长。
            const conservativeStep = Math.max(1, Math.round(windowHeight * 0.5));
            const requestedStep = Math.max(1, windowHeight - overlap);
            let effectiveStep = Math.min(conservativeStep, requestedStep);
            // 分段上限必须按**实际步长**算，不能按用户请求的步长：固定头尾会吃掉重叠、
            // 把实际步长压小，按请求步长估出来的上限会偏紧，长页面还没拍完就被判"截断"。
            // 实测 points/log 页即因此在 6 段处误报 truncated。步长在检测后会变，故此处
            // 先按保守步长估，检测完再重算。30 是防跑飞的硬上限。
            const capFor = (step) => Math.min(Math.ceil(contentHeight / Math.max(1, step)) + 3, 30);
            let segmentCap = capFor(effectiveStep);
            let prevScrollTop = 0;

            /**
             * 滚到指定位置并截一段。返回 null 表示没滚动（到底了）或截图失败。
             */
            const captureAt = async (index, fromScrollTop, step) => {
                const targetScrollY = fromScrollTop + step;
                try {
                    await miniProgram.pageScrollTo(targetScrollY);
                } catch (e) {
                    return null;
                }

                const actualScrollTop = await waitForScrollComplete(
                    miniProgram, targetScrollY, fromScrollTop);
                const actualDelta = actualScrollTop - fromScrollTop;
                if (actualDelta <= 0) return null;   // 已到底部

                const segPath = path.join(tmpDir, `seg_${index}.png`);
                await miniProgram.screenshot({ path: segPath });
                if (!fs.existsSync(segPath)) return null;

                const logicalOverlap = windowHeight - actualDelta;
                return {
                    segment: {
                        path: segPath,
                        physicalOverlap: Math.max(0, Math.round(logicalOverlap * pixelRatio)),
                    },
                    actualScrollTop,
                    actualDelta,
                };
            };

            for (let i = 1; i < segmentCap; i++) {
                const shot = await captureAt(i, prevScrollTop, effectiveStep);
                if (!shot) break;

                segments.push(shot.segment);
                const { actualScrollTop, actualDelta } = shot;

                // 懒加载列表越滚越长，开拍前那次 page.size() 会严重低估。
                // 实测积分明细页初始高度只够 3 步，实际滚了 6 段仍未到底，
                // 于是被按初始高度算出的上限误判为「截断」。这里跟随页面实际增长
                // 刷新上限；真正无限滚动的列表由 30 段硬上限兜住。
                try {
                    const sz = await page.size();
                    if (sz && sz.height > contentHeight) {
                        contentHeight = sz.height;
                        segmentCap = capFor(effectiveStep);
                    }
                } catch (e) { /* 读不到就沿用现有上限 */ }

                // 第二段截取后，检测固定头部和底部，并据此把步长放宽到真实所需
                if (i === 1 && segments.length === 2) {
                    try {
                        const { Jimp } = require('jimp');
                        const img0 = await Jimp.read(segments[0].path);
                        const img1 = await Jimp.read(segments[1].path);
                        // 传入两段之间的真实物理位移 —— 新判据靠它识别「哪些行在动」
                        const fixed = detectFixedRegions(
                            img0, img1, Math.round(actualDelta * pixelRatio));
                        headerHeight = fixed.headerHeight;
                        footerHeight = fixed.footerHeight;
                        detectionConfident = fixed.confident;

                        // 内容区至少保留 20 逻辑像素重叠，避免拼接错位
                        const fixedTotal = Math.round((headerHeight + footerHeight) / pixelRatio);
                        const neededLogicalOverlap = fixedTotal + 20;
                        // 首步是保守值，这里按实测结果放宽（但不超过用户要求的步长）
                        effectiveStep = Math.min(
                            requestedStep,
                            Math.max(1, windowHeight - neededLogicalOverlap),
                        );
                        // 步长定了，按它重算分段上限
                        segmentCap = capFor(effectiveStep);
                    } catch (e) {
                        // 检测失败：保持保守步长继续拍，宁可多几段也不留缺口
                        detectionConfident = false;
                    }
                }

                // 如果实际滚动距离远小于预期，说明接近底部了
                if (actualDelta < effectiveStep * 0.5) {
                    break;
                }

                prevScrollTop = actualScrollTop;

                // 撞到分段上限：页面比能拍的更长，底部内容拍不到，必须如实上报
                if (i === segmentCap - 1) {
                    truncated = true;
                }
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

        let finalWidth = 0, finalHeight = 0, contentGaps = 0;

        if (jimpAvailable && segments.length > 1) {
            const dims = await stitchImages(segments, absOutput, headerHeight, footerHeight);
            finalWidth = dims.width;
            finalHeight = dims.height;
            contentGaps = dims.contentGaps || 0;
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
            truncated: truncated || undefined,
            contentGaps: contentGaps || undefined,
            detectionConfident: segments.length > 1 ? detectionConfident : undefined,
        };

    } finally {
        try {
            const files = fs.readdirSync(tmpDir);
            for (const f of files) fs.unlinkSync(path.join(tmpDir, f));
            fs.rmdirSync(tmpDir);
        } catch (e) { /* ignore */ }
    }
}

// detectFixedRegions / pixelsClose / rowMatches 一并导出供 tests/ 直接验证真实实现，
// 避免测试复制一份副本、源码改了测试还绿。
module.exports = {
    handle, parseArgs, detectFixedRegions, pixelsClose, rowMatches, rowsAlike,
    waitForScrollComplete,
};
