# wechat-devtools MCP：`Network.enable` 最小 Patch 方案

## 目标

在现有 CDP 采集链路上增加网络请求观测，使调用方能够：

1. 查看 `wx.request` 的 URL、方法、query 参数与可选请求体；
2. 可选查看响应状态与 MIME type；
3. 以 URL 正则筛选埋点/API 请求；
4. 通过现有 `wechat_inspector` 聚合接口获取结果，不新增 MCP tool。

本方案只做**观察**，不拦截、修改、重放或 mock 网络请求。

建议目标版本为 `v0.9.16`。实现前须基于实际发布包或上游源码确认 bundle 的模块路径；本仓库只含
文档，不能将路径假定为已验证的源码事实。

## 最小改动范围

复用 daemon 已建立的 CDP target/WebSocket 连接和 `wechat_inspector` 的采集、限量与
`detail_level` 约定：

| 位置 | 最小改动 |
| --- | --- |
| CDP collector | 在选定的小程序运行时 target 上发送 `Network.enable`，并订阅网络事件。 |
| CDP collector | 按 `requestId` 缓存请求元数据，按需合并 `responseReceived` 状态；不读取 response body。 |
| `wechat_inspector` | 增加 `action="network"`，复用 `duration`、`cdp_port`，并增加网络采集专用参数。 |
| 文档/Skill | 补充 `network` action、返回结构、隐私限制和排查流程。 |

不改动 `wechat_navigate` 的返回结构；后续如有需要，可单独设计“跳转期间网络瀑布”能力。

## CDP 协议流程

1. 按当前 `cdp` action 的 target 过滤规则，连接小程序运行时 target，排除 IDE 壳页、
   `devtools://` target。
2. 默认只连接 URL 含 `/appservice/` 的逻辑层 target；`wx.request` 通常由此发起。调用方可用
   `appservice_only=false` 覆盖，以排查特殊版本或渲染层请求。
3. 在每个选定 target 上发送 `Network.enable`。首版不传缓存、buffer 大小等可选参数，避免改变
   DevTools 的默认行为。
4. 在 `duration` 窗口内处理下列事件：

   | 事件 | 记录内容 |
   | --- | --- |
   | `Network.requestWillBeSent` | `requestId`、时间、URL、method、可选 `postData`、target hint。 |
   | `Network.responseReceived` | 在 `include_responses=true` 时合并状态码与 MIME type。 |
   | `Network.loadingFinished` | 结束时间、encodedDataLength。 |
   | `Network.loadingFailed` | `errorText`、`canceled`、`blockedReason`，作为失败请求返回。 |

5. 采集结束时移除本次事件监听、清理按 `requestId` 的临时缓存，并在格式化后按
   `max_requests` 截断结果。

`requestWillBeSentExtraInfo` 和 `responseReceivedExtraInfo` 暂不作为首版依赖：不同 CDP target
对这些事件的支持可能不同。收到时可补充 headers，但未收到不影响基础请求/响应观测。

## MCP 接口

```text
wechat_inspector(
  action="network",
  duration=10,
  cdp_port=9222,
  url_pattern="dig\\.|ulog|track",
  include_post_data=true,
  include_responses=false,
  max_requests=100,
  appservice_only=true
)
```

参数定义：

- `duration`：采集窗口，范围 1～120 秒；
- `cdp_port`：必须与 `wechat_ide(action="open")` 使用的端口一致；
- `url_pattern`：可选 JavaScript RegExp；只返回匹配 URL 的请求。无 pattern 时全部请求均匹配；
- `include_post_data`：默认 `true`；是否返回 `request.postData`；
- `include_responses`：默认 `false`；是否合并 `responseReceived` 的 status 和 MIME type；
- `max_requests`：默认 100，范围 1～500；
- `appservice_only`：默认 `true`；仅订阅 `/appservice/` target，以减少 pageframe 噪音。

正则编译失败必须返回输入验证错误；CDP 端口不可用应返回 `CDP_UNAVAILABLE`，而不是空的成功结果。

## 建议返回结构

