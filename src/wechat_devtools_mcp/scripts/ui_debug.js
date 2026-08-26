/**
 * ui_debug.js
 * 负责 UI 和状态相关的调试任务：截图、页面数据、Storage、执行代码。
 *
 * 导出 { handle, parseArgs } 供 daemon 调用。
 */

'use strict';

const path = require('path');
const fs = require('fs');

function parseArgs(argv) {
    const args = { port: 9420, action: '', path: '', key: '', code: '', segmentsDir: '', overlap: 50, expectedPath: '' };
    for (let i = 2; i < argv.length; i++) {
        switch (argv[i]) {
            case '--port': args.port = parseInt(argv[++i], 10); break;
            case '--action': args.action = argv[++i]; break; // screenshot, data, storage, evaluate, full_screenshot
            case '--path': args.path = argv[++i]; break; // screenshot path
            case '--key': args.key = argv[++i]; break; // storage key
            case '--code': args.code = argv[++i]; break; // evaluate code
            case '--segments-dir': args.segmentsDir = argv[++i]; break;
            case '--overlap': args.overlap = parseInt(argv[++i], 10); break;
            case '--expected-path': args.expectedPath = argv[++i]; break;
        }
    }
    return args;
}

async function handle(miniProgram, args) {
    const { action } = args;

    let result = { success: true };

    switch (action) {
        case 'full_screenshot': {
            if (!args.segmentsDir) throw new Error('缺失 --segments-dir 参数');
            const sysInfo = await miniProgram.systemInfo();
            const winH = sysInfo.windowHeight;

            const scrollH = await miniProgram.evaluate(function () {
                return new Promise(resolve => {
                    wx.createSelectorQuery()
                        .selectViewport()
                        .scrollOffset(r => resolve(r.scrollHeight))
                        .exec();
                });
            });

            const overlap = args.overlap || 50;
            const step = winH > overlap ? winH - overlap : winH;
            const segments = [];

            if (scrollH <= winH) {
                const segPath = path.join(args.segmentsDir, `seg_0.png`);
                await miniProgram.screenshot({ path: segPath });
                segments.push({ path: segPath, offset: 0, winH });
            } else {
                let offset = 0;
                let segIndex = 0;

                await miniProgram.pageScrollTo(0);
                await new Promise(r => setTimeout(r, 600));

                while (true) {
                    const segPath = path.join(args.segmentsDir, `seg_${segIndex}.png`);
                    await miniProgram.screenshot({ path: segPath });
                    segments.push({ path: segPath, offset, winH });

                    if (offset + winH >= scrollH) {
                        break;
                    }

                    offset += step;
                    if (offset + winH > scrollH) {
                        offset = scrollH - winH;
                    }

                    segIndex++;
                    await miniProgram.pageScrollTo(offset);
                    await new Promise(r => setTimeout(r, 600));
                }
                await miniProgram.pageScrollTo(0);
            }

            result.segments = segments;
            result.scrollHeight = scrollH;
            result.windowHeight = winH;
            break;
        }

        case 'screenshot':
            const savePath = args.path || path.join(process.cwd(), `screenshot_${Date.now()}.png`);
            await miniProgram.screenshot({ path: savePath });
            result.savePath = savePath;
            // 如果文件存在，读取并返回一小段确认信息
            if (fs.existsSync(savePath)) {
                result.fileSize = fs.statSync(savePath).size;
            }
            break;

        case 'data':
            let dataPage = null;
            if (args.expectedPath) {
                const expectedBare = args.expectedPath.split('?')[0];
                const MAX_POLLS = 10;
                const POLL_INTERVAL = 300;
                for (let i = 0; i < MAX_POLLS; i++) {
                    dataPage = await miniProgram.currentPage();
                    if (dataPage && dataPage.path === expectedBare) {
                        break;
                    }
                    if (i < MAX_POLLS - 1) {
                        await new Promise(r => setTimeout(r, POLL_INTERVAL));
                    }
                }
                if (!dataPage || dataPage.path !== expectedBare) {
                    result.path_mismatch = true;
                    result.warning = `当前页面 ${dataPage ? dataPage.path : 'null'} 与预期 ${args.expectedPath} 不符`;
                }
            } else {
                dataPage = await miniProgram.currentPage();
            }
            if (dataPage) {
                result.data = await dataPage.data();
                result.path = dataPage.path;
            } else {
                result.success = false;
                result.error = '无法获取当前页面';
            }
            break;

        case 'storage':
            if (args.key) {
                const storageRes = await miniProgram.callWxMethod('getStorage', { key: args.key });
                result.value = storageRes.data;
            } else {
                const info = await miniProgram.callWxMethod('getStorageInfo');
                result.keys = info.keys;
                result.currentSize = info.currentSize;
                result.limitSize = info.limitSize;
            }
            break;

        case 'evaluate':
            if (!args.code) {
                throw new Error('缺失 --code 参数');
            }
            // 先尝试表达式模式（return + code），失败后 fallback 到语句模式
            try {
                result.result = await miniProgram.evaluate(new Function('return ' + args.code));
            } catch (evalErr) {
                if (evalErr.message && evalErr.message.includes('Unexpected token')) {
                    result.result = await miniProgram.evaluate(new Function(args.code));
                } else {
                    throw evalErr;
                }
            }
            break;

        default:
            throw new Error(`未知 action: ${action}`);
    }

    return result;
}

module.exports = { handle, parseArgs };
