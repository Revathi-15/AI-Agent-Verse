# sql_tool.py — NL → SQL → execute → return rows

import json
from backend.tools.base import BaseTool
from backend.database import get_schema, run_query, DB_PATH, quote, state
from backend.llm import generate_sql


class SQLTool(BaseTool):
    name        = "sql_query"
    description = "Convert a natural-language question to SQL, execute it, and return rows + chart data"
    emoji       = "⚙️"

    def run(self, table: str, df_store: dict, query: str = "", **kwargs) -> dict:
        if not table:
            return {"ok": False, "summary": "No table loaded.", "data": None}
        try:
            schema = get_schema(table)
            sql    = generate_sql(table, schema, query)
            df     = run_query(sql)
            state["sql"] = sql
            state["df"]  = df
            return {
                "ok"     : True,
                "sql"    : sql,
                "columns": list(df.columns),
                "rows"   : df.to_dict(orient="records"),
                "count"  : len(df),
                "summary": f"Found **{len(df)}** row(s).",
                "data"   : None,
            }
        except Exception as e:
            return {"ok": False, "summary": f"SQL failed: {e}", "data": None,
                    "sql": state.get("sql")}
