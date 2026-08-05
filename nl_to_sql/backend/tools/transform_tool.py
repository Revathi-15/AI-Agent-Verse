# transform_tool.py — Natural language data transformations: filter, rename, merge, create columns

import sqlite3
import pandas as pd
from backend.tools.base import BaseTool
from backend.database import run_query, quote, DB_PATH, DATA_DIR, state
from backend.llm import call_llm
import os


class TransformTool(BaseTool):
    name        = "transform_data"
    description = "Transform data using natural language: filter rows, rename columns, create new columns, merge tables"
    emoji       = "🔀"

    def run(self, table: str, df_store: dict, instruction: str = "", **kwargs) -> dict:
        if not table:
            return {"ok": False, "summary": "No table loaded.", "data": None}
        try:
            df     = df_store.get(table) or run_query(f"SELECT * FROM {quote(table)}")
            schema = "\n".join(f"  {c} ({df[c].dtype})" for c in df.columns)

            # Ask LLM to generate pandas code for the transformation
            prompt = f"""You are a Python/pandas expert. Transform a DataFrame using this instruction.

DataFrame name: df
Columns and types:
{schema}

Instruction: "{instruction}"

Rules:
- Write ONLY valid Python code using pandas
- The result must be stored in a variable called `result_df`
- Do NOT import anything — pandas is already imported as pd
- Do NOT use exec or eval inside the code
- Keep it safe: no file I/O, no subprocess, no os calls
- If the instruction is unclear, do a reasonable interpretation

Example output format:
result_df = df[df["column"] > 100]

Code:"""

            code = call_llm(prompt, max_tokens=300, temperature=0)
            # Strip markdown fences
            for fence in ("```python", "```"):
                code = code.replace(fence, "")
            code = code.strip()

            # Execute safely with restricted globals
            safe_globals = {"pd": pd, "df": df.copy()}
            exec(code, safe_globals)          # nosec — LLM output, sandboxed globals
            result_df = safe_globals.get("result_df")

            if result_df is None or not isinstance(result_df, pd.DataFrame):
                return {"ok": False,
                        "summary": "Transformation produced no DataFrame.",
                        "data": {"code": code}}

            # Save to SQLite
            new_table = f"{table}_transformed"
            conn = sqlite3.connect(DB_PATH)
            result_df.to_sql(new_table, conn, if_exists="replace", index=False)
            conn.close()

            # Save CSV
            out = os.path.join(DATA_DIR, f"{new_table}.csv")
            result_df.to_csv(out, index=False)
            df_store[new_table] = result_df
            state["table"] = new_table

            return {
                "ok"       : True,
                "new_table": new_table,
                "summary"  : f"Transformed → **`{new_table}`** ({len(result_df):,} rows, {len(result_df.columns)} cols)",
                "data"     : {
                    "code"     : code,
                    "columns"  : list(result_df.columns),
                    "rows"     : result_df.head(10).to_dict(orient="records"),
                    "new_table": new_table,
                },
            }
        except Exception as e:
            return {"ok": False, "summary": f"Transform failed: {e}", "data": None}
