"""Engine registry: tracks capabilities, health, and routes for all service modules.

In v0.7.5 this was a YAML config + HTTP proxy to 26+ separate processes.
In v0.8 cloud mode, engines are internal modules registered at startup.
The registry still provides:
  - Capability discovery (for workflow validation)
  - Health status tracking
  - Tool routing (OpenClaw plugin looks up engines here)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EngineAction:
    name: str
    method: str = "POST"
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    returns: dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineDefinition:
    engine_id: str
    name: str
    category: str  # ai, data, system, workflow, iot, automation
    description: str = ""
    actions: list[EngineAction] = field(default_factory=list)
    healthy: bool = True
    last_check: float = 0.0


class EngineRegistry:
    """Central registry for all engine modules."""

    def __init__(self):
        self._engines: dict[str, EngineDefinition] = {}

    def register(self, engine: EngineDefinition):
        self._engines[engine.engine_id] = engine

    def unregister(self, engine_id: str):
        self._engines.pop(engine_id, None)

    def get(self, engine_id: str) -> EngineDefinition | None:
        return self._engines.get(engine_id)

    def list_engines(self) -> list[dict]:
        return [
            {
                "id": e.engine_id,
                "name": e.name,
                "category": e.category,
                "description": e.description,
                "healthy": e.healthy,
                "actions": [a.name for a in e.actions],
            }
            for e in self._engines.values()
        ]

    def get_capabilities(self) -> dict[str, Any]:
        """Return full capability schema for workflow validation."""
        caps = {}
        for e in self._engines.values():
            caps[e.engine_id] = {
                "name": e.name,
                "category": e.category,
                "description": e.description,
                "actions": {
                    a.name: {
                        "method": a.method,
                        "description": a.description,
                        "parameters": a.parameters,
                        "returns": a.returns,
                    }
                    for a in e.actions
                },
            }
        return caps

    def get_health(self) -> dict[str, dict]:
        return {
            e.engine_id: {"healthy": e.healthy, "last_check": e.last_check}
            for e in self._engines.values()
        }

    def set_health(self, engine_id: str, healthy: bool):
        engine = self._engines.get(engine_id)
        if engine:
            engine.healthy = healthy
            engine.last_check = time.time()


# Singleton
_registry: EngineRegistry | None = None


def get_registry() -> EngineRegistry:
    global _registry
    if _registry is None:
        _registry = EngineRegistry()
        _register_builtin_engines(_registry)
    return _registry


def _register_builtin_engines(reg: EngineRegistry):
    """Register all built-in engine modules."""

    # AI engines
    reg.register(EngineDefinition(
        engine_id="llm", name="LLM Chat", category="ai",
        description="Large language model chat completion",
        actions=[
            EngineAction("chat", "POST", "Chat completion",
                         parameters={"messages": {"type": "array"}, "model": {"type": "string"}}),
            EngineAction("stream", "POST", "Streaming chat completion"),
        ],
    ))
    reg.register(EngineDefinition(
        engine_id="tts", name="Text to Speech", category="ai",
        description="Convert text to speech audio",
        actions=[EngineAction("synthesize", "POST", "Synthesize speech",
                              parameters={"text": {"type": "string"}, "language": {"type": "string"}})],
    ))
    reg.register(EngineDefinition(
        engine_id="translate", name="Translation", category="ai",
        description="Multi-language text translation",
        actions=[EngineAction("translate", "POST", "Translate text",
                              parameters={"text": {"type": "string"}, "target_lang": {"type": "string"}})],
    ))

    # Data engines
    reg.register(EngineDefinition(
        engine_id="rag", name="Knowledge Base", category="data",
        description="RAG knowledge base with vector search",
        actions=[
            EngineAction("ingest", "POST", "Ingest document into knowledge base"),
            EngineAction("query", "POST", "Query knowledge base"),
        ],
    ))
    reg.register(EngineDefinition(
        engine_id="memory", name="Conversation Memory", category="data",
        description="Long-term conversation memory with semantic search",
        actions=[
            EngineAction("store", "POST", "Store memory entry"),
            EngineAction("retrieve", "POST", "Retrieve relevant memories"),
            EngineAction("context", "GET", "Get memory context for session"),
        ],
    ))
    reg.register(EngineDefinition(
        engine_id="crawl", name="Web Crawler", category="data",
        description="Web content extraction and RSS feed parsing",
        actions=[EngineAction("crawl", "POST", "Crawl and extract web content")],
    ))
    reg.register(EngineDefinition(
        engine_id="email", name="Email Manager", category="data",
        description="Email inbox management via IMAP/SMTP",
        actions=[
            EngineAction("inbox", "GET", "List inbox emails"),
            EngineAction("send", "POST", "Send email"),
        ],
    ))

    # System engines
    reg.register(EngineDefinition(
        engine_id="system_monitor", name="System Monitor", category="system",
        description="System resource monitoring (CPU, memory, disk)",
        actions=[EngineAction("status", "GET", "Get system status")],
    ))
    reg.register(EngineDefinition(
        engine_id="file_transfer", name="File Transfer", category="system",
        description="File upload and download",
        actions=[
            EngineAction("upload", "POST", "Upload file"),
            EngineAction("download", "GET", "Download file"),
            EngineAction("list", "GET", "List files"),
        ],
    ))

    # Workflow engines
    reg.register(EngineDefinition(
        engine_id="workflow", name="Workflow Engine", category="workflow",
        description="Visual workflow creation and execution (n8n format)",
        actions=[
            EngineAction("create", "POST", "Create workflow"),
            EngineAction("execute", "POST", "Execute workflow"),
            EngineAction("list", "GET", "List workflows"),
        ],
    ))
    reg.register(EngineDefinition(
        engine_id="workflow_store", name="Workflow Store", category="workflow",
        description="Workflow marketplace: browse and install",
        actions=[
            EngineAction("browse", "GET", "Browse available workflows"),
            EngineAction("install", "POST", "Install workflow"),
        ],
    ))
    reg.register(EngineDefinition(
        engine_id="doc_version", name="Document Version Manager", category="data",
        description="Git-backed document version management with AI analysis",
        actions=[
            EngineAction("ingest", "POST", "Ingest document"),
            EngineAction("list_projects", "GET", "List projects"),
            EngineAction("history", "GET", "Get document history"),
            EngineAction("diff", "GET", "Get version diff"),
        ],
    ))

    # IoT / HAL
    reg.register(EngineDefinition(
        engine_id="smart_home", name="Smart Home", category="iot",
        description="Home Assistant integration for device control",
        actions=[
            EngineAction("devices", "GET", "List smart home devices"),
            EngineAction("control", "POST", "Control device"),
        ],
    ))
    reg.register(EngineDefinition(
        engine_id="wol", name="Wake on LAN", category="system",
        description="Remote device wake via magic packet",
        actions=[EngineAction("wake", "POST", "Wake device")],
    ))

    # Task delegation
    reg.register(EngineDefinition(
        engine_id="task_agent", name="Task Agent", category="automation",
        description="Cross-device task delegation with AI assistance",
        actions=[
            EngineAction("create", "POST", "Create task"),
            EngineAction("list", "GET", "List tasks"),
            EngineAction("send", "POST", "Send task to device"),
        ],
    ))
