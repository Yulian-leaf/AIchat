from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, List, Mapping

import requests


Message = Mapping[str, str]


class AIClientError(RuntimeError):
    pass


class BaseAIClient:
    def generate(self, messages: List[Message]) -> str:
        raise NotImplementedError

    def stream_generate(self, messages: List[Message]) -> Iterable[str]:
        raise NotImplementedError


@dataclass
class PlaceholderClient(BaseAIClient):
    def generate(self, messages: List[Message]) -> str:
        last_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = msg.get("content", "")
                break
        last_user = (last_user or "").strip()
        if not last_user:
            return "你还没有输入消息。"
        return (
            "（当前未配置模型）我收到了你的消息："
            f"{last_user}\n\n"
            "要让 AI 真正回答：请在 `.env` 里设置 `AI_PROVIDER=deepseek` 并填入 `DEEPSEEK_API_KEY`，然后重启后端。"
        )

    def stream_generate(self, messages: List[Message]) -> Iterable[str]:
        text = self.generate(messages)
        # 简单按字符流式输出，前端能立刻看到“流式效果”
        for ch in text:
            yield ch


@dataclass
class DeepseekClient(BaseAIClient):
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.7
    timeout_seconds: int = 30

    def generate(self, messages: List[Message]) -> str:
        if not self.api_key:
            raise AIClientError("missing_api_key")

        url = self.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": list(messages),
            "temperature": self.temperature,
            "stream": False,
        }

        try:
            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=self.timeout_seconds)
        except requests.RequestException as e:
            raise AIClientError("network_error") from e

        if resp.status_code >= 400:
            raise AIClientError(f"http_{resp.status_code}")

        try:
            data = resp.json()
        except ValueError as e:
            raise AIClientError("invalid_json") from e

        try:
            return (data["choices"][0]["message"]["content"] or "").strip()
        except Exception as e:
            raise AIClientError("bad_response_shape") from e

    def stream_generate(self, messages: List[Message]) -> Iterable[str]:
        if not self.api_key:
            raise AIClientError("missing_api_key")

        url = self.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": list(messages),
            "temperature": self.temperature,
            "stream": True,
        }

        try:
            resp = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=self.timeout_seconds,
                stream=True,
            )
        except requests.RequestException as e:
            raise AIClientError("network_error") from e

        if resp.status_code >= 400:
            raise AIClientError(f"http_{resp.status_code}")

        # OpenAI compatible: Server-Sent Events
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if isinstance(line, bytes):
                try:
                    line = line.decode("utf-8", errors="ignore")
                except Exception:
                    continue

            line = line.strip()
            if not line.startswith("data:"):
                continue

            data_part = line[len("data:") :].strip()
            if data_part == "[DONE]":
                break

            try:
                data = json.loads(data_part)
            except ValueError:
                continue

            try:
                choice0 = data.get("choices", [{}])[0]
                delta = choice0.get("delta", {}) or {}
                content = delta.get("content")
                if content:
                    yield str(content)
            except Exception:
                continue


def build_client(
    provider: str,
    *,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float,
    timeout_seconds: int,
) -> BaseAIClient:
    provider = (provider or "placeholder").strip().lower()
    if provider in {"deepseek", "deepseek_api"}:
        return DeepseekClient(
            base_url=base_url,
            api_key=api_key,
            model=model,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )
    return PlaceholderClient()
