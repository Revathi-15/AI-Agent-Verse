# backend/llm.py — Multi-provider LLM client for SQL generation
#
# Switch provider by changing ONE line in .env:
#   LLM_PROVIDER=openai    →  gpt-4o-mini
#   LLM_PROVIDER=claude    →  claude-3-5-haiku-20241022
#   LLM_PROVIDER=gemini    →  gemini-2.0-flash

import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()

_MODELS = {
    "openai": "gpt-4o-mini",
    "claude": "claude-3-5-haiku-20241022",
    "gemini": "gemini-2.0-flash",
}

if PROVIDER not in _MODELS:
    raise ValueError(f"Unknown LLM_PROVIDER='{PROVIDER}'. Choose: {', '.join(_MODELS)}")

MODEL = _MODELS[PROVIDER]

# Build the correct client
_client = None

if PROVIDER == "openai":
    from openai import OpenAI
    _key = os.getenv("OPENAI_API_KEY")
    if not _key:
        raise RuntimeError("OPENAI_API_KEY missing in .env")
    _client = OpenAI(api_key=_key)

elif PROVIDER == "claude":
    from anthropic import Anthropic
    _key = os.getenv("CLAUDE_API_KEY")
    if not _key:
        raise RuntimeError("CLAUDE_API_KEY missing in .env")
    _client = Anthropic(api_key=_key)

elif PROVIDER == "gemini":
    from google import genai
    _key = os.getenv("GEMINI_API_KEY")
    if not _key:
        raise RuntimeError("GEMINI_API_KEY missing in .env")
    _client = genai.Client(api_key=_key)


def _build_prompt(table_name: str, schema: str, question: str) -> str:
    # Detailed prompt — handles both normal and wide-format (year-column) tables
    return f"""You are an expert SQLite SQL generator. Your job is to write ONE correct SQL query.

TABLE: "{table_name}"
SCHEMA:
{schema}

CRITICAL RULES:
1. Return ONLY the raw SQL — no markdown, no explanation, no comments.
2. Wrap ALL table and column names in double-quotes.
3. Use only SQLite-compatible syntax.
4. Never use LIMIT unless the user explicitly asks for "top N" or a specific count.
5. For wide-format tables with year columns (e.g. "2020", "2019"...):
   - To get the highest/lowest value: ORDER BY the most recent year column DESC/ASC
   - To get all countries' values: SELECT "Country Name", "<year>" FROM table
   - NEVER select all 60+ year columns unless asked — pick the most relevant year
   - If user says "GDP" without specifying year, use the most recent year with data shown in schema
6. Ignore any column that starts with "Unnamed" — it is empty junk.
7. For aggregations (average, sum, count), cast year columns: CAST("<year>" AS REAL)
8. If user asks to "show all" or "visualise all countries", select "Country Name" and the best year column only.

User question: \"\"\"{question}\"\"\"

SQL:"""


def _clean(sql: str) -> str:
    # Strip accidental markdown fences
    for fence in ("```sql", "```"):
        sql = sql.replace(fence, "")
    return sql.strip()


def generate_sql(table_name: str, schema: str, user_question: str) -> str:
    # Convert natural language to SQLite SQL using the configured provider
    prompt = _build_prompt(table_name, schema, user_question)

    if PROVIDER == "openai":
        resp = _client.chat.completions.create(
            model=MODEL, temperature=0, max_tokens=500,
            messages=[
                {"role": "system", "content": "You are a SQLite expert. Return ONLY raw SQL. No markdown, no explanation."},
                {"role": "user",   "content": prompt},
            ],
        )
        return _clean(resp.choices[0].message.content)

    elif PROVIDER == "claude":
        resp = _client.messages.create(
            model=MODEL, max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        return _clean(resp.content[0].text)

    elif PROVIDER == "gemini":
        resp = _client.models.generate_content(model=MODEL, contents=prompt)
        return _clean(resp.text)


def active_provider() -> str:
    # Human-readable label shown in the UI header
    return {"openai": "OpenAI", "claude": "Claude", "gemini": "Gemini"}[PROVIDER] + f" ({MODEL})"


def call_llm(prompt: str, max_tokens: int = 400, temperature: float = 0.3) -> str:
    """Generic LLM call — used by orchestrator and insights tool."""
    if PROVIDER == "openai":
        resp = _client.chat.completions.create(
            model=MODEL, temperature=temperature, max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    elif PROVIDER == "claude":
        resp = _client.messages.create(
            model=MODEL, max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    elif PROVIDER == "gemini":
        resp = _client.models.generate_content(model=MODEL, contents=prompt)
        return resp.text.strip()
    return ""
