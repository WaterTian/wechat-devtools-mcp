/**
 * console_listener.js
 * 连接微信开发者工具自动化端口，监听 console 和 exception 事件。
 * 在指定时间窗口内收集日志，以 JSON 格式返回。
 *
 * 导出 { handle, parseArgs } 供 daemon 调用。
 *
 * 参数：
 *   --port      自动化端口（默认 9420）
 *   --duration  采集持续时间，秒（默认 10，范围 1~120）
 *   --type      监听类型：all（日志+异常）、console（仅日志）、exception（仅异常）
 *   --tap       可选：在采集期间自动点击指定 CSS 选择器的元素
 *   --tap-delay 可选：延迟多少毫秒后再点击（默认 500ms）
 */

'use strict';

// ── 参数解析 ──────────────────────────────────────────────────────────────────

function parseArgs(argv) {
  const args = { port: 9420, duration: 10, type: 'all', tap: '', tapDelay: 500 };
  for (let i = 2; i < argv.length; i++) {
    switch (argv[i]) {
      case '--port':
        args.port = parseInt(argv[++i], 10);
        break;
      case '--duration':
        args.duration = Math.min(Math.max(parseInt(argv[++i], 10), 1), 120);
        break;
      case '--type':
        args.type = argv[++i]; // all | console | exception
        break;
      case '--tap':
        args.tap = argv[++i]; // CSS 选择器
        break;
      case '--tap-delay':
        args.tapDelay = Math.max(parseInt(argv[++i], 10), 0);
        break;
    }
  }
  return args;
}

// ── 时间格式化 ────────────────────────────────────────────────────────────────

function formatTime(ts) {
  const d = new Date(ts);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  const ms = String(d.getMilliseconds()).padStart(3, '0');
  return `${hh}:${mm}:${ss}.${ms}`;
}

// ── 主处理函数 ────────────────────────────────────────────────────────────────

async function handle(miniProgram, args) {
  const { duration, type, tap, tapDelay } = args;

  const consoleLogs = [];
  const exceptions = [];
  let tapResult = null;

  // 注册 console 事件监听
  if (type === 'all' || type === 'console') {
    miniProgram.on('console', (msg) => {
      const ts = Date.now();
      consoleLogs.push({
        time: formatTime(ts),
        timestamp: ts,
        type: msg.type || 'log',
        args: msg.args || [],
      });
    });
  }

  // 注册 exception 事件监听
  if (type === 'all' || type === 'exception') {
    miniProgram.on('exception', (err) => {
      const ts = Date.now();
      exceptions.push({
        time: formatTime(ts),
        timestamp: ts,
        message: err.message || String(err),
        stack: err.stack || '',
      });
    });
  }

  // 如果指定了 --tap，在延迟后自动点击元素
  if (tap) {
    setTimeout(async () => {
      try {
        const page = await miniProgram.currentPage();
        const el = await page.$(tap);
        if (el) {
          await el.tap();
          tapResult = { success: true, selector: tap };
        } else {
          tapResult = { success: false, error: `未找到元素: ${tap}` };
        }
      } catch (tapErr) {
        tapResult = { success: false, error: tapErr.message || String(tapErr) };
      }
    }, tapDelay);
  }

  // 等待指定时间
  await new Promise((resolve) => setTimeout(resolve, duration * 1000));

  return {
    success: true,
    port: args.port,
    duration,
    console_logs: consoleLogs,
    exceptions: exceptions,
    tap_result: tapResult,
    summary: buildSummary(consoleLogs, exceptions),
  };
}

function buildSummary(consoleLogs, exceptions) {
  const counts = { log: 0, warn: 0, error: 0, info: 0, debug: 0 };
  for (const entry of consoleLogs) {
    const t = entry.type || 'log';
    if (t in counts) counts[t]++;
    else counts.log++;
  }
  return {
    total_logs: consoleLogs.length,
    logs: counts.log,
    warnings: counts.warn,
    errors: counts.error,
    info: counts.info,
    debug: counts.debug,
    exceptions: exceptions.length,
  };
}

module.exports = { handle, parseArgs };
