/**
 * automation.js
 * 统一的自动化操作脚本，支持 UI 交互、页面状态修改、wx API 调用等。
 *
 * 导出 { handle, parseArgs } 供 daemon 调用。
 *
 * 支持的 action：
 *   setData       --data <JSON>                  设置页面 Data
 *   callMethod    --method <方法名> [--args <JSON>]  调用页面方法
 *   tap           --selector <CSS选择器>           点击元素
 *   elementInfo   --selector <CSS选择器> [--prop <属性>]  获取元素信息
 *   input         --selector <CSS选择器> --value <值>     输入内容
 *   mockWx        --method <wx方法> --result <JSON>       Mock wx API
 *   callWx        --method <wx方法> [--args <JSON>]       调用 wx API
 *   pageStack                                             获取页面栈
 */

'use strict';

/**
 * 解析命令行参数
 */
function parseArgs(argv) {
    const args = { port: 9420, action: '' };
    for (let i = 2; i < argv.length; i++) {
        switch (argv[i]) {
            case '--port': args.port = parseInt(argv[++i], 10); break;
            case '--action': args.action = argv[++i]; break;
            case '--selector': args.selector = argv[++i]; break;
            case '--data': args.data = argv[++i]; break;
            case '--method': args.method = argv[++i]; break;
            case '--args': args.args = argv[++i]; break;
            case '--value': args.value = argv[++i]; break;
            case '--result': args.result = argv[++i]; break;
            case '--prop': args.prop = argv[++i]; break;
        }
    }
    return args;
}

/**
 * 安全解析 JSON 字符串
 */
function safeParseJson(str, fallback) {
    if (!str) return fallback;
    try { return JSON.parse(str); } catch (e) { return fallback; }
}

async function handle(miniProgram, args) {
    const { action } = args;

    let result = { success: true, action };

    switch (action) {

        // ── 设置页面 Data ──
        case 'setData': {
            const data = safeParseJson(args.data, null);
            if (!data) throw new Error('缺失 --data 参数或 JSON 格式错误');
            const page = await miniProgram.currentPage();
            await page.setData(data);
            result.path = page.path;
            result.updatedKeys = Object.keys(data);
            break;
        }

        // ── 调用页面方法 ──
        case 'callMethod': {
            if (!args.method) throw new Error('缺失 --method 参数');
            const page = await miniProgram.currentPage();
            const methodArgs = safeParseJson(args.args, []);
            const callResult = await page.callMethod(args.method, ...methodArgs);
            result.path = page.path;
            result.method = args.method;
            result.returnValue = callResult;
            break;
        }

        // ── 点击元素 ──
        case 'tap': {
            if (!args.selector) throw new Error('缺失 --selector 参数');
            const page = await miniProgram.currentPage();
            const el = await page.$(args.selector);
            if (!el) throw new Error(`未找到元素: ${args.selector}`);
            await el.tap();
            result.selector = args.selector;
            result.tapped = true;
            break;
        }

        // ── 获取元素信息 ──
        case 'elementInfo': {
            if (!args.selector) throw new Error('缺失 --selector 参数');
            const page = await miniProgram.currentPage();
            const el = await page.$(args.selector);
            if (!el) throw new Error(`未找到元素: ${args.selector}`);

            const info = {
                tagName: el.tagName,
                text: await el.text(),
                wxml: await el.wxml(),
                size: await el.size(),
                offset: await el.offset(),
            };

            // 如果指定了具体样式属性
            if (args.prop) {
                info.style = {};
                info.style[args.prop] = await el.style(args.prop);
            }

            result.selector = args.selector;
            result.element = info;
            break;
        }

        // ── 输入内容 ──
        case 'input': {
            if (!args.selector) throw new Error('缺失 --selector 参数');
            if (args.value === undefined) throw new Error('缺失 --value 参数');
            const page = await miniProgram.currentPage();
            const el = await page.$(args.selector);
            if (!el) throw new Error(`未找到元素: ${args.selector}`);
            await el.input(args.value);
            result.selector = args.selector;
            result.inputValue = args.value;
            break;
        }

        // ── Mock wx API ──
        case 'mockWx': {
            if (!args.method) throw new Error('缺失 --method 参数');
            const mockResult = safeParseJson(args.result, null);
            if (mockResult === null) throw new Error('缺失 --result 参数或 JSON 格式错误');
            await miniProgram.mockWxMethod(args.method, mockResult);
            result.method = args.method;
            result.mocked = true;
            break;
        }

        // ── 调用 wx API ──
        case 'callWx': {
            if (!args.method) throw new Error('缺失 --method 参数');
            const wxArgs = safeParseJson(args.args, []);
            // callWxMethod 接受展开参数
            const wxResult = await miniProgram.callWxMethod(args.method, ...wxArgs);
            result.method = args.method;
            result.returnValue = wxResult;
            break;
        }

        // ── 获取页面栈 ──
        case 'pageStack': {
            const stack = await miniProgram.pageStack();
            result.pages = stack.map(p => ({ path: p.path, query: p.query }));
            result.depth = stack.length;
            break;
        }

        default:
            throw new Error(`未知 action: ${action}`);
    }

    return result;
}

module.exports = { handle, parseArgs };
