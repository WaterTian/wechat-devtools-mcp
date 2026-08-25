# wechat-devtools MCP：`Network.enable` 最小 Patch 方案

## 目标

在现有 CDP 采集链路上增加网络请求观测，使调用方能够：

1. 查看请求的 URL、方法、请求头和 query 参数；
2. 查看请求体参数（例如 JSON、form-urlencoded）；
3. 查看响应状态、响应头和响应体；
4. 通过现有 `wechat_inspector` 聚合接口获取结果，不新增 MCP tool。

本方案只做**观察**，不拦截、修改、重放或 mock 网络请求。

## 最小改动范围

复用 daemon 已建立的 CDP target/WebSocket 连接和 `wechat_inspector` 的采集、限量与
`detail_level` 约定：

| 位置 | 最小改动 |
| --- | --- |
| CDP collector | 在选定的小程序运行时 target 上发送 `Network.enable`，并订阅网络事件。 |
| CDP collector | 按 `requestId` 缓存一条请求的 request/response 元数据；完成后拉取可用的请求体和响应体。 |
| `wechat_inspector` | 增加 `action="network"`，复用 `duration`、`max_logs`、`cdp_port` 和 `detail_level` 参数。 |
| 文档/Skill | 补充 `network` action、返回结构、隐私限制和排查流程。 |

不改动 `wechat_navigate` 的返回结构；后续如有需要，可单独设计“跳转期间网络瀑布”能力。

## CDP 协议流程

1. 按当前 `cdp` action 的 target 过滤规则，连接小程序运行时 target，排除 IDE 壳页和
   `devtools://` target。
2. 发送 `Network.enable`。首版不传缓存、buffer 大小等可选参数，避免改变 DevTools 的默认行为。
3. 在 `duration` 窗口内处理下列事件：

   | 事件 | 记录内容 |
   | --- | --- |
   | `Network.requestWillBeSent` | `requestId`、时间、URL、method、headers、`postData`、`type`、initiator。 |
   | `Network.responseReceived` | 状态码、statusText、response headers、MIME type、协议、远端地址、缓存标记。 |
   | `Network.loadingFinished` | 结束时间、encodedDataLength；随后调用 `Network.getRequestPostData` 与 `Network.getResponseBody`。 |
   | `Network.loadingFailed` | `errorText`、`canceled`、`blockedReason`，作为失败请求返回。 |

4. `Network.getRequestPostData` 或 `Network.getResponseBody` 失败时保留已采集元数据，并在该请求
   的 `body_error` 中说明原因；单条 body 失败不能导致整个采集失败。
5. 采集结束时移除本次事件监听、清理按 `requestId` 的临时缓存，并按 `max_logs` 截断结果。

`requestWillBeSentExtraInfo` 和 `responseReceivedExtraInfo` 暂不作为首版依赖：不同 CDP target
对这些事件的支持可能不同。收到时可补充 headers，但未收到不影响基础请求/响应观测。

## MCP 接口

```text
wechat_inspector(
  action="network",
  duration=10,
  detail_level="concise",
  max_logs=50,
  cdp_port=9222
)
```

参数沿用现有 `wechat_inspector` 定义：

- `duration`：采集窗口，范围 1～120 秒；
- `max_logs`：最多返回的请求数，超出时 `truncated=true`；
- `cdp_port`：必须与 `wechat_ide(action="open")` 使用的端口一致；
- `detail_level`：
  - `concise`：请求 URL（脱敏后）、method、query 参数名、状态码、MIME type、时长、body 摘要；
  - `full`：额外返回请求/响应 headers、请求体及响应体（均受下方脱敏和大小限制）。

## 建议返回结构

```json
{
  "success": true,
  "data": {
    "summary": {
      "total": 2,
      "succeeded": 1,
      "failed": 1,
      "truncated": false
    },
    "requests": [
      {
        "request_id": "1234.5",
        "url": "https://api.example.com/orders?page=1",
        "method": "POST",
        "query": {"page": "1"},
        "request_headers": {"content-type": "application/json"},
        "request_body": "{\"sku\":\"...\"}",
        "status": 200,
        "response_headers": {"content-type": "application/json"},
        "response_body": "{\"items\":[]}",
        "mime_type": "application/json",
        "duration_ms": 142,
        "encoded_data_length": 381
      }
    ]
  },
  "message": "采集 10 秒，发现 2 个请求（1 成功，1 失败）。"
}
```

`concise` 模式省略完整 headers 与 body；若 body 因协议限制、重定向或资源已释放而无法读取，
对应字段为 `null`，并返回 `body_error`。

## 数据安全与边界

- 返回前对 URL query、headers 和 JSON/form body 中名称匹配
  `authorization`、`cookie`、`token`、`secret`、`password`、`openid`、`session` 的字段值做掩码；
  header 名不区分大小写。
- 每个请求体和响应体限制为 64 KiB，超过时截断并标记 `body_truncated=true`。二进制、图片、
  音视频等非文本 MIME type 不读取 body，只返回长度和 MIME type。
- 不在 daemon 日志、异常消息或持久化缓存中写入原始 request/response body。
- 只采集调用期间新发生的请求；不会回放 Network 历史缓冲，避免把无关会话数据返回给调用方。

## 验收

1. 以 `wechat_ide(action="open", cdp_enabled=true)` 启动目标项目，并确认 CDP 端口可连接。
2. 调用 `wechat_inspector(action="network", detail_level="full")`，在采集窗口内触发一个 JSON
   GET 和一个 JSON POST。
3. 返回结果包含两条请求的 method、脱敏后的 URL/query、请求参数、状态码、响应参数与耗时。
4. 触发一个失败请求，结果包含 `failed` 计数和 `error_text`，且不影响其他请求。
5. 触发含 `Authorization`/`Cookie`/`token` 的请求，确认原始敏感值不出现在返回值或 daemon 日志中。
6. 触发大于 64 KiB 的文本响应和图片响应，确认前者截断标记正确、后者不返回 body。

## 非目标与后续

首版不提供 HAR 导出、按 URL 过滤、缓存禁用、请求拦截/改写、响应重放或跨调用持久化。上述功能
会扩大权限、状态管理和隐私风险，应在基础观测稳定后单独设计。
