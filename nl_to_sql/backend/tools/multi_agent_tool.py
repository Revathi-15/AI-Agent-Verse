# multi_agent_tool.py — Full multi-agent pipeline:
#   Planner → Schema Agent → SQL Agent → Validation Agent → Visualization Agent → Explanation Agent
#
# Each agent is a focused LLM call with a specific role and output contract.

import json
import time
from typing import Generator
from backend.tools.base  import BaseTool
from backend.database    import get_schema, run_query, quote, state, DB_PATH
from backend.llm         import call_llm, generate_sql


# ─────────────────────────────────────────────────────────────────────────────
# Individual Agent functions
# ─────────────────────────────────────────────────────────────────────────────

def planner_agent(question: str, schema: str, table: str) -> dict:
    """Breaks the question into a data pipeline plan."""
    prompt = f"""You are a data pipeline planner agent.

User question: "{question}"
Table: "{table}"
Schema:
{schema}

Your job: Break this into a structured pipeline. Return JSON only:
{{
  "intent": "query|analysis|dashboard|transform|schema|export",
  "entities": ["list of key entities/columns mentioned"],
  "filters": ["any filter conditions mentioned"],
  "aggregations": ["COUNT, SUM, AVG, etc. needed"],
  "sort": "column and direction if needed",
  "limit": "number if specified, else null",
  "chart_hint": "bar|line|pie|scatter|histogram|none",
  "complexity": "simple|medium|complex",
  "reasoning": "one sentence about approach"
}}"""
    try:
        raw  = call_llm(prompt, max_tokens=300, temperature=0)
        raw  = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        plan = json.loads(raw)
        return {"ok": True, "plan": plan}
    except Exception as e:
        return {
            "ok": True,
            "plan": {
                "intent": "query",
                "entities": [],
                "filters": [],
                "aggregations": [],
                "sort": "",
                "limit": None,
                "chart_hint": "bar",
                "complexity": "simple",
                "reasoning": f"Fallback plan (parse error: {e})",
            },
        }


def schema_agent(table: str, question: str, schema: str) -> dict:
    """Identifies the relevant columns and any data quality concerns."""
    prompt = f"""You are a database schema expert agent.

Table: "{table}"
Question: "{question}"
Schema:
{schema}

Identify:
1. Most relevant columns for this question (list them).
2. Any column name ambiguities to watch for.
3. Data quality concerns (nulls, mixed types, etc.).
4. Suggested JOIN or subquery strategy if needed.

Return JSON only:
{{
  "relevant_columns": ["col1", "col2"],
  "year_column": "best year column or null",
  "concerns": ["concern1", "concern2"],
  "strategy": "one sentence SQL approach"
}}"""
    try:
        raw    = call_llm(prompt, max_tokens=300, temperature=0)
        raw    = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        result = json.loads(raw)
        return {"ok": True, "schema_analysis": result}
    except Exception as e:
        return {"ok": True, "schema_analysis": {"relevant_columns": [], "concerns": [], "strategy": str(e)}}


def sql_agent(table: str, schema: str, question: str,
              plan: dict, schema_analysis: dict) -> dict:
    """Generates the SQL query using planner and schema agent outputs."""
    # Enrich the question with planner hints
    enriched = (
        f"{question}\n\n"
        f"[Planner hints: intent={plan.get('intent')}, "
        f"filters={plan.get('filters')}, "
        f"aggregations={plan.get('aggregations')}, "
        f"sort={plan.get('sort')}, "
        f"limit={plan.get('limit')}, "
        f"complexity={plan.get('complexity')}]\n"
        f"[Schema agent: use columns {schema_analysis.get('relevant_columns')}, "
        f"year={schema_analysis.get('year_column')}, "
        f"strategy={schema_analysis.get('strategy')}]"
    )
    try:
        sql = generate_sql(table, schema, enriched)
        return {"ok": True, "sql": sql}
    except Exception as e:
        return {"ok": False, "sql": "", "error": str(e)}


def validation_agent(sql: str, table: str) -> dict:
    """Validates the SQL before execution: syntax check + safety check."""
    import sqlite3
    issues = []

    # Safety: block destructive keywords
    danger_words = ["DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE", "CREATE"]
    sql_upper = sql.upper()
    for word in danger_words:
        if word in sql_upper:
            return {
                "ok"    : False,
                "safe"  : False,
                "issues": [f"Blocked: SQL contains '{word}' — only SELECT is allowed."],
            }

    # Syntax: try EXPLAIN
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(f"EXPLAIN {sql}").fetchall()
        conn.close()
    except Exception as e:
        issues.append(f"Syntax issue: {e}")

    # LLM review
    prompt = (
        f"Review this SQL for correctness:\n{sql}\n\n"
        f"List any issues on separate lines. If it looks correct, reply: VALID"
    )
    llm_review = call_llm(prompt, max_tokens=150, temperature=0)
    if "VALID" not in llm_review.upper() and len(llm_review) > 5:
        issues.append(f"LLM review: {llm_review[:200]}")

    return {
        "ok"    : len(issues) == 0,
        "safe"  : True,
        "issues": issues,
    }


