"""OpenClaw Agent core: LLM + tool-calling loop.

Ported from v0.7.5 server.py (ThreadedHTTPServer) to async FastAPI.
Key changes:
  - Async LLM calls via LLMProvider (httpx)
  - Redis-backed sessions
  - Internal tool execution (no localhost HTTP)
  - Qwen-style tool parsing preserved for compatibility
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator
from typing import Any

from ..llm.provider import get_llm_provider, strip_think_tags
from .session import Session, get_session_store
from .tools import TOOL_DEFINITIONS, execute_tool

MAX_TOOL_ROUNDS = 3

# Qwen-style tool call parser: <function=name><parameter=key>value</parameter></function>
_QWEN_FUNC_RE = re.compile(
    r"<function=(\w+)>(.*?)</function>", re.DOTALL
)
_QWEN_PARAM_RE = re.compile(
    r"<parameter=(\w+)>(.*?)</parameter>", re.DOTALL
)

BASE_SYSTEM_PROMPT = """你是 AI Workflow Terminal 的智能助手 (OpenClaw)。
你可以通过工具调用来帮助用户完成各种任务。

工具使用原则:
1. 简单知识问答 → 直接回答
2. 需要系统操作 → 调用相应工具
3. 多步骤任务 → 连续调用多个工具
4. 用户明确要求自动化 → 创建工作流

始终用中文回答，除非用户使用其他语言。回答要简洁有用。"""


def _parse_qwen_tool_calls(text: str) -> list[dict]:
    """Parse Qwen-style text tool calls into standardized format."""
    calls = []
    for match in _QWEN_FUNC_RE.finditer(text):
        func_name = match.group(1)
        params_text = match.group(2)
        params = {}
        for pm in _QWEN_PARAM_RE.finditer(params_text):
            params[pm.group(1)] = pm.group(2).strip()
        calls.append({"name": func_name, "arguments": params})
    return calls


def _extract_tool_calls(response_data: dict) -> list[dict]:
    """Extract tool calls from LLM response (OpenAI or Qwen format)."""
    choices = response_data.get("choices", [])
    if not choices:
        return []

    message = choices[0].get("message", {})

    # OpenAI format: tool_calls array
    tool_calls = message.get("tool_calls")
    if tool_calls:
        result = []
        for tc in tool_calls:
            func = tc.get("function", {})
            args = func.get("arguments", "{}")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            result.append({
                "id": tc.get("id", ""),
                "name": func.get("name", ""),
                "arguments": args,
            })
        return result

    # Qwen text format fallback
    content = message.get("content", "")
    if "<function=" in content:
        return _parse_qwen_tool_calls(content)

    return []


async def run_agent(
    message: str,
    session_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Non-streaming agent execution. Returns final response."""
    store = get_session_store()
    llm = get_llm_provider()

    session = await store.get_or_create(session_id, BASE_SYSTEM_PROMPT)
    session.add_message("user", message)

    tools = TOOL_DEFINITIONS
    final_content = ""

    for _round in range(MAX_TOOL_ROUNDS):
        resp = await llm.chat(
            session.messages,
            provider=provider,
            model=model,
            tools=tools,
        )

        tool_calls = _extract_tool_calls(resp)
        content = resp["choices"][0]["message"].get("content", "")

        if not tool_calls:
            final_content = content
            break

        # Add assistant message with tool calls
        session.add_message("assistant", content or "")

        # Execute each tool
        for tc in tool_calls:
            result = await execute_tool(tc["name"], tc["arguments"], user_id=user_id)
            session.add_message("tool", result, name=tc["name"])
    else:
        # Max rounds reached, use last content
        final_content = content

    session.add_message("assistant", final_content)
    await store.save(session)

    return {
        "response": final_content,
        "session_id": session.session_id,
    }


async def stream_agent(
    message: str,
    session_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    user_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Streaming agent execution. Yields SSE data lines.

    For tool-calling rounds, executes tools silently then streams final response.
    """
    store = get_session_store()
    llm = get_llm_provider()

    session = await store.get_or_create(session_id, BASE_SYSTEM_PROMPT)
    session.add_message("user", message)

    tools = TOOL_DEFINITIONS

    # Tool-calling rounds (non-streaming for tool execution)
    for _round in range(MAX_TOOL_ROUNDS - 1):
        resp = await llm.chat(
            session.messages,
            provider=provider,
            model=model,
            tools=tools,
        )

        tool_calls = _extract_tool_calls(resp)
        content = resp["choices"][0]["message"].get("content", "")

        if not tool_calls:
            # No tools needed, re-stream from scratch
            # Remove the non-streaming attempt from session and stream instead
            break

        session.add_message("assistant", content or "")
        for tc in tool_calls:
            result = await execute_tool(tc["name"], tc["arguments"], user_id=user_id)
            session.add_message("tool", result, name=tc["name"])
    else:
        # All rounds used tools, stream the final response
        pass

    # Final streaming response
    full_content = ""
    async for line in llm.chat_stream(
        session.messages,
        provider=provider,
        model=model,
    ):
        yield line
        # Accumulate content for session storage
        if line.startswith("data: ") and line.strip() != "data: [DONE]":
            try:
                chunk = json.loads(line[6:])
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                c = delta.get("content", "")
                if c:
                    full_content += c
            except (json.JSONDecodeError, IndexError, KeyError):
                pass

    # Save accumulated response to session
    if full_content:
        clean = strip_think_tags(full_content)
        session.add_message("assistant", clean)
    await store.save(session)
