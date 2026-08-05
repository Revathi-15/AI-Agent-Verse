# clean_tool.py — Automated data cleaning: duplicates, nulls, types, standardisation

import sqlite3
import pandas as pd
import numpy as np
from backend.tools.base import BaseTool
from backend.database import run_query, quote, DB_PATH, DATA_DIR
import os


class CleanTool(BaseTool):
    name        = "clean_data"
    description = "Clean a dataset: remove duplicates, fill nulls, fix types, standardise categories, generate report"
    emoji       = "🧹"

    def run(self, table: str, df_store: dict, **kwargs) -> dict:
        try:
            df      = df_store.get(table) or run_query(f"SELECT * FROM {quote(table)}")
            orig_n  = len(df)
            report  = []

            # 1. Drop fully-empty unnamed columns
            junk = [c for c in df.columns if c.lower().startswith("unnamed") and df[c].isna().all()]
            if junk:
                df.drop(columns=junk, inplace=True)
                report.append(f"Dropped {len(junk)} empty column(s): {junk}")

            # 2. Remove duplicate rows
            n_dup = df.duplicated().sum()
            if n_dup:
                df.drop_duplicates(inplace=True)
                report.append(f"Removed **{n_dup}** duplicate row(s)")

            # 3. Numeric columns — fill nulls with median
            num_cols  = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
            year_cols = [c for c in num_cols if c.isdigit() and len(c) == 4]
            fill_cols = [c for c in num_cols if c not in year_cols]
            filled = 0
            for c in fill_cols:
                n_null = df[c].isna().sum()
                if n_null:
                    df[c].fillna(df[c].median(), inplace=True)
                    filled += n_null
            if filled:
                report.append(f"Filled **{filled}** null(s) in numeric columns with median")

            # 4. String columns — strip whitespace, standardise case
            str_cols = [c for c in df.columns
                        if df[c].dtype == object and c not in year_cols]
            for c in str_cols:
                df[c] = df[c].astype(str).str.strip()
            if str_cols:
                report.append(f"Stripped whitespace in {len(str_cols)} text column(s)")

            # 5. Save cleaned table back to SQLite
            clean_table = f"{table}_cleaned"
            conn = sqlite3.connect(DB_PATH)
            df.to_sql(clean_table, conn, if_exists="replace", index=False)
            conn.close()

            # 6. Save as CSV
            out_path = os.path.join(DATA_DIR, f"{clean_table}.csv")
            df.to_csv(out_path, index=False)

            df_store[clean_table] = df

            return {
                "ok"          : True,
                "clean_table" : clean_table,
                "summary"     : f"Cleaned dataset saved as **`{clean_table}`** ({len(df):,} rows).",
                "data": {
                    "original_rows" : orig_n,
                    "clean_rows"    : len(df),
                    "report"        : report,
                    "clean_table"   : clean_table,
                    "download_name" : f"{clean_table}.csv",
                },
            }
        except Exception as e:
            return {"ok": False, "summary": f"Cleaning failed: {e}", "data": None}
