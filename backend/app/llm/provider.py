"""Unified LLM provider abstraction supporting multiple backends."""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from ..config import settings

# Strip Qwen <think>...</think> tags from responses
_THINK_COMPLETE = re.compile(r"<think>[\s\S]*?</think>\s*")
_THINK_ORPHAN = re.compile(r"<think>[\s\S]*")


def strip_think_tags(text: str) -> str:
    result = _THINK_COMPLETE.sub("", text)
    result = _THINK_ORPHAN.sub("", result)
    return result.strip()


class ProviderConfig:
    """Configuration for a single LLM provider."""

    def __init__(self, name: str, base_url: str, api_key: str, model: str):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model


class LLMProvider:
    """Unified interface for calling LLMs via OpenAI-compatible API."""

    def __init__(self):
        self._providers: dict[str, ProviderConfig] = {}
        self._register_providers()
        self._client = httpx.AsyncClient(timeout=120.0)

    def _register_providers(self):
        if settings.qwen_api_key:
            self._providers["qwen-cloud"] = ProviderConfig(
                "qwen-cloud", settings.qwen_base_url, settings.qwen_api_key, settings.qwen_model
            )
        if settings.openai_api_key:
            self._providers["openai"] = ProviderConfig(
                "openai", settings.openai_base_url, settings.openai_api_key, settings.openai_model
            )
        if settings.claude_api_key:
            self._providers["claude"] = ProviderConfig(
                "claude", settings.openai_base_url, settings.claude_api_key, settings.claude_model
            )
        if settings.vllm_base_url:
            self._providers["vllm"] = ProviderConfig(
                "vllm", settings.vllm_base_url, "", settings.vllm_model
            )

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

    def _resolve(self, provider: str | None) -> ProviderConfig:
        name = provider or settings.llm_default_provider
        if name not in self._providers:
            available = ", ".join(self._providers.keys()) or "none configured"
            raise ValueError(f"Provider '{name}' not available. Available: {available}")
        return self._providers[name]

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: list[dict] | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> dict:
        """Non-streaming chat completion. Returns the full response dict."""
        cfg = self._resolve(provider)
        body: dict[str, Any] = {
            "model": model or cfg.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            body["tools"] = tools
        if extra_body:
            body.update(extra_body)

        headers = {"Content-Type": "application/json"}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"

        resp = await self._client.post(
            f"{cfg.base_url}/chat/completions", json=body, headers=headers
        )
        resp.raise_for_status()
        data = resp.json()

        # Strip think tags from content
        for choice in data.get("choices", []):
            msg = choice.get("message", {})
            content = msg.get("content")
            if content:
                msg["content"] = strip_think_tags(content)

        return data

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: list[dict] | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Streaming chat completion. Yields SSE data lines."""
        cfg = self._resolve(provider)
        body: dict[str, Any] = {
            "model": model or cfg.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            body["tools"] = tools
        if extra_body:
            body.update(extra_body)

        headers = {"Content-Type": "application/json"}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"

        async with self._client.stream(
            "POST", f"{cfg.base_url}/chat/completions", json=body, headers=headers
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    yield line + "\n\n"

        yield "data: [DONE]\n\n"

    async def close(self):
        await self._client.aclose()


# Singleton
_instance: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    global _instance
    if _instance is None:
        _instance = LLMProvider()
    return _instance
