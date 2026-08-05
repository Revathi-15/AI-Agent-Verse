# tutor_tool.py — SQL Tutor: generate SQL + explain it + alternatives + optimisation tips

from backend.tools.base import BaseTool
from backend.database import get_schema, run_query, quote, state
from backend.llm import generate_sql, call_llm


class SQLTutorTool(BaseTool):
    name        = "sql_tutor"
    description = "Teach SQL: generate query + plain-English explanation + alternative approaches + optimisation tips"
    emoji       = "🎓"

    def run(self, table: str, df_store: dict, query: str = "", **kwargs) -> dict:
        if not table:
            return {"ok": False, "summary": "No table loaded.", "data": None}
        try:
            schema = get_schema(table)
            sql    = generate_sql(table, schema, query)

            # Run the query
            df = run_query(sql)
            state["sql"] = sql
            state["df"]  = df

            # Ask LLM for full tutor response
            tutor_prompt = f"""You are an expert SQL tutor teaching a student.

The student asked: "{query}"
Table: "{table}"
Schema:
{schema}

Generated SQL:
{sql}

Provide a structured response with these exact sections:

**📖 Explanation**
Explain in plain English what this SQL does, clause by clause.

**🔄 Alternative Approach**
Show one alternative way to write this query (if applicable).

**⚡ Optimisation Tips**
List 2-3 tips to make this query faster or more efficient.

**📊 Query Analysis**
- Estimated complexity: O(n) / O(n log n) / O(n²)
- Indexes that would help: list column names
- Potential issues: any warnings

Keep each section concise. Use code blocks for SQL."""

            tutor_text = call_llm(tutor_prompt, max_tokens=600, temperature=0.3)

            return {
                "ok"      : True,
                "summary" : f"SQL Tutor analysis for: \"{query}\"",
                "sql"     : sql,
                "columns" : list(df.columns),
                "rows"    : df.to_dict(orient="records"),
                "count"   : len(df),
                "data"    : {"tutor_text": tutor_text},
            }
        except Exception as e:
            return {"ok": False, "summary": f"Tutor failed: {e}", "data": None}