```json
{
  "success": true,
  "data": {
    "summary": {
      "total": 3,
      "matched": 2,
      "failed": 0,
      "truncated": false,
      "cdp_available": true,
      "network_enabled_targets": 1
    },
    "requests": [
      {
        "request_id": "1234.5",
        "url": "https://api.example.com/orders?evt=123",
        "method": "POST",
        "query": {"evt": "123"},
        "post_data": "[{\"event\":\"Module_View\"}]",
        "target_hint": "appservice",
        "matched": true,
        "status": 200,
        "mime_type": "application/json",
        "duration_ms": 142,
        "encoded_data_length": 381
      }
    ]
  },
  "message": "采集 10 秒，共 3 条请求，匹配 2 条。"
}
```

`matched` 表示是否命中 `url_pattern`。`target_hint` 为 `appservice`、`pageframe` 或 `other`。
每个 requestId 只返回一条合并记录；没有收到 response 事件时 `status` 与 `mime_type` 为 `null`。

## 数据安全与边界

- 返回前对 URL query 和 `postData` 中名称匹配 `authorization`、`cookie`、`token`、`secret`、
  `password`、`openid`、`session` 的字段值做掩码；匹配不区分大小写。
- `postData` 限制为每条 64 KiB，超过时截断并标记 `post_data_truncated=true`。
- 不在 daemon 日志、异常消息或持久化缓存中写入原始 `postData`。
- 只采集调用期间新发生的请求；不会回放 Network 历史缓冲，避免把无关会话数据返回给调用方。

## 验收

1. 以 `wechat_ide(action="open", cdp_enabled=true)` 启动目标项目，并确认 CDP 端口可连接。
2. 调用 `wechat_inspector(action="network", duration=15, url_pattern="dig\\.|ulog|track")`，在采集
   窗口内触发一个 JSON GET 和一个 JSON POST。
3. 返回结果包含匹配请求的 method、脱敏后的 URL/query、`post_data`、`target_hint`；开启
   `include_responses` 后还包含状态码。
4. 触发一个失败请求，结果包含 `failed` 计数和 `error_text`，且不影响其他请求。
5. 无 pattern 时不崩溃，有 pattern 时 `summary.matched` 正确；`network_enabled_targets >= 1`。
6. CDP 未开启时返回 `CDP_UNAVAILABLE`，不返回空 success。
7. 触发含 `Authorization`/`Cookie`/`token` 的请求，确认原始敏感值不出现在返回值或 daemon 日志中。

## 实现落点

实际文件路径应在实现前从发布包/上游源码核实。预期最小改动为：

1. 扩展 CDP core 的 target 发现和 IDE 壳过滤，新增 Network 专用连接与 discovery；
2. 增加 Network listener，采集至 deadline 后返回原始事件；
3. 注册 listener 到 daemon bundle，并重新生成 bundle；
4. 扩展 inspector schema 与 action 分发，执行 listener、按 requestId 合并、过滤、脱敏并限量；
5. 将 CDP/Network 域不支持、端口不可用与 daemon 异常转换为可观测错误码。

Network 应使用独立 WebSocket 连接，避免将持续的 Network 事件与既有 Console/Runtime/Log 采集混合，
也避免改变 `cdp` action 的返回语义。

## 上游 PR 文档同步（必须）

实现 PR 必须同时更新下列文件：

| 文件 | 必须同步的内容 |
| --- | --- |
| `MCP_DOC.md` | `wechat_inspector` action 表增加 `network`，列出网络专用参数、前置条件、错误码与返回示例。 |
| `.agents/skills/wechat-devtools/SKILL.md` | 增加埋点/API 验收 SOP，明确 `cdp` 日志采集不等于 `network` 请求采集，并给出“触发 → 抓取 → 断言”的流程。 |
| `README.md` | `v0.9.16` 中文 changelog，说明 Network.enable、默认 appservice target、过滤与脱敏边界。 |
| `README_EN.md` | 与中文 README 等义的 `v0.9.16` changelog。 |

文档必须说明：批量上报可能延迟，应使用足够长的 `duration`（建议 10～15 秒）；`url_pattern` 仅筛选 URL，
POST 埋点字段应从已脱敏的 `post_data` 断言；不得以私有 console hook 作为网络上报验收依据。

## 非目标与后续

首版不提供 HAR 导出、缓存禁用、请求拦截/改写、响应重放、跨调用持久化或 response body。
后续可设计 `Network.getResponseBody`、`wechat_navigate(capture_network=true)`、headers 暴露策略及
独立网络工具；这些能力会扩大权限、状态管理和隐私风险，应在基础观测稳定后单独设计。
