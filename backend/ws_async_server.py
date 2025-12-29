from __future__ import annotations

import asyncio
import json
import threading
from typing import Dict, Optional

import websockets

from backend.chat_service import ChatService
from backend.config import Settings


def _run_server(chat_service: ChatService, settings: Settings, state: Dict[str, object], ready: threading.Event) -> None:
    async def handler(ws):
        session_id = chat_service.new_session_id()
        await ws.send(json.dumps({"type": "session", "session_id": session_id}, ensure_ascii=False))

        async for raw in ws:
            try:
                data = json.loads(raw)
            except Exception:
                await ws.send(
                    json.dumps({"type": "error", "message": "invalid_json", "session_id": session_id}, ensure_ascii=False)
                )
                continue

            if data.get("type") != "user_message":
                await ws.send(
                    json.dumps({"type": "error", "message": "unknown_type", "session_id": session_id}, ensure_ascii=False)
                )
                continue

            content = str(data.get("content", ""))
            provided = data.get("session_id")
            if isinstance(provided, str) and provided.strip():
                session_id = provided.strip()

            system_prompt = data.get("system_prompt")
            if system_prompt is not None:
                system_prompt = str(system_prompt)

            stream = bool(data.get("stream", True))
            if not stream:
                result = chat_service.handle_user_message(session_id=session_id, content=content, system_prompt=system_prompt)
                session_id = result.session_id
                await ws.send(
                    json.dumps(
                        {"type": "assistant_message", "content": result.reply, "session_id": session_id},
                        ensure_ascii=False,
                    )
                )
                continue

            full = ""
            for chunk in chat_service.stream_user_message(session_id=session_id, content=content, system_prompt=system_prompt):
                full += chunk
                await ws.send(
                    json.dumps(
                        {"type": "assistant_delta", "content": chunk, "session_id": session_id},
                        ensure_ascii=False,
                    )
                )

            # stream_user_message 不负责落 assistant，最终在这里落库
            chat_service.append_assistant_message(session_id, full)
            await ws.send(
                json.dumps(
                    {"type": "assistant_message", "content": full, "session_id": session_id},
                    ensure_ascii=False,
                )
            )

    async def main() -> None:
        last_error: Optional[BaseException] = None
        bound_port: Optional[int] = None

        # 从 WS_PORT 开始，自动尝试下一个空闲端口，避免 Windows 上端口占用导致启动失败
        for port in range(int(settings.ws_port), int(settings.ws_port) + 20):
            try:
                await websockets.serve(handler, settings.host, port)
                bound_port = port
                settings.ws_port = port
                break
            except OSError as e:
                last_error = e
                continue

        if bound_port is None:
            state["error"] = repr(last_error) if last_error is not None else "failed_to_bind"
            ready.set()
            return

        state["port"] = bound_port
        ready.set()
        await asyncio.Future()

    asyncio.run(main())


def start_ws_server_in_thread(chat_service: ChatService, settings: Settings) -> None:
    state: Dict[str, object] = {"port": None, "error": None}
    ready = threading.Event()
    t = threading.Thread(target=_run_server, args=(chat_service, settings, state, ready), daemon=True)
    t.start()

    # 等待 WS server 绑定端口，确保 /api/config 返回的是实际可用端口
    ready.wait(timeout=2.0)