def visualization_agent(question: str, columns: list, row_count: int,
                        plan: dict) -> dict:
    """Decides the best visualization type and chart config."""
    # Use planner's chart hint as a strong prior
    chart_hint = plan.get("chart_hint", "")

    prompt = (
        f"You are a data visualization expert agent.\n"
        f"User question: \"{question}\"\n"
        f"Result: {row_count} rows, columns: {columns}\n"
        f"Planner suggested: {chart_hint}\n\n"
        f"Choose the BEST chart type from: bar, line, pie, scatter, histogram, none\n"
        f"Rules:\n"
        f"- line: trends over time, growth, historical series\n"
        f"- bar: rankings, top-N, comparisons across categories\n"
        f"- pie: percentages, shares, composition (≤10 slices)\n"
        f"- scatter: correlation between two numeric variables\n"
        f"- histogram: distribution of a single numeric variable\n"
        f"- none: single value, schema info, or text-only answers\n\n"
        f"Reply with JSON only: {{\"chart\": \"type\", \"reason\": \"one sentence\", "
        f"\"x_hint\": \"column name\", \"y_hint\": \"column name\"}}"
    )
    try:
        raw    = call_llm(prompt, max_tokens=80, temperature=0)
        raw    = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        result = json.loads(raw)
        return {
            "ok"        : True,
            "chart_type": result.get("chart", "bar"),
            "reason"    : result.get("reason", ""),
            "x_hint"    : result.get("x_hint", ""),
            "y_hint"    : result.get("y_hint", ""),
        }
    except Exception:
        return {"ok": True, "chart_type": chart_hint or "bar", "reason": "", "x_hint": "", "y_hint": ""}


def explanation_agent(question: str, sql: str,
                      rows: list, columns: list) -> str:
    """Generates a natural-language explanation of the results."""
    if not rows:
        return "The query returned no results."

    sample   = rows[:15]
    data_str = "\n".join(
        ", ".join(f"{c}: {r.get(c, '')}" for c in columns) for r in sample
    )
    more = f"\n…and {len(rows)-15} more rows." if len(rows) > 15 else ""

    prompt = (
        f"You are a data explanation expert agent. The user asked: \"{question}\"\n\n"
        f"SQL executed: {sql}\n\n"
        f"Results ({len(rows)} rows):\n{data_str}{more}\n\n"
        f"Write a clear, insightful answer:\n"
        f"1. Directly answer the question with specific numbers.\n"
        f"2. Highlight the most interesting finding.\n"
        f"3. Add one actionable insight if relevant.\n\n"
        f"Keep it under 100 words. Use bold for key numbers. No SQL repetition."
    )
    try:
        return call_llm(prompt, max_tokens=250, temperature=0.4)
    except Exception:
        if len(rows) == 1:
            vals = list(rows[0].values())
            return str(vals[0]) if len(vals) == 1 else f"**{vals[0]}**: {vals[-1]}"
        return f"Found **{len(rows)}** result(s)."


# ─────────────────────────────────────────────────────────────────────────────
# Multi-agent streaming generator
# ─────────────────────────────────────────────────────────────────────────────

