"""Workflow execution engine.

Ported from v0.7.5 WorkflowExecutor. Supports n8n node-graph format
and legacy steps format. In cloud mode, engine calls go through
internal service modules instead of localhost HTTP ports.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Callable

import httpx

from ..engines.registry import get_registry


async def execute_workflow(
    definition: dict,
    input_data: dict | None = None,
    trigger_data: dict | None = None,
    on_progress: Callable | None = None,
) -> dict:
    """Execute a workflow definition.

    Returns {status, steps_completed, steps_failed, results, execution_time_ms, error}.
    """
    input_data = input_data or {}
    trigger_data = trigger_data or {}
    start = time.time()

    context = {
        "trigger": trigger_data,
        "input": input_data,
        "steps": {},
        "env": {},
    }

    # Detect format: n8n (nodes+connections) vs steps
    wf = definition.get("workflow", definition)
    if "nodes" in wf and "connections" in wf:
        result = await _execute_n8n(wf, context, on_progress)
    elif "steps" in wf:
        result = await _execute_steps(wf["steps"], context, on_progress)
    else:
        result = {"status": "error", "error": "Unknown workflow format", "steps_completed": 0, "steps_failed": 0}

    elapsed = (time.time() - start) * 1000
    result["execution_time_ms"] = round(elapsed, 1)
    result["results"] = context["steps"]
    return result


# ---- n8n format execution ----

async def _execute_n8n(wf: dict, context: dict, on_progress: Callable | None) -> dict:
    nodes = {n["name"]: n for n in wf.get("nodes", [])}
    connections = wf.get("connections", {})

    # Build adjacency: node_name -> [next_node_names]
    adj: dict[str, list[str]] = {}
    for src_name, outputs in connections.items():
        targets = []
        for branch in outputs.get("main", []):
            for link in branch:
                targets.append(link["node"])
        adj[src_name] = targets

    # Find start node (no incoming edges)
    all_targets = {t for ts in adj.values() for t in ts}
    start_nodes = [n for n in nodes if n not in all_targets]
    if not start_nodes:
        start_nodes = list(nodes.keys())[:1]

    # Topological BFS execution
    executed = set()
    queue = list(start_nodes)
    steps_ok = 0
    steps_fail = 0

    while queue:
        name = queue.pop(0)
        if name in executed:
            continue
        executed.add(name)

        node = nodes.get(name)
        if not node:
            continue

        if on_progress:
            on_progress({"type": "step_started", "step_id": name, "step_name": name})

        result = await _execute_node(node, context)
        context["steps"][name] = result

        if result.get("status") == "success":
            steps_ok += 1
        else:
            steps_fail += 1

        if on_progress:
            on_progress({"type": "step_completed", "step_id": name, "status": result.get("status")})

        # Enqueue downstream nodes
        for next_name in adj.get(name, []):
            if next_name not in executed:
                queue.append(next_name)

    status = "success" if steps_fail == 0 else "error"
    return {"status": status, "steps_completed": steps_ok, "steps_failed": steps_fail}


async def _execute_node(node: dict, context: dict) -> dict:
    """Execute a single n8n node."""
    node_type = node.get("type", "")
    params = node.get("parameters", {})

    try:
        if node_type in ("n8n-nodes-base.manualTrigger", "n8n-nodes-base.noOp"):
            return {"status": "success", "result": {}}

        if node_type == "ai-workflow.engineCall":
            engine = params.get("engine", "")
            action = params.get("action", "")
            call_params = _resolve_params(params.get("params", {}), context)
            result = await _call_engine(engine, action, call_params)
            return {"status": "success", "result": result}

        if node_type == "n8n-nodes-base.httpRequest":
            url = _resolve_value(params.get("url", ""), context)
            method = params.get("method", "GET").upper()
            body = _resolve_params(params.get("body", {}), context)
            result = await _http_request(method, url, body)
            return {"status": "success", "result": result}

        if node_type == "n8n-nodes-base.code":
            code = params.get("code", "")
            # Cloud mode: eval simple expressions only (no subprocess sandbox)
            result = _eval_code(code, context)
            return {"status": "success", "result": result}

        if node_type == "n8n-nodes-base.set":
            assignments = params.get("assignments", {})
            resolved = _resolve_params(assignments, context)
            return {"status": "success", "result": resolved}

        if node_type == "n8n-nodes-base.if":
            condition = params.get("condition", "")
            val = _resolve_value(str(condition), context)
            branch = bool(val) if val else False
            return {"status": "success", "result": {"branch": branch}}

        if node_type == "n8n-nodes-base.merge":
            return {"status": "success", "result": {}}

        # Unknown node type — pass through
        return {"status": "success", "result": {"node_type": node_type, "note": "passthrough"}}

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---- Legacy steps format execution ----

async def _execute_steps(steps: list[dict], context: dict, on_progress: Callable | None) -> dict:
    steps_ok = 0
    steps_fail = 0

    for i, step in enumerate(steps):
        step_id = step.get("id", f"step_{i}")

        # Check condition
        condition = step.get("condition")
        if condition and not _evaluate_condition(condition, context):
            context["steps"][step_id] = {"status": "skipped"}
            continue

        if on_progress:
            on_progress({"type": "step_started", "step_id": step_id, "step_index": i})

        try:
            step_type = step.get("step_type", "engine")

            if step_type == "engine":
                engine = step.get("engine", "")
                action = step.get("action", "")
                params = _resolve_params(step.get("params", {}), context)
                timeout = step.get("timeout", 120)
                result = await asyncio.wait_for(_call_engine(engine, action, params), timeout=timeout)
                context["steps"][step_id] = {"status": "success", "result": result}
                steps_ok += 1

            elif step_type == "http_request":
                url = _resolve_value(step.get("url", ""), context)
                method = step.get("method", "GET").upper()
                body = _resolve_params(step.get("body", {}), context)
                result = await _http_request(method, url, body)
                context["steps"][step_id] = {"status": "success", "result": result}
                steps_ok += 1

            elif step_type == "transform":
                mapping = step.get("mapping", {})
                resolved = _resolve_params(mapping, context)
                context["steps"][step_id] = {"status": "success", "result": resolved}
                steps_ok += 1

            elif step_type == "code":
                code = step.get("code", "")
                result = _eval_code(code, context)
                context["steps"][step_id] = {"status": "success", "result": result}
                steps_ok += 1

            else:
                context["steps"][step_id] = {"status": "success", "result": {}}
                steps_ok += 1

        except asyncio.TimeoutError:
            context["steps"][step_id] = {"status": "error", "error": "timeout"}
            steps_fail += 1
            on_error = step.get("on_error", "stop")
            if on_error == "stop":
                break
        except Exception as e:
            context["steps"][step_id] = {"status": "error", "error": str(e)}
            steps_fail += 1
            on_error = step.get("on_error", "stop")
            if on_error == "stop":
                break

        if on_progress:
            on_progress({"type": "step_completed", "step_id": step_id, "status": context["steps"][step_id]["status"]})

    status = "success" if steps_fail == 0 else "error"
    return {"status": status, "steps_completed": steps_ok, "steps_failed": steps_fail}


# ---- Internal engine call ----

async def _call_engine(engine: str, action: str, params: dict) -> dict:
    """Call an internal engine.

    In v0.7.5 this was HTTP to localhost:8100/engine/{engine}/{action}.
    In v0.8 cloud mode, we call internal service modules directly where possible,
    or use the engine registry to dispatch.
    """
    registry = get_registry()
    engine_def = registry.get_engine(engine)
    if not engine_def:
        return {"error": f"Engine '{engine}' not found"}

    # For AI engines, use LLM provider
    if engine == "llm":
        from ..llm.provider import get_llm_provider
        llm = get_llm_provider()
        messages = params.get("messages", [{"role": "user", "content": params.get("prompt", "")}])
        result = await llm.chat(messages, max_tokens=params.get("max_tokens", 2048))
        return result

    # For other engines, return placeholder (will be wired per-service in later phases)
    return {"engine": engine, "action": action, "status": "dispatched", "params": params}


# ---- HTTP request helper ----

async def _http_request(method: str, url: str, body: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        if method == "GET":
            resp = await client.get(url, follow_redirects=True)
        elif method == "POST":
            resp = await client.post(url, json=body, follow_redirects=True)
        elif method == "PUT":
            resp = await client.put(url, json=body, follow_redirects=True)
        elif method == "DELETE":
            resp = await client.delete(url, follow_redirects=True)
        else:
            return {"error": f"Unsupported method: {method}"}

        try:
            data = resp.json()
        except Exception:
            data = resp.text[:2000]
        return {"status_code": resp.status_code, "data": data}


# ---- Variable resolution ----

_VAR_PATTERN = re.compile(r"\$(\w+(?:\.\w+)*)")
_N8N_EXPR = re.compile(r"\{\{(.+?)\}\}")


def _resolve_value(value: Any, context: dict) -> Any:
    """Resolve variable references in a single value."""
    if not isinstance(value, str):
        return value

    # n8n expression: {{ $json.field }}
    def _n8n_replace(m: re.Match) -> str:
        expr = m.group(1).strip()
        # $json.field → last step output
        if expr.startswith("$json"):
            return str(_walk_path(expr, context))
        if expr.startswith("$node"):
            return str(_walk_path(expr, context))
        if expr.startswith("$env"):
            return str(_walk_path(expr, context))
        return m.group(0)

    if "{{" in value:
        value = _N8N_EXPR.sub(_n8n_replace, value)

    # Direct $variable.path references
    def _var_replace(m: re.Match) -> str:
        path = m.group(1)
        result = _walk_path(f"${path}", context)
        return str(result) if result is not None else m.group(0)

    if "$" in value:
        # If the entire string is a single variable, preserve its type
        full_match = _VAR_PATTERN.fullmatch(value.strip())
        if full_match:
            result = _walk_path(f"${full_match.group(1)}", context)
            if result is not None:
                return result
        value = _VAR_PATTERN.sub(_var_replace, value)

    return value


def _resolve_params(params: dict | list | Any, context: dict) -> Any:
    """Recursively resolve all variable references in params."""
    if isinstance(params, dict):
        return {k: _resolve_params(v, context) for k, v in params.items()}
    if isinstance(params, list):
        return [_resolve_params(v, context) for v in params]
    return _resolve_value(params, context)


def _walk_path(path: str, context: dict) -> Any:
    """Walk a dot-separated path through context.

    Supports: $trigger.x, $input.x, $steps.step_id.result, $env.VAR
    """
    if path.startswith("$"):
        path = path[1:]
    parts = path.split(".")

    root_key = parts[0]
    if root_key in context:
        obj = context[root_key]
        for part in parts[1:]:
            if isinstance(obj, dict):
                obj = obj.get(part)
            else:
                return None
            if obj is None:
                return None
        return obj
    return None


def _evaluate_condition(condition: str, context: dict) -> bool:
    """Evaluate a simple condition string."""
    resolved = _resolve_value(condition, context)
    if isinstance(resolved, bool):
        return resolved
    s = str(resolved).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no", "none", ""):
        return False
    # Simple comparisons: "value == expected"
    if "==" in str(resolved):
        parts = str(resolved).split("==")
        if len(parts) == 2:
            return parts[0].strip() == parts[1].strip()
    return bool(resolved)


def _eval_code(code: str, context: dict) -> dict:
    """Evaluate simple code expressions (safe subset).

    Full sandbox execution via subprocess is deferred to a later phase.
    """
    # For now, return the code as-is with resolved variables
    return {"code": code, "note": "code execution deferred to container sandbox phase"}
