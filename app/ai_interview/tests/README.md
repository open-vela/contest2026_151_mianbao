# 端侧网络层单元测试

`cloud_parse_response()` 的 PC 端单测。**不需要开发板、不需要云端服务、不需要 API key。**

## 为什么要单独测这个函数

云端在**缺 `MIMO_API_KEY`** 时不会报错，而是返回 **HTTP 200**，并且响应里
`type`、`next_action` 都是正常值，只有 `tts_audio` 是空字符串：

```json
{
  "type": "question",
  "text": "抱歉，生成问题失败，请重试。",
  "tts_audio": "",
  "next_action": "continue"
}
```

端侧若只看 HTTP 状态码或 `type`/`next_action`，会把失败当成功，表现为
"状态灯正常、但没有声音" —— 演示时最难排查的一类故障。

所以"空的 `tts_audio` 判为失败"是**唯一可靠的检测手段**，其判定逻辑单点收敛在
`cloud_parse_response()` 里。这个函数是纯逻辑（JSON 解析 + base64 解码），
不碰硬件、不碰网络，因此可以在 PC 上做到完全覆盖。

## 运行

```bash
./run.sh                    # 自动向上查找 openvela 工作区
./run.sh /path/to/workspace # 或显式指定（含 apps/ 、nuttx/ 、external/ 的那一层）
```

## 覆盖的用例

| 用例 | 素材 | 期望 |
|------|------|------|
| 正常响应 | `fixtures/sample_ok.json` | `CLOUD_OK`，解出完整可播 WAV（校验 RIFF/WAVE 魔数） |
| **空 `tts_audio`** | `fixtures/sample_empty_tts.json` | `CLOUD_ERR_EMPTY_TTS` |
| 服务端 error 结构 | `fixtures/sample_error.json` | `CLOUD_ERR_EMPTY_TTS` |
| 非 JSON（网关 HTML 错误页） | `fixtures/sample_html.json` | `CLOUD_ERR_JSON` |
| 边界入参 | — | 空 body / NULL / 重复 free 均不崩 |

其中 `sample_empty_tts.json` 是**从本地 Flask 服务实测抓取的真实响应**
（不设 `MIMO_API_KEY`），不是手工构造的。

## 素材说明

`fixtures/sample_ok.json` 里的 WAV 是从 `cloud/test_tts_output.wav` 截取的
1 秒片段（24kHz / 单声道 / 16bit），结构与云端 TTS 实际返回的一致。
测试只校验容器格式与解码结果，不校验音频内容。

## 编译方式

测试直接把 `../network_client.c` 编进来，配合树里的 `cJSON.c` 与
`mbedtls` 的 `base64.c` / `constant_time.c`，不使用任何桩函数。
只被 HTTP 函数引用的 curl 符号通过 `--gc-sections` 丢弃，因此在 PC 上
无需链接 libcurl。
