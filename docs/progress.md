# Progress（日更 / 实时）

> 目标：Web AI 伴侣（聊天）

## 2025-12-29

### 已完成
- 跑通：HTML/JS/CSS + Flask HTTP + WebSocket（基础聊天）
- 增加：可配置 AI Provider（placeholder / Deepseek）与会话内存上下文
- 修复：Windows 直接运行脚本的导入问题、Python 3.8 兼容性问题
- 增加：SQLite 持久化存储层（sessions/messages/system_prompt）与 `/api/session`
- 增加：Deepseek（OpenAI 兼容）流式解析（SSE）与前端增量渲染协议（assistant_delta）
- 增加：前端最小“角色设定/系统提示词”输入，并随请求发送
- 调整：Deepseek 默认地址对齐 `/chat/completions`，并在聊天里显示失败原因（401/404 等）
- 修复：WS 端口占用时自动换端口（从 `WS_PORT` 起递增尝试），避免启动失败

### 进行中
- WS 流式输出联调：切换为 asyncio WebSocket server（`WS_PORT`），前端通过 `/api/config` 自动连接

### 下一步
- Deepseek 流式模型接入（OpenAI 兼容 stream=true）
- 前端：显示历史消息加载（从后端拉取/或首次握手下发）
