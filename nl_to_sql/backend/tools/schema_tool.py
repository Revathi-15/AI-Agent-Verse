# schema_tool.py — Return schema + sample rows for a table

from backend.tools.base import BaseTool
from backend.database import get_schema, run_query, quote


class SchemaTool(BaseTool):
    name        = "show_schema"
    description = "Show the schema (columns + types) and a sample of rows from the active table"
    emoji       = "📋"

    def run(self, table: str, df_store: dict, n: int = 5, **kwargs) -> dict:
        if not table:
            return {"ok": False, "summary": "No table loaded.", "data": None}
        try:
            schema = get_schema(table)
            df     = run_query(f"SELECT * FROM {quote(table)} LIMIT {n}")
            return {
                "ok"     : True,
                "summary": f"Schema for **`{table}`**",
                "data"   : {
                    "schema" : schema,
                    "columns": list(df.columns),
                    "rows"   : df.to_dict(orient="records"),
                },
            }
        except Exception as e:
            return {"ok": False, "summary": f"Schema lookup failed: {e}", "data": None}
