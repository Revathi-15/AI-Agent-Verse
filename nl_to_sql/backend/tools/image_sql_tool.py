# image_sql_tool.py — Image-to-SQL: upload a dashboard screenshot, AI infers metrics + SQL

import base64
import os
from backend.tools.base import BaseTool
from backend.database   import get_schema, run_query, state
from backend.llm        import call_llm, generate_sql

_ENV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"
)
from dotenv import load_dotenv
load_dotenv(_ENV)

PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()


def _vision_describe(image_b64: str, image_mime: str = "image/png") -> str:
    """Send image to vision-capable LLM and extract described metrics/filters."""
    if PROVIDER == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "This is a screenshot of a data dashboard or chart. "
                            "Analyse it carefully and extract:\n"
                            "1. What metrics or KPIs are shown (names + approximate values).\n"
                            "2. What filters or dimensions are visible (time range, categories, etc.).\n"
                            "3. What SQL query would reproduce this data from a database table.\n"
                            "4. What chart type(s) are used.\n\n"
                            "Format your response as:\n"
                            "METRICS: ...\n"
                            "FILTERS: ...\n"
                            "SQL_HINT: ...\n"
                            "CHART_TYPES: ...\n"
                            "DESCRIPTION: ..."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image_mime};base64,{image_b64}",
                            "detail": "high",
                        },
                    },
                ],
            }],
        )
        return resp.choices[0].message.content.strip()

    elif PROVIDER == "claude":
        from anthropic import Anthropic
        client = Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))
        resp = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_mime,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Analyse this dashboard screenshot. Extract:\n"
                            "1. Metrics/KPIs shown\n2. Filters/dimensions\n"
                            "3. SQL query hint to reproduce this data\n4. Chart types used\n\n"
                            "Format: METRICS: ...\nFILTERS: ...\nSQL_HINT: ...\n"
                            "CHART_TYPES: ...\nDESCRIPTION: ..."
                        ),
                    },
                ],
            }],
        )
        return resp.content[0].text.strip()

    elif PROVIDER == "gemini":
        from google import genai
        from google.genai import types as gtypes
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        image_bytes = base64.b64decode(image_b64)
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                gtypes.Part.from_bytes(data=image_bytes, mime_type=image_mime),
                "Analyse this dashboard. Extract METRICS, FILTERS, SQL_HINT, CHART_TYPES, DESCRIPTION.",
            ],
        )
        return resp.text.strip()

    return "Vision analysis not available for this provider."


def _parse_vision_output(raw: str) -> dict:
    """Parse structured vision output into a dict."""
    result = {"metrics": "", "filters": "", "sql_hint": "", "chart_types": "", "description": ""}
    for line in raw.splitlines():
        line = line.strip()
        for key in result:
            prefix = key.upper().replace("_", " ") + ":"
            alt    = key.upper() + ":"
            if line.startswith(prefix) or line.startswith(alt):
                result[key] = line.split(":", 1)[1].strip()
    return result


class ImageToSQLTool(BaseTool):
    name        = "image_to_sql"
    description = "Upload a dashboard screenshot — AI infers the metrics, filters, and SQL needed to recreate it"
    emoji       = "🖼️"

    def run(self, table: str, df_store: dict,
            image_b64:  str = "",
            image_mime: str = "image/png",
            image_path: str = "",
            **kwargs) -> dict:
        """
        Args:
            image_b64:  Base64-encoded image string.
            image_mime: MIME type (image/png, image/jpeg, etc.).
            image_path: Local file path (alternative to base64).
        """
        if not image_b64 and image_path:
            if not os.path.exists(image_path):
                return {"ok": False, "summary": f"Image not found: {image_path}", "data": None}
            ext = os.path.splitext(image_path)[1].lower()
            image_mime = {"png":"image/png","jpg":"image/jpeg",
                          "jpeg":"image/jpeg","gif":"image/gif",
                          "webp":"image/webp"}.get(ext.lstrip("."), "image/png")
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode()

        if not image_b64:
            return {"ok": False, "summary": "Provide an image (base64 or file path).", "data": None}

        try:
            # ── Vision analysis ─────────────────────────────────────────────
            raw      = _vision_describe(image_b64, image_mime)
            parsed   = _parse_vision_output(raw)

            # ── Generate actual SQL from table schema + vision hints ─────────
            sql_hint = parsed.get("sql_hint", "")
            metrics  = parsed.get("metrics", "")
            filters  = parsed.get("filters", "")

            schema = get_schema(table)
            nl_query = (
                f"Based on this dashboard analysis:\n"
                f"Metrics: {metrics}\nFilters: {filters}\n"
                f"SQL hint: {sql_hint}\n\n"
                f"Write a SQL query to recreate this data from table '{table}'."
            )
            sql = generate_sql(table, schema, nl_query)

            # ── Execute the generated SQL ────────────────────────────────────
            rows, columns = [], []
            try:
                df       = run_query(sql)
                state["sql"] = sql
                state["df"]  = df
                rows    = df.to_dict(orient="records")
                columns = list(df.columns)
            except Exception as eq:
                sql = f"-- SQL generation attempted but execution failed: {eq}\n{sql}"

            # ── Determine chart types ────────────────────────────────────────
            chart_hint = parsed.get("chart_types", "bar").lower()
            chart_type = "bar"
            for ct in ("line", "pie", "scatter", "histogram", "bar"):
                if ct in chart_hint:
                    chart_type = ct
                    break

            return {
                "ok"        : True,
                "summary"   : (
                    f"🖼️ Dashboard analysed!\n\n"
                    f"**Metrics detected:** {metrics or 'N/A'}\n"
                    f"**Filters:** {filters or 'N/A'}\n"
                    f"**Chart types:** {parsed.get('chart_types','N/A')}\n\n"
                    f"**Description:** {parsed.get('description','')}"
                ),
                "sql"       : sql,
                "columns"   : columns,
                "rows"      : rows,
                "chart_type": chart_type,
                "data"      : {
                    "vision_raw"  : raw,
                    "parsed"      : parsed,
                    "generated_sql": sql,
                },
            }

        except Exception as e:
            return {"ok": False, "summary": f"Image analysis failed: {e}", "data": None}
