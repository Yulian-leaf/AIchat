# AI 伴侣（基础聊天）MVP
这个项目是一个“网页端 AI 伴侣聊天”MVP：前端用纯 HTML/CSS/JS 提供最小聊天界面与系统提示词输入，后端用 Python Flask 同时托管页面并提供 HTTP 接口（/api/chat、/api/session、/api/config、/api/health）以及 WebSocket 实时通道，默认优先走 WS 的增量流式协议（assistant_delta）实现逐字输出、失败则回退到 HTTP；服务端支持可切换的 AI Provider（占位回显或 Deepseek/OpenAI 兼容接口）、会话上下文记忆与 SQLite 持久化存储（sessions/messages/system_prompt），并对 Windows 环境做了兼容与端口占用自动换端口处理，从而跑通“打开网页—发消息—流式回复—历史可回放”的闭环。
目标：用最小技术栈跑通“网页聊天”闭环。

- 前端：纯 HTML + CSS + JS
- 后端：Python Flask（HTTP + WebSocket）
- AI 回复：Deepseek api

## 1) 创建 conda 环境

在项目根目录执行：

```powershell
conda env create -f environment.yml
conda activate ai-companion-chat
```

如果你已经创建过环境（后续依赖有变更），可执行：

```powershell
conda env update -f environment.yml
conda activate ai-companion-chat
```

如果你想更新到“当前已有环境”（例如你的环境名是 `ne`），可用：

```powershell
conda env update -n ne -f environment.yml
conda activate ne
```

或者直接在当前环境用 pip 安装依赖：

```powershell
python -m pip install -r requirements.txt
```

## 2) 启动后端（同时托管前端页面）

```powershell
python -m backend.app
```

（也支持：`python backend/app.py`）

启动后访问：

- http://127.0.0.1:5000/

## 3) MVP 功能说明

- 发送消息后，服务端返回一个占位回复（回显）。
- 聊天优先走 WebSocket（支持流式增量 `assistant_delta`），若不可用则回退到 HTTP `/api/chat`。

说明：当前 WebSocket 默认由同一进程内的 asyncio server 提供（端口 `WS_PORT=8765`），前端会先请求 `/api/config` 获取端口。

## 4) 接入 Deepseek（可选）

1) 复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

2) 编辑 `.env`：

- 设置：`AI_PROVIDER=deepseek`
- 填入：`DEEPSEEK_API_KEY=...`

建议同时确认：

- `AI_MODEL=deepseek-chat`

重启后端后生效。
