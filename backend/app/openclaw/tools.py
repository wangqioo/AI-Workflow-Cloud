"""OpenClaw tool definitions and execution.

Ported from v0.7.5 plugin.py (call_local_service to localhost ports)
to v0.8 cloud mode (internal module calls or HTTP to external services).

Tool definitions follow OpenAI function-calling format.
"""

from __future__ import annotations

import json
from typing import Any

# --- Tool Definitions (OpenAI function-calling format) ---

TOOL_DEFINITIONS = [
    # === System Tools ===
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "Get system resource status: CPU, memory, disk, GPU usage",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_engines",
            "description": "List all available AI engines and their status",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    # === AI Service Tools ===
    {
        "type": "function",
        "function": {
            "name": "translate_text",
            "description": "Translate text to a target language",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to translate"},
                    "target_lang": {"type": "string", "description": "Target language code (en/zh/ja/ko/fr/de/es...)"},
                    "source_lang": {"type": "string", "description": "Source language (auto-detect if omitted)"},
                },
                "required": ["text", "target_lang"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "text_to_speech",
            "description": "Convert text to speech audio",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to synthesize"},
                    "language": {"type": "string", "description": "Language code"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_knowledge_base",
            "description": "Search the RAG knowledge base for relevant information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "top_k": {"type": "integer", "description": "Number of results (default 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crawl_webpage",
            "description": "Crawl a webpage and extract its main content",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to crawl"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_email_inbox",
            "description": "Check email inbox and list recent emails",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Number of emails to fetch (default 10)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject"},
                    "body": {"type": "string", "description": "Email body"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    # === Memory Tools ===
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Search long-term conversation memory for relevant past context",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save important information to long-term memory",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to remember"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for categorization"},
                },
                "required": ["content"],
            },
        },
    },
    # === Smart Home Tools ===
    {
        "type": "function",
        "function": {
            "name": "smart_home_devices",
            "description": "List all smart home devices and their states",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "smart_home_control",
            "description": "Control a smart home device (turn on/off, set temperature, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Device entity ID"},
                    "action": {"type": "string", "description": "Action: turn_on, turn_off, toggle, set_value"},
                    "value": {"type": "string", "description": "Value for set_value action"},
                },
                "required": ["entity_id", "action"],
            },
        },
    },
    # === Workflow Tools ===
    {
        "type": "function",
        "function": {
            "name": "discover_capabilities",
            "description": "Discover all available engine capabilities and their API schemas. Use before creating workflows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Filter by category (ai/data/system/workflow)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_workflow",
            "description": "Create a new workflow (n8n node-graph format)",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Workflow name"},
                    "description": {"type": "string", "description": "What this workflow does"},
                    "nodes": {"type": "array", "description": "n8n workflow nodes"},
                    "connections": {"type": "object", "description": "n8n node connections"},
                },
                "required": ["name", "nodes", "connections"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_workflow",
            "description": "Execute a saved workflow by ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "Workflow ID"},
                    "input_data": {"type": "object", "description": "Input parameters for the workflow"},
                },
                "required": ["workflow_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_workflows",
            "description": "List all available workflows",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    # === Document Version Tools ===
    {
        "type": "function",
        "function": {
            "name": "doc_list_projects",
            "description": "List all document projects and their documents",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "doc_search",
            "description": "Search documents by content, tags, or metadata",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "doc_get_history",
            "description": "Get version history of a document",
            "parameters": {
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Project name"},
                    "filename": {"type": "string", "description": "Document filename"},
                },
                "required": ["project", "filename"],
            },
        },
    },
    # === Task Delegation Tools ===
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a new task for cross-device delegation",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title"},
                    "description": {"type": "string", "description": "Detailed task description"},
                    "assignee": {"type": "string", "description": "Target device or user"},
                    "priority": {"type": "string", "description": "Priority: low/medium/high/urgent"},
                    "due_date": {"type": "string", "description": "Due date (ISO format)"},
                },
                "required": ["title", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List tasks with optional filters",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status (pending/in_progress/completed)"},
                },
                "required": [],
            },
        },
    },
    # === Wake on LAN ===
    {
        "type": "function",
        "function": {
            "name": "wake_device",
            "description": "Wake a device on the local network via Wake-on-LAN",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_name": {"type": "string", "description": "Device name or MAC address"},
                },
                "required": ["device_name"],
            },
        },
    },
]


# --- Tool Execution ---

async def execute_tool(name: str, arguments: dict[str, Any], user_id: str | None = None) -> str:
    """Execute a tool and return result as JSON string.

    In v0.7.5 this called localhost HTTP services.
    In v0.8 this calls internal modules or external APIs.
    """
    try:
        handler = _TOOL_HANDLERS.get(name)
        if handler is None:
            return json.dumps({"error": f"Unknown tool: {name}"})
        return await handler(arguments, user_id)
    except Exception as e:
        return json.dumps({"error": f"Tool '{name}' failed: {str(e)}"})


# --- Tool Handler Implementations ---
# Each handler is an async function(arguments, user_id) -> str

