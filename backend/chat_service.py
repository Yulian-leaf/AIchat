from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from backend.ai_client import AIClientError, BaseAIClient
from backend.storage_sqlite import SQLiteStore
from backend.utils import new_session_id


Message = Dict[str, str]


@dataclass
class ChatResult:
    session_id: str
    reply: str


class ChatService:
    def __init__(
        self,
        *,
        ai_client: BaseAIClient,
        store: SQLiteStore,
        default_system_prompt: str,
        max_history_messages: int = 20,
    ):
        self._ai_client = ai_client
        self._store = store
        self._default_system_prompt = (default_system_prompt or "").strip()
        self._max_history_messages = max(2, int(max_history_messages))

    def new_session_id(self) -> str:
        return new_session_id()

    def set_system_prompt(self, session_id: str, system_prompt: str) -> None:
        self._store.set_system_prompt(session_id, system_prompt)

    def append_assistant_message(self, session_id: str, content: str) -> None:
        self._store.append_message(session_id, "assistant", content)

    def get_effective_system_prompt(self, session_id: str) -> str:
        stored = self._store.get_system_prompt(session_id)
        if stored is None:
            return self._default_system_prompt
        stored = (stored or "").strip()
        return stored if stored else self._default_system_prompt

    def _build_messages(self, session_id: str) -> List[Message]:
        history = self._store.get_recent_messages(session_id, self._max_history_messages)
        messages: List[Message] = []
        system_prompt = self.get_effective_system_prompt(session_id)
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for m in history:
            messages.append({"role": m.role, "content": m.content})
        return messages

    def handle_user_message(self, *, session_id: str, content: str, system_prompt: Optional[str] = None) -> ChatResult:
        content = (content or "").strip()
        if not session_id:
            session_id = self.new_session_id()

        self._store.get_or_create_session(session_id)
        if system_prompt is not None:
            self._store.set_system_prompt(session_id, system_prompt)

        self._store.append_message(session_id, "user", content)
        messages = self._build_messages(session_id)

        try:
            reply = self._ai_client.generate(messages)
        except AIClientError as e:
            reason = str(e) or "unknown"
            reply = f"（AI 服务暂不可用：{reason}）" + ("你说：" + content if content else "")

        self._store.append_message(session_id, "assistant", reply)
        return ChatResult(session_id=session_id, reply=reply)

    def stream_user_message(
        self,
        *,
        session_id: str,
        content: str,
        system_prompt: Optional[str] = None,
    ) -> Iterable[str]:
        """Yield assistant reply chunks; caller can accumulate to final reply."""
        content = (content or "").strip()
        if not session_id:
            session_id = self.new_session_id()

        self._store.get_or_create_session(session_id)
        if system_prompt is not None:
            self._store.set_system_prompt(session_id, system_prompt)

        self._store.append_message(session_id, "user", content)
        messages = self._build_messages(session_id)

        try:
            for chunk in self._ai_client.stream_generate(messages):
                if chunk:
                    yield str(chunk)
        except AIClientError as e:
            reason = str(e) or "unknown"
            fallback = f"（AI 服务暂不可用：{reason}）" + ("你说：" + content if content else "")
            for ch in fallback:
                yield ch
        except Exception:
            # 流式失败时给一个可见的兜底
            fallback = "（AI 服务暂不可用）" + ("你说：" + content if content else "")
            for ch in fallback:
                yield ch
