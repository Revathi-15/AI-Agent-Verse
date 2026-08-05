# backend/orchestrator.py
# Two orchestration modes:
#   1. run_orchestrated()  — original tool-picker pipeline (used by /orchestrate)
#   2. run_multi_agent()   — full 6-agent pipeline imported from multi_agent_tool
#      (used by /multi-agent SSE endpoint)

import json
import time
from typing import Generator

from backend.tools    import all_tools
from backend.llm      import call_llm
from backend.database import state as db_state, run_query, quote


# ── Tool-picker orchestrator (original) ──────────────────────────────────────

def _plan(user_query: str, available_tools: dict, table: str) -> list[dict]:
    """Ask LLM to select which tools to run and in what order."""
    tool_list = "\n".join(
        f"  {t.emoji} {name}: {t.description}"
        for name, t in available_tools.items()
    )
    prompt = (
        f"You are a data analysis orchestrator. The user asked:\n\"{user_query}\"\n\n"
        f"Active table: {table}\n\n"
        f"Available tools:\n{tool_list}\n\n"
        f"Choose 1–2 tools to answer the query. Return ONLY a JSON array like:\n"
        f'[{{"tool":"sql_query","reason":"user wants data","kwargs":{{"query":"{user_query}"}}}}, ...]\n\n'
        f"Rules:\n"
        f"- Use sql_query for most data/chart questions\n"
        f"- Use discover_insights when user asks for insights, trends, or analysis\n"
        f"- Use clean_data when user asks to clean or fix the dataset\n"
        f"- Use profile_dataset when user asks for summary, profile, or overview\n"
        f"- Use show_schema when user asks about columns or schema\n"
        f"- Use optimize_query when user asks to optimise or explain a query\n"
        f"- Use vector_search when user asks about past queries or history\n"
        f"- Use multi_agent for maximum accuracy on complex questions\n"
        f"- Never pick more than 2 tools\n"
        f"Respond with ONLY the JSON array, nothing else."
    )
    try:
        raw  = call_llm(prompt, max_tokens=300, temperature=0)
        raw  = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        plan = json.loads(raw)
        return plan if isinstance(plan, list) else []
    except Exception:
        return [{"tool": "sql_query", "reason": "default", "kwargs": {"query": user_query}}]


def run_orchestrated(
    user_query: str,
    table: str,
    df_store: dict,
) -> Generator[dict, None, None]:
    """
    Tool-picker generator. Yields status / tool_done / result / error dicts.
    """
    tools = all_tools()

    yield {"type": "status", "text": "🧠 Planning which tools to use…", "step": 0}
    time.sleep(0.1)

    plan = _plan(user_query, tools, table)
    if not plan:
        yield {"type": "error", "text": "Could not determine which tools to run."}
        return

    total   = len(plan)
    results = []

    for i, step in enumerate(plan, 1):
        tool_name = step.get("tool", "sql_query")
        reason    = step.get("reason", "")
        kwargs    = step.get("kwargs", {})
        tool      = tools.get(tool_name)

        if not tool:
            yield {"type": "status", "text": f"⚠️ Unknown tool: {tool_name}", "step": i}
            continue

        yield {
            "type" : "status",
            "text" : f"{tool.emoji} Running **{tool_name}** — {reason}",
            "step" : i,
            "total": total,
        }
        time.sleep(0.05)

        t0      = time.time()
        result  = tool.run(table=table, df_store=df_store, **kwargs)
        elapsed = round(time.time() - t0, 2)

        result["tool"]    = tool_name
        result["elapsed"] = elapsed
        results.append(result)

        yield {
            "type"   : "tool_done",
            "tool"   : tool_name,
            "emoji"  : tool.emoji,
            "summary": result.get("summary", ""),
            "elapsed": elapsed,
            "step"   : i,
        }

    yield {"type": "result", "results": results, "tools_used": [p["tool"] for p in plan]}


# ── Multi-agent orchestrator (6-agent pipeline) ───────────────────────────────

def run_multi_agent_stream(
    user_query: str,
    table: str,
) -> Generator[dict, None, None]:
    """
    Proxy to multi_agent_tool.run_multi_agent — yields the same event dicts
    so the /multi-agent SSE endpoint can stream them directly.
    """
    from backend.tools.multi_agent_tool import run_multi_agent
    yield from run_multi_agent(user_query, table)