def run_multi_agent(question: str, table: str) -> Generator[dict, None, None]:
    """
    Streams multi-agent pipeline events. Each yield is a dict with type:
      status  → agent is working
      result  → final answer with all data
      error   → something failed
    """
    import time
    t0 = time.time()

    # ── Agent 1: Planner ──────────────────────────────────────────────────────
    yield {"type": "status", "agent": "planner", "step": 1, "total": 6,
           "text": "🧠 Planner Agent — Breaking down the question…"}
    schema = get_schema(table)
    plan   = planner_agent(question, schema, table)
    if plan["ok"]:
        yield {"type": "agent_result", "agent": "planner",
               "text": f"Plan: {plan['plan'].get('intent','query')} | "
                       f"complexity: {plan['plan'].get('complexity','simple')}",
               "data": plan["plan"]}
    time.sleep(0.05)

    # ── Agent 2: Schema ───────────────────────────────────────────────────────
    yield {"type": "status", "agent": "schema", "step": 2, "total": 6,
           "text": "📋 Schema Agent — Identifying relevant columns…"}
    sa = schema_agent(table, question, schema)
    cols = sa["schema_analysis"].get("relevant_columns", [])
    yield {"type": "agent_result", "agent": "schema",
           "text": f"Relevant columns: {', '.join(cols) or 'auto-detect'}",
           "data": sa["schema_analysis"]}
    time.sleep(0.05)

    # ── Agent 3: SQL ──────────────────────────────────────────────────────────
    yield {"type": "status", "agent": "sql", "step": 3, "total": 6,
           "text": "⚙️ SQL Agent — Generating optimised query…"}
    sql_result = sql_agent(table, schema, question, plan["plan"], sa["schema_analysis"])
    if not sql_result["ok"]:
        yield {"type": "error", "agent": "sql",
               "text": f"SQL generation failed: {sql_result.get('error','unknown')}"}
        return
    sql = sql_result["sql"]
    yield {"type": "agent_result", "agent": "sql", "text": f"SQL ready", "sql": sql}
    time.sleep(0.05)

    # ── Agent 4: Validation ───────────────────────────────────────────────────
    yield {"type": "status", "agent": "validation", "step": 4, "total": 6,
           "text": "✅ Validation Agent — Checking SQL safety & correctness…"}
    val = validation_agent(sql, table)
    if not val["ok"]:
        issues = "; ".join(val["issues"])
        yield {"type": "error", "agent": "validation",
               "text": f"Validation failed: {issues}"}
        # Try to auto-fix: regenerate with issues as hints
        fix_prompt = f"Fix this SQL for table '{table}':\n{sql}\nIssues: {issues}\nReturn only the fixed SQL."
        try:
            sql = call_llm(fix_prompt, max_tokens=300, temperature=0)
            for fence in ("```sql", "```"):
                sql = sql.replace(fence, "")
            sql = sql.strip()
            yield {"type": "agent_result", "agent": "validation",
                   "text": "Auto-fixed SQL", "sql": sql}
        except Exception:
            return

    yield {"type": "agent_result", "agent": "validation",
           "text": "SQL is safe ✅" + (f" — warnings: {'; '.join(val['issues'])}" if val["issues"] else "")}
    time.sleep(0.05)

    # ── Execute SQL ────────────────────────────────────────────────────────────
    yield {"type": "status", "agent": "execution", "step": 4.5, "total": 6,
           "text": "🚀 Executing query against database…"}
    try:
        df = run_query(sql)
        state["sql"] = sql
        state["df"]  = df
        rows    = df.to_dict(orient="records")
        columns = list(df.columns)
    except Exception as e:
        yield {"type": "error", "agent": "execution",
               "text": f"Execution failed: {e}", "sql": sql}
        return
    time.sleep(0.05)

    # ── Agent 5: Visualization ────────────────────────────────────────────────
    yield {"type": "status", "agent": "visualization", "step": 5, "total": 6,
           "text": "📊 Visualization Agent — Selecting best chart…"}
    viz = visualization_agent(question, columns, len(rows), plan["plan"])
    yield {"type": "agent_result", "agent": "visualization",
           "text": f"Chart: {viz['chart_type']} — {viz.get('reason','')}",
           "chart_type": viz["chart_type"]}
    time.sleep(0.05)

    # ── Agent 6: Explanation ──────────────────────────────────────────────────
    yield {"type": "status", "agent": "explanation", "step": 6, "total": 6,
           "text": "💡 Explanation Agent — Writing natural-language answer…"}
    reply = explanation_agent(question, sql, rows, columns)
    time.sleep(0.05)

    elapsed = round(time.time() - t0, 2)

    # ── Final result ───────────────────────────────────────────────────────────
    yield {
        "type"        : "result",
        "reply"       : reply,
        "sql"         : sql,
        "columns"     : columns,
        "rows"        : rows,
        "chart_type"  : viz["chart_type"],
        "elapsed"     : elapsed,
        "agents_used" : ["planner","schema","sql","validation","visualization","explanation"],
        "plan"        : plan["plan"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool wrapper
# ─────────────────────────────────────────────────────────────────────────────

class MultiAgentTool(BaseTool):
    name        = "multi_agent"
    description = "Full 6-agent pipeline: Planner→Schema→SQL→Validation→Visualization→Explanation for highest accuracy"
    emoji       = "🤖"

    def run(self, table: str, df_store: dict, query: str = "", **kwargs) -> dict:
        if not table:
            return {"ok": False, "summary": "No table loaded.", "data": None}
        if not query:
            return {"ok": False, "summary": "Provide a query.", "data": None}

        events  = list(run_multi_agent(query, table))
        result  = next((e for e in events if e.get("type") == "result"), None)
        errors  = [e for e in events if e.get("type") == "error"]

        if result:
            return {
                "ok"        : True,
                "summary"   : result.get("reply", ""),
                "sql"       : result.get("sql"),
                "columns"   : result.get("columns"),
                "rows"      : result.get("rows"),
                "chart_type": result.get("chart_type"),
                "data"      : {"agents_used": result.get("agents_used"), "plan": result.get("plan")},
            }
        if errors:
            return {"ok": False, "summary": errors[-1].get("text","Multi-agent pipeline failed."), "data": None}
        return {"ok": False, "summary": "Multi-agent pipeline produced no result.", "data": None}
