"""LLM providers (OpenAI-compatible chat API)."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)


class ChatProvider(Protocol):
    async def complete(self, system: str, user: str) -> str: ...

    async def complete_vision(
        self, system: str, user: str, image_data_url: str
    ) -> str: ...


class OpenAICompatibleProvider:
    """Works with OpenAI, OpenRouter, local LM Studio, etc."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 25.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def complete(self, system: str, user: str) -> str:
        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("empty AI response")
        return str(choices[0].get("message", {}).get("content", ""))

    async def complete_vision(self, system: str, user: str, image_data_url: str) -> str:
        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                },
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("empty AI vision response")
        return str(choices[0].get("message", {}).get("content", ""))


def parse_json_response(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        raise
