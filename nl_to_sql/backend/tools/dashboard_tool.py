# dashboard_tool.py — Auto dashboard builder: generates multi-chart layout config from description

import pandas as pd
from backend.tools.base import BaseTool
from backend.database import run_query, quote, get_schema
from backend.llm import generate_sql, call_llm


class DashboardTool(BaseTool):
    name        = "build_dashboard"
    description = "Auto-generate a multi-panel dashboard: KPI cards, bar chart, line chart, pie chart from one description"
    emoji       = "📊"

    def run(self, table: str, df_store: dict, description: str = "", **kwargs) -> dict:
        if not table:
            return {"ok": False, "summary": "No table loaded.", "data": None}
        try:
            df     = df_store.get(table) or run_query(f"SELECT * FROM {quote(table)}")
            schema = get_schema(table)

            real_cols = [c for c in df.columns if not c.lower().startswith("unnamed")]
            df        = df[real_cols]
            year_cols = sorted([c for c in real_cols if c.isdigit() and len(c) == 4])
            meta_cols = [c for c in real_cols if c not in year_cols]
            num_cols  = [c for c in meta_cols if pd.api.types.is_numeric_dtype(df[c])]
            cat_cols  = [c for c in meta_cols if not pd.api.types.is_numeric_dtype(df[c])]
            best_year = year_cols[-1] if year_cols else None

            panels = []

            # Panel 1: KPI cards — top 3 stats
            kpis = []
            if cat_cols and (num_cols or year_cols):
                val_col = num_cols[0] if num_cols else best_year
                if val_col:
                    top1 = df.nlargest(1, val_col).iloc[0]
                    kpis.append({"label": f"Top {cat_cols[0]}", "value": str(top1[cat_cols[0]]),
                                 "sub": f"{val_col}: {top1[val_col]:,.0f}"})
            if num_cols or best_year:
                val_col = num_cols[0] if num_cols else best_year
                if val_col:
                    avg = df[val_col].mean()
                    kpis.append({"label": f"Avg {val_col}", "value": f"{avg:,.0f}", "sub": "mean"})
                    kpis.append({"label": f"Total rows", "value": f"{len(df):,}", "sub": "dataset size"})

            if kpis:
                panels.append({"type": "kpi", "title": "Key Metrics", "data": kpis})

            # Panel 2: Bar chart — top 15 by latest value
            if cat_cols and (num_cols or best_year):
                val_col = num_cols[0] if num_cols else best_year
                bar_df  = df[[cat_cols[0], val_col]].dropna().nlargest(15, val_col)
                panels.append({
                    "type"   : "bar",
                    "title"  : f"Top 15 {cat_cols[0]} by {val_col}",
                    "x_col"  : cat_cols[0],
                    "y_col"  : val_col,
                    "columns": [cat_cols[0], val_col],
                    "rows"   : bar_df.to_dict(orient="records"),
                })

            # Panel 3: Line chart — trend of top entity over years
            if year_cols and cat_cols:
                top_entity = df.nlargest(1, year_cols[-1])[cat_cols[0]].iloc[0]
                row = df[df[cat_cols[0]] == top_entity].iloc[0]
                trend_rows = [{"Year": y, "Value": row[y]}
                              for y in year_cols if pd.notna(row.get(y))]
                if trend_rows:
                    panels.append({
                        "type"   : "line",
                        "title"  : f"{top_entity} — trend over time",
                        "x_col"  : "Year",
                        "y_col"  : "Value",
                        "columns": ["Year", "Value"],
                        "rows"   : trend_rows,
                    })

            # Panel 4: Pie chart — top 8 share
            if cat_cols and (num_cols or best_year):
                val_col  = num_cols[0] if num_cols else best_year
                pie_df   = df[[cat_cols[0], val_col]].dropna().nlargest(8, val_col)
                total    = pie_df[val_col].sum()
                pie_rows = pie_df.to_dict(orient="records")
                panels.append({
                    "type"   : "pie",
                    "title"  : f"Share of {val_col} — top 8",
                    "label_col": cat_cols[0],
                    "value_col": val_col,
                    "columns"  : [cat_cols[0], val_col],
                    "rows"     : pie_rows,
                })

            # LLM summary
            try:
                summary = call_llm(
                    f"Write a 2-sentence executive summary for a dashboard about '{table}' "
                    f"with {len(df)} rows, columns {meta_cols[:4]}. Be concise.",
                    max_tokens=100, temperature=0.4,
                )
            except Exception:
                summary = f"Dashboard for **{table}** — {len(df):,} rows, {len(panels)} panels."

            return {
                "ok"     : True,
                "summary": summary,
                "data"   : {"panels": panels, "table": table},
            }
        except Exception as e:
            return {"ok": False, "summary": f"Dashboard build failed: {e}", "data": None}
