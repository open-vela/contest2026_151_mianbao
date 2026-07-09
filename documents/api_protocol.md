# AI模拟面试官 — 端云接口协议

> 维护人：B同学、C同学
> 版本：v0.1

## 接口定义

### 端侧 -> 云端
```json
POST /api/interview
{
  "session_id": "uuid-xxxx",
  "audio": "base64编码的WAV音频",
  "role": "产品经理",
  "state": "recording_finished"
}
```

### 云端 -> 端侧
```json
{
  "type": "question",
  "text": "你的回答逻辑清晰...",
  "tts_audio": "base64编码的PCM音频",
  "session_id": "uuid-xxxx",
  "next_action": "continue"
}
```

### 健康检查
```
GET /api/health
```

## 状态流转
- 正常面试：多轮交互，每轮请求->响应
- 错误重试：最多3次
- 超时：单次回答最多3分钟
