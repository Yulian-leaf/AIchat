from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

try:
    from flask_sock import Sock
except ModuleNotFoundError:  # pragma: no cover
    Sock = None

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover
    def load_dotenv(*_args, **_kwargs):
        return False

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

# Prefer `.env`; fallback to `.env.example` to reduce beginner friction.
if callable(load_dotenv):
    loaded = load_dotenv(BASE_DIR / ".env")
    if not loaded:
        load_dotenv(BASE_DIR / ".env.example")

from backend.ai_client import build_client
from backend.chat_service import ChatService
from backend.config import Settings
from backend.storage_sqlite import SQLiteStore
from backend.ws_async_server import start_ws_server_in_thread

settings = Settings()

store = SQLiteStore(settings.db_path)

ai_client = build_client(
    settings.ai_provider,
    base_url=settings.ai_base_url,
    api_key=settings.deepseek_api_key,
    model=settings.ai_model,
    temperature=settings.ai_temperature,
    timeout_seconds=settings.ai_timeout_seconds,
)

chat_service = ChatService(
    ai_client=ai_client,
    store=store,
    default_system_prompt=settings.system_prompt,
    max_history_messages=settings.max_history_messages,
)

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path="",
)

sock = Sock(app) if Sock is not None else None


def _normalize_session_id(maybe_session_id: Any) -> str:
    if isinstance(maybe_session_id, str) and maybe_session_id.strip():
        return maybe_session_id.strip()
    return ""


@app.get("/")
def index():
    return send_from_directory(str(FRONTEND_DIR), "index.html")


@app.post("/api/chat")
def api_chat():
    payload = request.get_json(silent=True) or {}
    message = payload.get("message", "")
    session_id = _normalize_session_id(payload.get("session_id"))
    system_prompt = payload.get("system_prompt")

    if system_prompt is not None:
        system_prompt = str(system_prompt)

    result = chat_service.handle_user_message(session_id=session_id, content=str(message), system_prompt=system_prompt)
    return jsonify({"session_id": result.session_id, "reply": result.reply})


@app.get("/api/config")
def api_config():
    return jsonify({"ws_port": settings.ws_port, "ws_path": "/ws"})


@app.get("/api/health")
def api_health():
    return jsonify(
        {
            "ai_provider": settings.ai_provider,
            "ai_base_url": settings.ai_base_url,
            "ai_model": settings.ai_model,
            "deepseek_api_key_present": bool(settings.deepseek_api_key),
            "ws_port": settings.ws_port,
            "db_path": settings.db_path,
        }
    )


@app.get("/api/session")
def api_session():
    session_id = _normalize_session_id(request.args.get("session_id"))
    if not session_id:
        return jsonify({"error": "missing_session_id"}), 400
    data = store.export_session(session_id, settings.max_history_messages)
    # 若 session 没设置过 prompt，返回默认 prompt 便于前端展示
    if not data.get("system_prompt"):
        data["system_prompt"] = settings.system_prompt
    return jsonify(data)


if sock is not None:

    @sock.route("/ws")
    def ws_chat(ws):
        session_id = chat_service.new_session_id()
        ws.send(json.dumps({"type": "session", "session_id": session_id}, ensure_ascii=False))

        while True:
            raw = ws.receive()
            if raw is None:
                break

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                ws.send(
                    json.dumps(
                        {"type": "error", "message": "invalid_json", "session_id": session_id},
                        ensure_ascii=False,
                    )
                )
                continue

            msg_type = data.get("type")
            if msg_type != "user_message":
                ws.send(
                    json.dumps(
                        {
                            "type": "error",
                            "message": "unknown_type",
                            "session_id": session_id,
                        },
                        ensure_ascii=False,
                    )
                )
                continue

            content = str(data.get("content", ""))
            session_id = _normalize_session_id(data.get("session_id")) or session_id
            system_prompt = data.get("system_prompt")
            if system_prompt is not None:
                system_prompt = str(system_prompt)

            stream = bool(data.get("stream", True))

            if stream:
                full = ""
                for chunk in chat_service.stream_user_message(
                    session_id=session_id,
                    content=content,
                    system_prompt=system_prompt,
                ):
                    full += chunk
                    ws.send(
                        json.dumps(
                            {
                                "type": "assistant_delta",
                                "content": chunk,
                                "session_id": session_id,
                            },
                            ensure_ascii=False,
                        )
                    )

                # 记录最终 assistant 消息
                store.append_message(session_id, "assistant", full)
                ws.send(
                    json.dumps(
                        {
                            "type": "assistant_message",
                            "content": full,
                            "session_id": session_id,
                        },
                        ensure_ascii=False,
                    )
                )
                continue

            result = chat_service.handle_user_message(session_id=session_id, content=content, system_prompt=system_prompt)
            session_id = result.session_id
            ws.send(
                json.dumps(
                    {
                        "type": "assistant_message",
                        "content": result.reply,
                        "session_id": result.session_id,
                    },
                    ensure_ascii=False,
                )
            )


if __name__ == "__main__":
    # 在同一进程启动一个 asyncio WebSocket server（更稳定，尤其是 Windows）
    start_ws_server_in_thread(chat_service, settings)
    app.run(host=settings.host, port=settings.port, debug=True, use_reloader=False)
