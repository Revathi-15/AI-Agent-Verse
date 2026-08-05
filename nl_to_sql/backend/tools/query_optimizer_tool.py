# query_optimizer_tool.py — SQL query analysis: cost estimate, index recs, optimisation, execution plan

import re
import sqlite3
from backend.tools.base import BaseTool
from backend.database   import DB_PATH, get_schema, quote, run_query
from backend.llm        import call_llm, generate_sql


class QueryOptimizerTool(BaseTool):
    name        = "optimize_query"
    description = "Analyse SQL for performance: estimated cost, index recommendations, optimised rewrite, execution plan"
    emoji       = "⚡"

    def run(self, table: str, df_store: dict,
            query: str = "",
            sql:   str = "",
            **kwargs) -> dict:
        """
        Args:
            query: Natural-language question (generates SQL if sql not provided).
            sql:   Existing SQL to analyse directly.
        """
        if not table:
            return {"ok": False, "summary": "No table loaded.", "data": None}

        try:
            schema = get_schema(table)

            # ── Step 1: Get or generate SQL ──────────────────────────────────
            if not sql and query:
                sql = generate_sql(table, schema, query)
            if not sql:
                return {"ok": False, "summary": "Provide a query or SQL to optimise.", "data": None}

            # ── Step 2: EXPLAIN QUERY PLAN ───────────────────────────────────
            explain_rows = []
            try:
                conn = sqlite3.connect(DB_PATH)
                plan = conn.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()
                conn.close()
                explain_rows = [
                    {"id": r[0], "parent": r[1], "notused": r[2], "detail": r[3]}
                    for r in plan
                ]
            except Exception as ep:
                explain_rows = [{"detail": f"Could not explain: {ep}"}]

            # ── Step 3: Table stats for cost estimate ────────────────────────
            try:
                count_df   = run_query(f"SELECT COUNT(*) AS n FROM {quote(table)}")
                table_rows = int(count_df.iloc[0]["n"]) if not count_df.empty else 0
            except Exception:
                table_rows = 0

            # Simple heuristic cost: does the plan use an index?
            plan_text    = " ".join(r.get("detail","") for r in explain_rows).upper()
            uses_index   = "INDEX" in plan_text or "COVERING" in plan_text
            has_full_scan= "SCAN" in plan_text and not uses_index
            complexity   = (
                "O(log n) — Index scan ✅" if uses_index
                else "O(n) — Full table scan ⚠️"
            )

            # ── Step 4: LLM deep analysis ────────────────────────────────────
            llm_prompt = f"""You are a SQL performance expert for SQLite.

Table: "{table}"  |  Rows: {table_rows:,}
Schema:
{schema}

SQL to analyse:
{sql}

EXPLAIN QUERY PLAN output:
{chr(10).join(r.get("detail","") for r in explain_rows)}

Provide ALL of the following:

**⚡ Optimised SQL**
Rewrite the SQL to be faster (better WHERE clauses, avoid SELECT *, etc.).
Show only the SQL in a code block.

**📊 Cost Analysis**
- Table size: {table_rows:,} rows
- Scan type: {complexity}
- Estimated relative cost: low/medium/high

**🗂️ Index Recommendations**
List specific CREATE INDEX statements that would speed this up most.

**💡 Tips**
3 bullet points of practical optimisation tips for this specific query.

**⚠️ Potential Issues**
Any SQL anti-patterns, edge cases, or bugs you notice.

Be concise and specific. Use code blocks for SQL."""

            analysis = call_llm(llm_prompt, max_tokens=700, temperature=0.2)

            return {
                "ok"     : True,
                "summary": f"⚡ Query analysis complete — {complexity}",
                "sql"    : sql,
                "data"   : {
                    "original_sql"   : sql,
                    "explain_plan"   : explain_rows,
                    "table_rows"     : table_rows,
                    "uses_index"     : uses_index,
                    "has_full_scan"  : has_full_scan,
                    "complexity"     : complexity,
                    "llm_analysis"   : analysis,
                },
                "columns": ["detail"],
                "rows"   : explain_rows,
            }

        except Exception as e:
            return {"ok": False, "summary": f"Optimisation failed: {e}", "data": None}
