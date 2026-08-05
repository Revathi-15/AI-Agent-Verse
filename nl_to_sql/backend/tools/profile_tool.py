# profile_tool.py — Deep dataset profiling: types, nulls, duplicates, outliers, correlations

import pandas as pd
import numpy as np
from backend.tools.base import BaseTool
from backend.database import run_query, quote


class ProfileTool(BaseTool):
    name        = "profile_dataset"
    description = "Analyse a dataset: row count, column types, null %, duplicates, numeric stats, outliers, correlations"
    emoji       = "🔍"

    def run(self, table: str, df_store: dict, **kwargs) -> dict:
        try:
            df = df_store.get(table) or run_query(f"SELECT * FROM {quote(table)}")

            real_cols = [c for c in df.columns if not c.lower().startswith("unnamed")]
            df        = df[real_cols]

            year_cols = [c for c in real_cols if c.isdigit() and len(c) == 4]
            meta_cols = [c for c in real_cols if c not in year_cols]
            num_cols  = [c for c in meta_cols if pd.api.types.is_numeric_dtype(df[c])]
            cat_cols  = [c for c in meta_cols if not pd.api.types.is_numeric_dtype(df[c])]

            # Basic stats
            nulls      = {c: round(df[c].isna().mean() * 100, 1) for c in meta_cols}
            dup_rows   = int(df.duplicated().sum())
            total      = len(df)

            # Outlier detection — IQR method on numeric columns
            outlier_cols = []
            for c in num_cols[:5]:          # limit to first 5 numeric cols
                q1, q3 = df[c].quantile(0.25), df[c].quantile(0.75)
                iqr = q3 - q1
                n   = int(((df[c] < q1 - 1.5*iqr) | (df[c] > q3 + 1.5*iqr)).sum())
                if n > 0:
                    outlier_cols.append({"col": c, "count": n})

            # Correlation — top 3 pairs from numeric columns
            top_corr = []
            if len(num_cols) >= 2:
                corr = df[num_cols[:10]].corr().abs()
                pairs = (corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
                             .stack().sort_values(ascending=False))
                for (c1, c2), v in pairs.head(3).items():
                    top_corr.append({"col1": c1, "col2": c2, "r": round(float(v), 2)})

            # Recommended questions
            rec_qs = self._recommend(table, meta_cols, num_cols, cat_cols, year_cols)

            return {
                "ok"          : True,
                "summary"     : f"Profiled **{total:,}** rows across **{len(real_cols)}** columns.",
                "data": {
                    "rows"         : total,
                    "cols"         : len(real_cols),
                    "meta_cols"    : meta_cols,
                    "num_cols"     : num_cols,
                    "cat_cols"     : cat_cols,
                    "year_range"   : f"{min(year_cols)}–{max(year_cols)}" if year_cols else None,
                    "duplicates"   : dup_rows,
                    "null_pct"     : nulls,
                    "outliers"     : outlier_cols,
                    "correlations" : top_corr,
                    "recommendations": rec_qs,
                },
            }
        except Exception as e:
            return {"ok": False, "summary": f"Profiling failed: {e}", "data": None}

    def _recommend(self, table, meta_cols, num_cols, cat_cols, year_cols):
        qs = []
        if cat_cols and num_cols:
            qs.append(f"Which {cat_cols[0]} has the highest {num_cols[0]}?")
            qs.append(f"Show top 10 {cat_cols[0]} by {num_cols[0]}")
        if cat_cols:
            qs.append(f"How many unique {cat_cols[0]} values are there?")
        if num_cols:
            qs.append(f"What is the average {num_cols[0]}?")
        if year_cols:
            best = sorted(year_cols)[-1]
            qs.append(f"Plot all {cat_cols[0] if cat_cols else 'values'} by {best}")
            qs.append(f"Which country has the highest value in {best}?")
        return qs[:6]
