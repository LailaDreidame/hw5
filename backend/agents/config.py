"""Model, Portkey, MCP connection and the limits that keep token use in check.

Every agent uses ONE model: gpt-6-luna through Portkey. The name is a constant
(not read from the environment) so no other model can slip in.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402
from pydantic_ai import RunContext  # noqa: E402
from pydantic_ai.mcp import MCPToolset  # noqa: E402
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings  # noqa: E402
from pydantic_ai.providers.openai import OpenAIProvider  # noqa: E402
from pydantic_ai.usage import UsageLimits  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent                      # hw5/
PROMPTS_DIR = BACKEND / "prompts"
AUDIT_PATH = Path(os.environ.get("CAMPUS_AUDIT_PATH", ROOT / "output" / "audit_trail.json"))
MCP_DIR = ROOT / "mcp_server"

# .env may sit in hw5/, the Homework 5 folder, or the class folder; the shell env also works.
for env_file in (ROOT / ".env", ROOT.parent / ".env", ROOT.parent.parent / ".env"):
    load_dotenv(env_file)

# --- the only model allowed ------------------------------------------------
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# --- token / cost guardrails (apply to one whole team run) -----------------
MAX_DELEGATION_DEPTH = 2          # boss -> worker -> one more worker, no deeper
MAX_DELEGATIONS_PER_RUN = 8       # total ask_agent calls across the whole run
MAX_MODEL_CALLS_PER_AGENT = 10    # model calls one agent may make before it is stopped
RUN_LIMITS = UsageLimits(
    request_limit=30,             # model calls across all agents in the run
    tool_calls_limit=60,          # tool calls across all agents in the run
    total_tokens_limit=250_000,   # input + output tokens across all agents in the run
)
MODEL_SETTINGS = OpenAIResponsesModelSettings(
    max_tokens=8_000,                 # cap on each single response (reasoning tokens count toward it)
    openai_reasoning_effort="low",    # short internal reasoning to save tokens
)

# --- tools no agent may ever call (human approval only) ---------------------
HUMAN_ONLY_TOOLS = frozenset({"approve_and_pay", "reject_approval"})
# Tool arguments that record WHO acted; always overwritten with the real agent name.
ACTOR_ARGS = ("requested_by", "created_by", "updated_by")


def require_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is not set (shell environment or a .env file).")
    return key


_model: OpenAIResponsesModel | None = None


def build_model() -> OpenAIResponsesModel:
    """gpt-6-luna via Portkey (same pattern as the lectures). Shared by all five agents."""
    global _model
    if _model is None:
        key = require_api_key()
        client = AsyncOpenAI(api_key=key, base_url=PORTKEY_BASE_URL,
                             default_headers={"x-portkey-api-key": key})
        _model = OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
    assert _model.model_name == MODEL_NAME, "Only gpt-6-luna is allowed."
    return _model


async def _stamp_actor(ctx: RunContext[Any], call_tool, name: str, args: dict[str, Any]):
    """Runs before every MCP call: block human-only tools and record the real agent as the actor."""
    if name in HUMAN_ONLY_TOOLS:
        return {"ok": False, "refused": True, "reason": f"{name} is human-only. Ask a person on the board."}
    agent = getattr(ctx.deps, "agent", None)
    if agent:
        for arg in ACTOR_ARGS:
            if arg in args:
                args[arg] = agent
    return await call_tool(name, args)


_mcp_toolset: MCPToolset | None = None


def mcp_toolset() -> MCPToolset:
    """The Campus Customs MCP server, attached in-process. All shop facts come through here."""
    global _mcp_toolset
    if _mcp_toolset is None:
        if str(MCP_DIR) not in sys.path:
            sys.path.insert(0, str(MCP_DIR))
        from server import mcp as campus_mcp  # mcp_server/server.py

        _mcp_toolset = MCPToolset(campus_mcp, id="campus-customs", process_tool_call=_stamp_actor,
                                  max_retries=1)
    return _mcp_toolset
