# insights_tool.py — Proactive AI insight discovery: trends, anomalies, top/bottom, correlations

import pandas as pd
import numpy as np
from backend.tools.base import BaseTool
from backend.database import run_query, quote
from backend.llm import call_llm


class InsightsTool(BaseTool):
    name        = "discover_insights"
    description = "Proactively discover trends, anomalies, top/bottom performers, and business insights from the dataset"
    emoji       = "💡"

    def run(self, table: str, df_store: dict, **kwargs) -> dict:
        try:
            df = df_store.get(table) or run_query(f"SELECT * FROM {quote(table)}")

            real_cols = [c for c in df.columns if not c.lower().startswith("unnamed")]
            df        = df[real_cols]
            year_cols = sorted([c for c in real_cols if c.isdigit() and len(c) == 4])
            meta_cols = [c for c in real_cols if c not in year_cols]
            num_cols  = [c for c in meta_cols if pd.api.types.is_numeric_dtype(df[c])]
            cat_cols  = [c for c in meta_cols if not pd.api.types.is_numeric_dtype(df[c])]

            facts = []

            # Top / bottom performers
            if cat_cols and num_cols:
                cat, num = cat_cols[0], num_cols[0]
                top    = df.nlargest(1, num)[[cat, num]].iloc[0]
                bottom = df.nsmallest(1, num)[[cat, num]].iloc[0]
                facts.append(f"**Top {cat}:** {top[cat]} ({num}: {top[num]:,.0f})")
                facts.append(f"**Bottom {cat}:** {bottom[cat]} ({num}: {bottom[num]:,.0f})")

            # Year-over-year trend (last 2 years)
            if year_cols and len(year_cols) >= 2 and cat_cols:
                y1, y2   = year_cols[-2], year_cols[-1]
                df2      = df[[cat_cols[0], y1, y2]].dropna()
                if not df2.empty:
                    df2["change"] = ((df2[y2] - df2[y1]) / df2[y1].replace(0, np.nan)) * 100
                    fastest = df2.nlargest(1, "change").iloc[0]
                    facts.append(
                        f"**Fastest growth ({y1}→{y2}):** {fastest[cat_cols[0]]} "
                        f"(+{fastest['change']:.1f}%)"
                    )
                    declining = df2[df2["change"] < 0]
                    if not declining.empty:
                        facts.append(f"**{len(declining)}** entr{'y' if len(declining)==1 else 'ies'} declined from {y1} to {y2}")

            # Null hotspots
            high_null = {c: round(df[c].isna().mean()*100, 1)
                         for c in meta_cols if df[c].isna().mean() > 0.3}
            if high_null:
                cols_str = ", ".join(f"{c} ({v}%)" for c, v in high_null.items())
                facts.append(f"**High null %:** {cols_str}")

            # Distribution spread
            if num_cols:
                c   = num_cols[0]
                std = df[c].std()
                mn  = df[c].mean()
                cv  = round(std/mn*100, 1) if mn else 0
                facts.append(f"**{c} spread:** mean {mn:,.0f}, CV {cv}% — {'high' if cv > 50 else 'moderate'} variability")

            # Ask LLM to write 3 bullet narrative insights
            narrative = self._llm_narrative(table, facts, cat_cols, num_cols, year_cols, df)

            return {
                "ok"     : True,
                "summary": f"Discovered **{len(facts)}** data insights.",
                "data"   : {
                    "facts"    : facts,
                    "narrative": narrative,
                },
            }
        except Exception as e:
            return {"ok": False, "summary": f"Insight discovery failed: {e}", "data": None}

    def _llm_narrative(self, table, facts, cat_cols, num_cols, year_cols, df):
        # Brief LLM call to turn raw facts into readable business insights
        facts_str = "\n".join(f"- {f}" for f in facts)
        prompt = (
            f"You are a data analyst. Given these facts about the '{table}' dataset:\n"
            f"{facts_str}\n\n"
            f"Write exactly 3 concise business insight bullet points (each ≤ 20 words). "
            f"Start each with a relevant emoji. No preamble."
        )
        try:
            return call_llm(prompt, max_tokens=200)
        except Exception:
            return "\n".join(f"• {f}" for f in facts[:3])
