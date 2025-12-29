from __future__ import annotations

from dataclasses import dataclass, field
import os


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass
class Settings:
    # 注意：不要用“类属性读取 os.getenv”——那会在 import 时就固定住，导致 .env 后加载无效。
    host: str = field(default_factory=lambda: os.getenv("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _get_int("PORT", 5000))
    ws_port: int = field(default_factory=lambda: _get_int("WS_PORT", 8765))

    db_path: str = field(
        default_factory=lambda: os.getenv("DB_PATH", os.path.join("backend", "data", "chat.db")).strip()
    )

    ai_provider: str = field(default_factory=lambda: os.getenv("AI_PROVIDER", "placeholder").strip().lower())

    ai_base_url: str = field(default_factory=lambda: os.getenv("AI_BASE_URL", "https://api.deepseek.com").strip())
    ai_model: str = field(default_factory=lambda: os.getenv("AI_MODEL", "deepseek-chat").strip())
    ai_temperature: float = field(default_factory=lambda: _get_float("AI_TEMPERATURE", 0.7))
    ai_timeout_seconds: int = field(default_factory=lambda: _get_int("AI_TIMEOUT_SECONDS", 30))

    deepseek_api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", "").strip())

    system_prompt: str = field(
        default_factory=lambda: os.getenv(
            "SYSTEM_PROMPT",
            "你是一个友好、可靠的 AI 伴侣。回答要简洁、清晰，必要时给出可执行步骤。",
        ).strip()
    )

    max_history_messages: int = field(default_factory=lambda: _get_int("MAX_HISTORY_MESSAGES", 20))
