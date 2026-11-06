"""Append-only audit trail: output/audit_trail.json.

The file is one JSON list. Every agent-loop step adds one entry; nothing is
ever removed or rewritten, so the trail grows across runs. If the file is ever
corrupted it is set aside (renamed) rather than wiped.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any

from pydantic_ai import CallToolsNode, ModelRequestNode, UserPromptNode
from pydantic_ai.messages import (
    BaseToolCallPart,
    BaseToolReturnPart,
    RetryPromptPart,
    TextPart,
    ThinkingPart,
    UserPromptPart,
)
from pydantic_core import to_json

from models import TeamDeps

from .config import AUDIT_PATH

PREVIEW_CHARS = 1_500
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def preview(value: Any, limit: int = PREVIEW_CHARS) -> str:
    text = value if isinstance(value, str) else to_json(value).decode("utf-8", "replace")
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def append(entry: dict[str, Any], deps: TeamDeps | None = None) -> dict[str, Any]:
    """Append one entry to output/audit_trail.json (never wipes) and push it to the live queue."""
    row = {"time": _now()}
    if deps is not None:
        row.update(run_id=deps.run_id, ticket_id=deps.ticket_id, agent=deps.agent,
                   depth=deps.depth, chain=list(deps.chain))
    row.update(entry)
    with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        rows: list[Any] = []
        if AUDIT_PATH.exists() and AUDIT_PATH.stat().st_size > 0:
            try:
                loaded = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
                rows = loaded if isinstance(loaded, list) else [loaded]
            except json.JSONDecodeError:
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                AUDIT_PATH.replace(AUDIT_PATH.with_name(f"audit_trail.corrupt-{stamp}.json"))
        rows.append(row)
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(AUDIT_PATH)
    if deps is not None and deps.events is not None:
        deps.events.put_nowait(row)
    return row


def log_node(node: Any, step: int, deps: TeamDeps) -> None:
    """Record one step of an agent's loop: what went in, what the model said, which tools it called."""
    entry: dict[str, Any] = {"event": "agent_step", "step": step}

    if isinstance(node, UserPromptNode):
        entry.update(node_type="task_received", task=preview(node.user_prompt))

    elif isinstance(node, ModelRequestNode):
        tool_results, retries, prompts = [], [], []
        for part in node.request.parts:
            if isinstance(part, BaseToolReturnPart):
                tool_results.append({"tool": part.tool_name, "call_id": part.tool_call_id,
                                     "result": preview(part.content)})
            elif isinstance(part, RetryPromptPart):
                retries.append({"tool": part.tool_name, "error": preview(part.content, 400)})
            elif isinstance(part, UserPromptPart):
                prompts.append(preview(part.content, 400))
        entry.update(node_type="model_request", tool_results=tool_results, retries=retries,
                     user_prompt=prompts or None)

    elif isinstance(node, CallToolsNode):
        resp = node.model_response
        calls, texts, thoughts = [], [], []
        for part in resp.parts:
            if isinstance(part, BaseToolCallPart):
                calls.append({"tool": part.tool_name, "call_id": part.tool_call_id,
                              "args": part.args_as_dict()})
            elif isinstance(part, TextPart) and part.content:
                texts.append(preview(part.content, 800))
            elif isinstance(part, ThinkingPart) and part.content:
                thoughts.append(preview(part.content, 800))
        usage = resp.usage
        entry.update(node_type="model_response", model=resp.model_name,
                     finish_reason=resp.finish_reason, tool_calls=calls, text=texts or None,
                     reasoning_summary=thoughts or None,
                     usage={"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens})
    else:
        entry.update(node_type="end")
        result = getattr(node, "data", None)
        output = getattr(result, "output", None)
        if output is not None:
            entry["output"] = output.model_dump() if hasattr(output, "model_dump") else preview(output)

    append(entry, deps)