async def _get_system_status(args: dict, user_id: str | None) -> str:
    import platform
    return json.dumps({
        "platform": platform.platform(),
        "python": platform.python_version(),
        "status": "running",
        "deploy_mode": "cloud",
    })


async def _list_engines(args: dict, user_id: str | None) -> str:
    from ..engines.registry import get_registry
    return json.dumps({"engines": get_registry().list_engines()})


async def _discover_capabilities(args: dict, user_id: str | None) -> str:
    from ..engines.registry import get_registry
    caps = get_registry().get_capabilities()
    category = args.get("category")
    if category:
        caps = {k: v for k, v in caps.items() if v.get("category") == category}
    # Format as readable summary
    lines = []
    for eid, info in caps.items():
        lines.append(f"[{eid}] {info['name']} ({info['category']}): {info['description']}")
        for aname, ainfo in info.get("actions", {}).items():
            lines.append(f"  - {aname}: {ainfo['description']}")
    return "\n".join(lines) if lines else "No engines found."


async def _translate_text(args: dict, user_id: str | None) -> str:
    # TODO: integrate with translation service module
    return json.dumps({"status": "not_implemented", "message": "Translation service pending migration"})


async def _text_to_speech(args: dict, user_id: str | None) -> str:
    return json.dumps({"status": "not_implemented", "message": "TTS service pending migration"})


async def _query_knowledge_base(args: dict, user_id: str | None) -> str:
    return json.dumps({"status": "not_implemented", "message": "RAG service pending migration"})


async def _crawl_webpage(args: dict, user_id: str | None) -> str:
    import httpx
    url = args.get("url", "")
    if not url:
        return json.dumps({"error": "URL is required"})
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, follow_redirects=True)
        # Return first 4000 chars of text content
        text = resp.text[:4000]
        return json.dumps({"url": url, "status": resp.status_code, "content": text})


async def _check_email(args: dict, user_id: str | None) -> str:
    return json.dumps({"status": "not_implemented", "message": "Email service pending migration"})


async def _send_email(args: dict, user_id: str | None) -> str:
    return json.dumps({"status": "not_implemented", "message": "Email service pending migration"})


async def _search_memory(args: dict, user_id: str | None) -> str:
    return json.dumps({"status": "not_implemented", "message": "Memory service pending migration"})


async def _save_memory(args: dict, user_id: str | None) -> str:
    return json.dumps({"status": "not_implemented", "message": "Memory service pending migration"})


async def _smart_home_devices(args: dict, user_id: str | None) -> str:
    return json.dumps({"status": "not_implemented", "message": "Smart home pending HAL bridge"})


async def _smart_home_control(args: dict, user_id: str | None) -> str:
    return json.dumps({"status": "not_implemented", "message": "Smart home pending HAL bridge"})


async def _create_workflow(args: dict, user_id: str | None) -> str:
    return json.dumps({"status": "not_implemented", "message": "Workflow engine pending migration"})


async def _execute_workflow(args: dict, user_id: str | None) -> str:
    return json.dumps({"status": "not_implemented", "message": "Workflow engine pending migration"})


async def _list_workflows(args: dict, user_id: str | None) -> str:
    return json.dumps({"status": "not_implemented", "message": "Workflow engine pending migration"})


async def _doc_list_projects(args: dict, user_id: str | None) -> str:
    return json.dumps({"status": "not_implemented", "message": "Doc version pending migration"})


async def _doc_search(args: dict, user_id: str | None) -> str:
    return json.dumps({"status": "not_implemented", "message": "Doc version pending migration"})


async def _doc_get_history(args: dict, user_id: str | None) -> str:
    return json.dumps({"status": "not_implemented", "message": "Doc version pending migration"})


async def _create_task(args: dict, user_id: str | None) -> str:
    return json.dumps({"status": "not_implemented", "message": "Task system pending migration"})


async def _list_tasks(args: dict, user_id: str | None) -> str:
    return json.dumps({"status": "not_implemented", "message": "Task system pending migration"})


async def _wake_device(args: dict, user_id: str | None) -> str:
    return json.dumps({"status": "not_implemented", "message": "WOL pending HAL bridge"})


# Tool name → handler mapping
_TOOL_HANDLERS = {
    "get_system_status": _get_system_status,
    "list_engines": _list_engines,
    "discover_capabilities": _discover_capabilities,
    "translate_text": _translate_text,
    "text_to_speech": _text_to_speech,
    "query_knowledge_base": _query_knowledge_base,
    "crawl_webpage": _crawl_webpage,
    "check_email_inbox": _check_email,
    "send_email": _send_email,
    "search_memory": _search_memory,
    "save_memory": _save_memory,
    "smart_home_devices": _smart_home_devices,
    "smart_home_control": _smart_home_control,
    "create_workflow": _create_workflow,
    "execute_workflow": _execute_workflow,
    "list_workflows": _list_workflows,
    "discover_capabilities": _discover_capabilities,
    "doc_list_projects": _doc_list_projects,
    "doc_search": _doc_search,
    "doc_get_history": _doc_get_history,
    "create_task": _create_task,
    "list_tasks": _list_tasks,
    "wake_device": _wake_device,
}
