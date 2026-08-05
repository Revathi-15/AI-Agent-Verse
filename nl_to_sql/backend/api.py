# backend/api.py — FastAPI: all routes for NL-to-SQL enterprise platform

import json, io, os, base64, sqlite3, time
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional

from backend.database import (
    state, get_schema, all_tables, get_profile,
    run_query, quote, DB_PATH, DATA_DIR,
    log_audit, log_feedback, get_audit_log,
    get_feedback_stats, ensure_all_tables,
    has_permission, get_user, upsert_user, list_users,
    list_connections, save_connection, query_live_connection,
    ROLE_PERMISSIONS,
)
from backend.tools import all_tools
from sql import csv_to_sqlite

app = FastAPI(title="NL-to-SQL Enterprise API", version="5.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# Ensure all system tables exist at startup
ensure_all_tables()


# ── Pydantic models ───────────────────────────────────────────────────────────
class UploadRequest(BaseModel):
    filename:         str
    file_content_b64: Optional[str] = None
    file_path:        Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    table:   Optional[str] = None
    mode:    Optional[str] = "chat"

class ChatResponse(BaseModel):
    reply:      str
    sql:        Optional[str]  = None
    columns:    Optional[list] = None
    rows:       Optional[list] = None
    error:      Optional[str]  = None
    chart_type: Optional[str]  = None
    extras:     Optional[dict] = None

class FeedbackRequest(BaseModel):
    query:   str
    sql:     Optional[str] = None
    rating:  int
    comment: Optional[str] = None

class StreamRequest(BaseModel):
    message: str
    table:   Optional[str] = None

class EmailRequest(BaseModel):
    to:      str
    subject: Optional[str] = "NL→SQL Report"
    body:    Optional[str] = ""

class ScheduleRequest(BaseModel):
    query:       str
    recipient:   str
    frequency:   Optional[str] = "weekly"
    day_of_week: Optional[str] = "monday"
    run_time:    Optional[str] = "08:00"
    name:        Optional[str] = ""
    action:      Optional[str] = "create"
    job_id:      Optional[int] = None

class ImageSQLRequest(BaseModel):
    image_b64:  str
    image_mime: Optional[str] = "image/png"

class UserRequest(BaseModel):
    username: str
    role:     str
    email:    Optional[str] = ""

class ConnectionRequest(BaseModel):
    name:     str
    db_type:  str
    host:     Optional[str] = ""
    port:     Optional[int] = 5432
    database: Optional[str] = ""
    username: Optional[str] = ""
    password: Optional[str] = ""
    extra:    Optional[dict] = None

class VoiceRequest(BaseModel):
    audio_b64:  str
    audio_mime: Optional[str] = "audio/webm"

class VectorSearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5

class OptimizeRequest(BaseModel):
    query: Optional[str] = ""
    sql:   Optional[str] = ""


# ── Core helpers ──────────────────────────────────────────────────────────────
def _ensure_table(table: Optional[str]) -> Optional[str]:
    if table and table in all_tables():
        state["table"] = table
        return table
    if not state["table"]:
        tbls = all_tables()
        if tbls:
            state["table"] = tbls[0]
    return state["table"]


def _load_df(table: str):
    if table not in state["df_store"]:
        state["df_store"][table] = run_query(f"SELECT * FROM {quote(table)}")
    return state["df_store"][table]


def _interpret(user_question: str, sql: str, rows: list, columns: list) -> str:
    from backend.llm import call_llm
    if not rows:
        return "The query returned no results."
    sample   = rows[:20]
    data_str = "\n".join(
        ", ".join(f"{c}: {r.get(c, '')}" for c in columns) for r in sample
    )
    more   = f"\n...and {len(rows)-20} more rows." if len(rows) > 20 else ""
    prompt = (
        f"You are a data analyst. The user asked: \"{user_question}\"\n\n"
        f"SQL: {sql}\n\nResults ({len(rows)} rows):\n{data_str}{more}\n\n"
        f"Write a clear, concise natural-language answer. Include key numbers. "
        f"Use bullet points for lists. Do NOT repeat the SQL. Under 120 words."
    )
    try:
        return call_llm(prompt, max_tokens=250, temperature=0.4)
    except Exception:
        if len(rows) == 1 and len(columns) <= 2:
            vals = list(rows[0].values())
            return f"**{vals[0]}**: {vals[-1]}" if len(vals) == 2 else str(vals[0])
        return f"Found **{len(rows)}** result(s)."


def _decide_chart(user_question: str, columns: list, row_count: int) -> str:
    from backend.llm import call_llm
    if row_count <= 1:
        return "none"
    prompt = (
        f"User question: \"{user_question}\"\n"
        f"Result: {row_count} rows, columns: {columns}\n"
        f"Pick ONE chart: bar, line, scatter, histogram, pie, none\n"
        f"Rules: line for trends/growth/time; bar for rankings/top-N; "
        f"pie for shares/percentages (≤10 rows); scatter for correlation; "
        f"histogram for distribution; none for single values or schema.\n"
        f"Reply with ONE word only."
    )
    try:
        r = call_llm(prompt, max_tokens=5, temperature=0).strip().lower().split()[0]
        return r if r in ("bar", "line", "scatter", "histogram", "pie", "none") else "bar"
    except Exception:
        return "bar" if row_count > 1 else "none"


def _handle_growth_query(msg: str, table: str):
    try:
        conn   = sqlite3.connect(DB_PATH)
        pragma = conn.execute(f"PRAGMA table_info({quote(table)})").fetchall()
        conn.close()
        col_names = [r[1] for r in pragma]
        year_cols = sorted([c for c in col_names if c.isdigit() and len(c) == 4])
        cat_cols  = [c for c in col_names if not c.isdigit()
                     and not c.lower().startswith("unnamed")]
        if not year_cols or not cat_cols:
            return None
        best_year = year_cols[-1]
        cat_col   = cat_cols[0]
        top_df = run_query(
            f'SELECT {quote(cat_col)}, {quote(best_year)} FROM {quote(table)} '
            f'WHERE {quote(best_year)} IS NOT NULL '
            f'ORDER BY CAST({quote(best_year)} AS REAL) DESC LIMIT 1'
        )
        if top_df.empty:
            return None
        entity   = top_df.iloc[0][cat_col]
        year_sel = ", ".join(f"{quote(y)}" for y in year_cols)
        row_df   = run_query(
            f'SELECT {year_sel} FROM {quote(table)} '
            f'WHERE {quote(cat_col)} = "{entity}"'
        )
        if row_df.empty:
            return None
        import pandas as pd
        long_df = pd.DataFrame({
            "Year" : year_cols,
            "Value": [row_df.iloc[0][y] for y in year_cols],
        }).dropna(subset=["Value"])
        long_df["Value"] = pd.to_numeric(long_df["Value"], errors="coerce")
        long_df = long_df.dropna()
        return entity, long_df
    except Exception:
        return None


def _store_to_vector(query: str, sql: str, reply: str, table: str, rows: int):
    """Persist query to vector store for semantic search (fire-and-forget)."""
    try:
        from backend.tools.vector_db_tool import store_query
        store_query(query, sql, reply, table, rows)
    except Exception:
        pass


# ── Health & info ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    from backend.llm import active_provider
    return {
        "status"      : "ok",
        "tables"      : all_tables(),
        "active_table": state["table"],
        "llm"         : active_provider(),
        "current_user": state.get("current_user", "admin"),
        "current_role": state.get("current_role", "admin"),
        "tools"       : {n: {"desc": t.description, "emoji": t.emoji}
                         for n, t in all_tools().items()},
        "connections" : [c["name"] for c in list_connections()],
    }


@app.get("/profile")
def profile():
    t = _ensure_table(None)
    if not t:
        return {"error": "No table loaded"}
    _load_df(t)
    tool = all_tools().get("profile_dataset")
    return tool.run(table=t, df_store=state["df_store"]) if tool else get_profile(t)


@app.get("/audit")
def audit(limit: int = 50):
    return {"entries": get_audit_log(limit)}


@app.get("/feedback/stats")
def feedback_stats():
    return get_feedback_stats()


# ── Permissions / users ───────────────────────────────────────────────────────
@app.get("/users")
def get_users():
    return {"users": list_users()}


@app.post("/users")
def create_user(req: UserRequest):
    try:
        result = upsert_user(req.username, req.role, req.email or "")
        return {"ok": True, "user": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/login")
def login(req: UserRequest):
    """Simple username-based login (no password for demo — add auth in production)."""
    user = get_user(req.username)
    if not user:
        # Auto-create with viewer role
        upsert_user(req.username, "viewer", req.email or "")
        user = get_user(req.username)
    state["current_user"] = user["username"]
    state["current_role"] = user["role"]
    from backend.database import touch_user
    touch_user(req.username)
    return {
        "ok"         : True,
        "username"   : user["username"],
        "role"       : user["role"],
        "permissions": list(ROLE_PERMISSIONS.get(user["role"], set())),
    }


# ── Live DB connections ───────────────────────────────────────────────────────
@app.get("/connections")
def get_connections():
    return {"connections": list_connections()}


@app.post("/connections")
def add_connection(req: ConnectionRequest):
    cid = save_connection(
        req.name, req.db_type, req.host or "", req.port or 5432,
        req.database or "", req.username or "", req.password or "",
        req.extra,
    )
    return {"ok": True, "id": cid, "name": req.name}


@app.post("/connections/{name}/query")
def query_connection(name: str, req: ChatRequest):
    try:
        from backend.llm import generate_sql
        # Get schema from live DB
        df  = query_live_connection(name, "SELECT * FROM information_schema.tables LIMIT 1")
        sql = req.message  # For live DBs user can pass raw SQL or NL (basic support)
        df  = query_live_connection(name, sql)
        rows = df.to_dict(orient="records")
        cols = list(df.columns)
        return ChatResponse(
            reply=f"Live query returned **{len(rows)}** row(s).",
            sql=sql, columns=cols, rows=rows,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Upload CSV ────────────────────────────────────────────────────────────────
@app.post("/upload")
def upload(req: UploadRequest):
    target = os.path.join(DATA_DIR, os.path.basename(req.filename))
    try:
        if req.file_content_b64:
            with open(target, "wb") as f:
                f.write(base64.b64decode(req.file_content_b64))
        elif req.file_path:
            p = os.path.abspath(req.file_path)
            if not os.path.exists(p):
                return JSONResponse(status_code=400, content={"detail": f"Not found: {p}"})
            with open(p, "rb") as s, open(target, "wb") as d:
                d.write(s.read())
        else:
            # Try loading an already-present file in DATA_DIR
            if os.path.exists(target):
                pass  # file already there, just (re)load it
            else:
                return JSONResponse(status_code=400,
                    content={"detail": "Provide file_content_b64 or file_path."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

    table = csv_to_sqlite(target, DB_PATH)
    if not table:
        return JSONResponse(status_code=500, content={"detail": "SQLite conversion failed."})

    sanitized = table.replace("-", "_")
    if sanitized != table:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(f"ALTER TABLE {quote(table)} RENAME TO {quote(sanitized)}")
        conn.commit(); conn.close()
        table = sanitized

    state["table"] = table
    state["df_store"][table] = run_query(f"SELECT * FROM {quote(table)}")
    return {"message": f"Loaded → table **{table}**", "table": table}


# ── Pre-load existing CSV files into SQLite on startup ────────────────────────
@app.on_event("startup")
def _preload_data():
    """Auto-load any CSV already in the data/ folder into SQLite."""
    import glob
    for csv_path in glob.glob(os.path.join(DATA_DIR, "*.csv")):
        try:
            table = csv_to_sqlite(csv_path, DB_PATH)
            if table:
                sanitized = table.replace("-", "_")
                if sanitized != table:
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        conn.execute(f"ALTER TABLE {quote(table)} RENAME TO {quote(sanitized)}")
                        conn.commit(); conn.close()
                        table = sanitized
                    except Exception:
                        pass
                if table not in state["df_store"]:
                    state["df_store"][table] = run_query(f"SELECT * FROM {quote(table)}")
                if not state["table"]:
                    state["table"] = table
        except Exception:
            pass


# ── Streaming SSE endpoint (main chat flow) ───────────────────────────────────
@app.post("/stream")
def stream(req: StreamRequest):
    table = _ensure_table(req.table)
    if not table:
        def _err():
            yield 'data: {"type":"error","text":"No table loaded. Upload a CSV first."}\n\n'
        return StreamingResponse(_err(), media_type="text/event-stream")

    _load_df(table)
    msg = req.message.strip()

    def event_stream():
        t0 = time.time()

        yield f'data: {json.dumps({"type":"status","step":1,"total":5,"text":"🧠 Thinking..."})}\n\n'
        time.sleep(0.1)

        yield f'data: {json.dumps({"type":"status","step":2,"total":5,"text":"📋 Inspecting schema..."})}\n\n'
        schema = get_schema(table)
        time.sleep(0.08)

        yield f'data: {json.dumps({"type":"status","step":3,"total":5,"text":"⚙️ Generating SQL..."})}\n\n'
        try:
            from backend.llm import generate_sql
            sql = generate_sql(table, schema, msg)
        except Exception as e:
            yield f'data: {json.dumps({"type":"error","text":f"SQL generation failed: {e}"})}\n\n'
            return

        yield f'data: {json.dumps({"type":"status","step":4,"total":5,"text":"🚀 Executing query..."})}\n\n'
        try:
            df = run_query(sql)
            state["sql"] = sql
            state["df"]  = df
        except Exception as e:
            yield f'data: {json.dumps({"type":"error","text":f"Execution failed: {e}","sql":sql})}\n\n'
            return

        rows    = df.to_dict(orient="records")
        columns = list(df.columns)

        yield f'data: {json.dumps({"type":"status","step":5,"total":5,"text":"💡 Interpreting results..."})}\n\n'
        reply      = _interpret(msg, sql, rows, columns)
        chart_type = _decide_chart(msg, columns, len(df))

        elapsed = round(time.time() - t0, 2)
        log_audit(msg, sql, len(df), elapsed)
        _store_to_vector(msg, sql, reply, table, len(df))

        result = {
            "type"      : "result",
            "reply"     : reply,
            "sql"       : sql,
            "columns"   : columns,
            "rows"      : rows,
            "chart_type": chart_type,
            "elapsed"   : elapsed,
        }
        yield f'data: {json.dumps(result)}\n\n'
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Multi-agent SSE endpoint ──────────────────────────────────────────────────
@app.post("/multi-agent")
def multi_agent_stream(req: StreamRequest):
    table = _ensure_table(req.table)
    if not table:
        def _err():
            yield 'data: {"type":"error","text":"No table loaded."}\n\n'
        return StreamingResponse(_err(), media_type="text/event-stream")

    _load_df(table)

    def event_stream():
        from backend.orchestrator import run_multi_agent_stream
        for event in run_multi_agent_stream(req.message.strip(), table):
            yield f"data: {json.dumps(event)}\n\n"
            time.sleep(0.02)
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Orchestrate (tool-picker) ─────────────────────────────────────────────────
@app.post("/orchestrate")
def orchestrate(req: StreamRequest):
    table = _ensure_table(req.table)
    if not table:
        return JSONResponse(status_code=400, content={"detail": "No table loaded."})
    _load_df(table)

    def event_stream():
        from backend.orchestrator import run_orchestrated
        for event in run_orchestrated(req.message, table, state["df_store"]):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Synchronous chat fallback ─────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    msg  = req.message.strip()
    mode = req.mode or "chat"
    if not msg:
        return ChatResponse(reply="Please enter a question.")

    table = _ensure_table(req.table)
    if not table:
        return ChatResponse(reply="No data loaded. Upload a CSV first.", error="no table")

    lower = msg.lower()

    if any(k in lower for k in ("list tables", "show tables", "what tables")):
        return ChatResponse(reply="**Available tables:**\n• " + "\n• ".join(all_tables()))
    if any(k in lower for k in ("show schema", "describe", "what columns", "table schema")):
        return ChatResponse(reply=f"**Schema for `{table}`:**\n```\n{get_schema(table)}\n```")
    if any(k in lower for k in ("preview", "head", "sample", "first few")):
        df = run_query(f"SELECT * FROM {quote(table)} LIMIT 5")
        return ChatResponse(reply=f"**First 5 rows:**\n```\n{df.to_string(index=False)}\n```")

    if any(k in lower for k in ("growth", "trend", "over time", "over the years",
                                 "history", "historical", "year by year", "progress")):
        res = _handle_growth_query(msg, table)
        if res:
            entity, long_df = res
            rows    = long_df.to_dict(orient="records")
            columns = ["Year", "Value"]
            reply   = _interpret(msg, f"-- Growth of {entity}", rows, columns)
            log_audit(msg, f"-- Growth of {entity}", len(long_df), 0)
            _store_to_vector(msg, f"-- Growth of {entity}", reply, table, len(long_df))
            return ChatResponse(reply=reply, columns=columns, rows=rows, chart_type="line")

    _load_df(table)
    t0     = time.time()
    tool   = all_tools().get("sql_query")
    result = tool.run(table=table, df_store=state["df_store"], query=msg)
    elapsed= round(time.time() - t0, 2)

    if not result["ok"]:
        log_audit(msg, result.get("sql", ""), 0, elapsed, error=result["summary"])
        return ChatResponse(reply=result["summary"], error=result["summary"])

    rows    = result.get("rows", [])
    columns = result.get("columns", [])
    sql     = result.get("sql", "")
    reply      = _interpret(msg, sql, rows, columns)
    chart_type = _decide_chart(msg, columns, len(rows))
    log_audit(msg, sql, len(rows), elapsed)
    _store_to_vector(msg, sql, reply, table, len(rows))

    return ChatResponse(reply=reply, sql=sql, columns=columns, rows=rows, chart_type=chart_type)


# ── Tutor / Transform / Dashboard ────────────────────────────────────────────
@app.post("/tutor")
def tutor(req: ChatRequest):
    table = _ensure_table(req.table)
    if not table:
        return JSONResponse(status_code=400, content={"detail": "No table loaded."})
    _load_df(table)
    tool = all_tools().get("sql_tutor")
    if not tool:
        return JSONResponse(status_code=501, content={"detail": "Tutor tool not found."})
    return tool.run(table=table, df_store=state["df_store"], query=req.message)


@app.post("/transform")
def transform(req: ChatRequest):
    table = _ensure_table(req.table)
    if not table:
        return JSONResponse(status_code=400, content={"detail": "No table loaded."})
    _load_df(table)
    tool = all_tools().get("transform_data")
    if not tool:
        return JSONResponse(status_code=501, content={"detail": "Transform tool not found."})
    result = tool.run(table=table, df_store=state["df_store"], instruction=req.message)
    if result.get("ok") and result.get("new_table"):
        nt = result["new_table"]
        state["df_store"][nt] = run_query(f"SELECT * FROM {quote(nt)}")
    return result


@app.post("/dashboard")
def dashboard(req: ChatRequest):
    table = _ensure_table(req.table)
    if not table:
        return JSONResponse(status_code=400, content={"detail": "No table loaded."})
    _load_df(table)
    tool = all_tools().get("build_dashboard")
    if not tool:
        return JSONResponse(status_code=501, content={"detail": "Dashboard tool not found."})
    return tool.run(table=table, df_store=state["df_store"], description=req.message)


@app.post("/analyse")
def analyse(req: ChatRequest):
    table = _ensure_table(req.table)
    if not table:
        return JSONResponse(status_code=400, content={"detail": "No table loaded."})
    _load_df(table)
    tools = all_tools()
    prof  = tools["profile_dataset"].run(table=table, df_store=state["df_store"])
    ins   = tools["discover_insights"].run(table=table, df_store=state["df_store"])
    return {"profile": prof, "insights": ins}


@app.post("/clean")
def clean(req: ChatRequest):
    table = _ensure_table(req.table)
    if not table:
        return JSONResponse(status_code=400, content={"detail": "No table loaded."})
    _load_df(table)
    result = all_tools()["clean_data"].run(table=table, df_store=state["df_store"])
    if result.get("ok") and result.get("data", {}).get("clean_table"):
        ct = result["data"]["clean_table"]
        state["df_store"][ct] = run_query(f"SELECT * FROM {quote(ct)}")
    return result


# ── Export routes ─────────────────────────────────────────────────────────────
@app.get("/export")
def export_csv():
    if state["df"] is None or state["df"].empty:
        return JSONResponse(status_code=404, content={"detail": "No results yet."})
    buf = io.StringIO()
    state["df"].to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=results.csv"})


@app.get("/export/excel")
def export_excel():
    if state["df"] is None or state["df"].empty:
        return JSONResponse(status_code=404, content={"detail": "No results yet."})
    try:
        import openpyxl
        buf = io.BytesIO()
        state["df"].to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        return StreamingResponse(iter([buf.getvalue()]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=results.xlsx"})
    except ImportError:
        return JSONResponse(status_code=500,
            content={"detail": "openpyxl not installed. Run: pip install openpyxl"})


@app.get("/export/json")
def export_json():
    if state["df"] is None or state["df"].empty:
        return JSONResponse(status_code=404, content={"detail": "No results yet."})
    return JSONResponse(content=state["df"].to_dict(orient="records"))


@app.get("/export/pdf")
def export_pdf():
    if state["df"] is None or state["df"].empty:
        return JSONResponse(status_code=404, content={"detail": "No results yet."})
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        buf    = io.BytesIO()
        doc    = SimpleDocTemplate(buf, pagesize=letter)
        styles = getSampleStyleSheet()
        elems  = []

        elems.append(Paragraph("NL → SQL Query Report", styles["Title"]))
        elems.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
        elems.append(Spacer(1, 12))
        if state.get("sql"):
            elems.append(Paragraph("SQL Query:", styles["Heading2"]))
            elems.append(Paragraph(state["sql"], styles["Code"]))
            elems.append(Spacer(1, 12))

        df   = state["df"]
        data = [list(df.columns)] + df.head(50).astype(str).values.tolist()
        tbl  = Table(data)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0a0c10")),
            ("TEXTCOLOR",  (0,0), (-1,0), colors.HexColor("#00d4ff")),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,-1), 8),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f0f0")]),
            ("GRID",       (0,0), (-1,-1), 0.5, colors.grey),
        ]))
        elems.append(tbl)
        doc.build(elems)
        buf.seek(0)
        return StreamingResponse(iter([buf.getvalue()]), media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=report.pdf"})
    except ImportError:
        return JSONResponse(status_code=500,
            content={"detail": "reportlab not installed. Run: pip install reportlab"})


@app.get("/export_clean")
def export_clean():
    import glob
    clean_files = [f for f in os.listdir(DATA_DIR) if f.endswith("_cleaned.csv")]
    if not clean_files:
        return JSONResponse(status_code=404, content={"detail": "No cleaned file yet."})
    path = os.path.join(DATA_DIR, sorted(clean_files)[-1])
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return StreamingResponse(iter([content]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={os.path.basename(path)}"})


# ── Google Sheets export ──────────────────────────────────────────────────────
@app.post("/export/google-sheets")
def export_google_sheets(req: EmailRequest):
    tool   = all_tools().get("export_google_sheets")
    if not tool:
        return JSONResponse(status_code=501, content={"detail": "Google Sheets tool not loaded."})
    result = tool.run(table=state.get("table",""), df_store=state["df_store"],
                      title=req.subject or "NL→SQL Export",
                      share_email=req.to or None)
    return result


# ── Email report ──────────────────────────────────────────────────────────────
@app.post("/email-report")
def email_report(req: EmailRequest):
    tool   = all_tools().get("email_report")
    if not tool:
        return JSONResponse(status_code=501, content={"detail": "Email tool not loaded."})
    result = tool.run(
        table=state.get("table",""), df_store=state["df_store"],
        to=req.to, subject=req.subject or "NL→SQL Report",
        body_text=req.body or "",
    )
    return result


# ── Schedule report ───────────────────────────────────────────────────────────
@app.post("/schedule")
def schedule_report(req: ScheduleRequest):
    tool = all_tools().get("schedule_report")
    if not tool:
        return JSONResponse(status_code=501, content={"detail": "Scheduler tool not loaded."})
    return tool.run(
        table=state.get("table",""), df_store=state["df_store"],
        query=req.query, recipient=req.recipient,
        frequency=req.frequency, day_of_week=req.day_of_week,
        run_time=req.run_time, name=req.name or "",
        action=req.action or "create", job_id=req.job_id,
    )


@app.get("/schedule")
def list_schedules():
    tool = all_tools().get("schedule_report")
    if not tool:
        return {"jobs": []}
    return tool.run(table="", df_store={}, action="list")


# ── Image-to-SQL ──────────────────────────────────────────────────────────────
@app.post("/image-to-sql")
def image_to_sql(req: ImageSQLRequest):
    table = _ensure_table(None)
    if not table:
        return JSONResponse(status_code=400, content={"detail": "No table loaded."})
    _load_df(table)
    tool = all_tools().get("image_to_sql")
    if not tool:
        return JSONResponse(status_code=501, content={"detail": "Image-to-SQL tool not loaded."})
    return tool.run(table=table, df_store=state["df_store"],
                    image_b64=req.image_b64, image_mime=req.image_mime)


# ── Query optimiser ───────────────────────────────────────────────────────────
@app.post("/optimize")
def optimize(req: OptimizeRequest):
    table = _ensure_table(None)
    if not table:
        return JSONResponse(status_code=400, content={"detail": "No table loaded."})
    _load_df(table)
    tool = all_tools().get("optimize_query")
    if not tool:
        return JSONResponse(status_code=501, content={"detail": "Optimizer tool not loaded."})
    return tool.run(table=table, df_store=state["df_store"],
                    query=req.query or "", sql=req.sql or "")


# ── Vector search (past queries) ──────────────────────────────────────────────
@app.post("/vector-search")
def vector_search(req: VectorSearchRequest):
    tool = all_tools().get("vector_search")
    if not tool:
        return JSONResponse(status_code=501, content={"detail": "Vector search tool not loaded."})
    return tool.run(table=state.get("table",""), df_store={},
                    query=req.query, top_k=req.top_k or 5)


# ── Voice (Whisper) ───────────────────────────────────────────────────────────
@app.post("/voice")
def voice_transcribe(req: VoiceRequest):
    """Transcribe audio using OpenAI Whisper and return the text."""
    try:
        audio_bytes = base64.b64decode(req.audio_b64)
        audio_ext   = {"audio/webm": "webm", "audio/wav": "wav",
                       "audio/mp4": "mp4", "audio/ogg": "ogg"}.get(req.audio_mime, "webm")
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        buf    = io.BytesIO(audio_bytes)
        buf.name = f"audio.{audio_ext}"
        transcript = client.audio.transcriptions.create(
            model="whisper-1", file=buf, response_format="text"
        )
        return {"ok": True, "text": transcript.strip()}
    except ImportError:
        return JSONResponse(status_code=500, content={"detail": "openai not installed."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Transcription failed: {e}"})


# ── Feedback ──────────────────────────────────────────────────────────────────
@app.post("/feedback")
def feedback(req: FeedbackRequest):
    log_feedback(req.query, req.sql or "", req.rating, req.comment or "")
    return {"ok": True, "message": "Feedback recorded. Thank you!"}


# ── Conversation History ──────────────────────────────────────────────────────
from backend.database import (
    save_conversation, list_conversations, load_conversation,
    delete_conversation, pin_conversation, purge_old_conversations,
)
import uuid as _uuid

class HistorySaveRequest(BaseModel):
    session_id: Optional[str]  = None
    title:      str
    messages:   list
    table_name: Optional[str]  = ""
    pinned:     Optional[bool] = False

class PinRequest(BaseModel):
    pinned: bool


@app.get("/history")
def get_history(limit: int = 60):
    user = state.get("current_user", "admin")
    return {"conversations": list_conversations(user, limit=limit)}


@app.post("/history")
def create_history(req: HistorySaveRequest):
    sid = req.session_id or str(_uuid.uuid4())
    user = state.get("current_user", "admin")
    save_conversation(
        session_id=sid,
        title=req.title or "Untitled",
        messages=req.messages,
        table_name=req.table_name or "",
        username=user,
        pinned=req.pinned or False,
    )
    return {"ok": True, "session_id": sid}


@app.get("/history/{session_id}")
def get_conversation(session_id: str):
    conv = load_conversation(session_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conv


@app.delete("/history/{session_id}")
def delete_history(session_id: str):
    delete_conversation(session_id)
    return {"ok": True}


@app.patch("/history/{session_id}/pin")
def toggle_pin(session_id: str, req: PinRequest):
    pin_conversation(session_id, req.pinned)
    return {"ok": True, "pinned": req.pinned}


@app.post("/history/purge")
def purge_history():
    count = purge_old_conversations()
    return {"ok": True, "deleted": count,
            "message": f"Purged {count} conversation(s) older than 2 days."}


# ── MCP Server / Tool registry ────────────────────────────────────────────────
# Returns tools grouped by logical "server" so the UI can show
# the Claude-style Connectors panel with per-server toggles.
MCP_SERVERS = {
    "Database Ops": {
        "icon": "🗄️",
        "color": "#00d4ff",
        "tools": [
            {"name": "db_list",             "desc": "List all databases"},
            {"name": "db_schemas",          "desc": "Get schemas in a database"},
            {"name": "db_tables",           "desc": "Get tables with fields"},
            {"name": "sql_execute",         "desc": "Execute SQL queries"},
            {"name": "db_table_create",     "desc": "Create tables (AI-prefixed)"},
            {"name": "db_view_create",      "desc": "Create views"},
            {"name": "db_matview_create",   "desc": "Create materialized views"},
            {"name": "db_index_create",     "desc": "Create indexes"},
            {"name": "db_vacuum_analyze",   "desc": "VACUUM and ANALYZE"},
            {"name": "db_query_explain",    "desc": "EXPLAIN query plans"},
            {"name": "db_table_stats",      "desc": "Table statistics"},
            {"name": "db_index_usage",      "desc": "Index usage analysis"},
            {"name": "db_schema_explore",   "desc": "Fast schema exploration"},
            {"name": "db_schema_analyze",   "desc": "Deep schema analysis"},
            {"name": "db_relationships_detect", "desc": "Detect foreign keys & relationships"},
        ],
    },
    "AI Features": {
        "icon": "🤖",
        "color": "#7c3aed",
        "tools": [
            {"name": "ai_sql_generate",         "desc": "Natural language → SQL"},
            {"name": "ai_sql_optimize",         "desc": "Query optimization suggestions"},
            {"name": "ai_sql_explain",          "desc": "Explain SQL in plain English"},
            {"name": "ai_relationships_suggest","desc": "Suggest table relationships"},
            {"name": "mb_auto_describe",        "desc": "Auto-generate descriptions"},
        ],
    },
    "NL→SQL Core": {
        "icon": "⚙️",
        "color": "#10b981",
        "tools": [
            {"name": "sql_query",       "desc": "NL → SQL → execute → rows + chart"},
            {"name": "sql_tutor",       "desc": "Teach SQL with explanation & tips"},
            {"name": "optimize_query",  "desc": "EXPLAIN + index recs + rewrite"},
            {"name": "show_schema",     "desc": "Show schema + sample rows"},
            {"name": "multi_agent",     "desc": "6-agent pipeline for max accuracy"},
        ],
    },
    "Dashboard": {
        "icon": "📊",
        "color": "#f59e0b",
        "tools": [
            {"name": "build_dashboard",             "desc": "Auto multi-panel dashboard"},
            {"name": "mb_dashboard_create",         "desc": "Create dashboards"},
            {"name": "mb_dashboards",               "desc": "List all dashboards"},
            {"name": "mb_dashboard_get",            "desc": "Get dashboard details"},
            {"name": "mb_dashboard_update",         "desc": "Update dashboards"},
            {"name": "mb_dashboard_delete",         "desc": "Delete dashboards"},
            {"name": "mb_dashboard_add_card",       "desc": "Add cards to dashboard"},
            {"name": "mb_dashboard_add_filter",     "desc": "Add filters"},
            {"name": "mb_dashboard_layout_optimize","desc": "Optimize layout"},
            {"name": "mb_dashboard_template_executive", "desc": "Executive templates"},
        ],
    },
    "Data Tools": {
        "icon": "🔧",
        "color": "#06b6d4",
        "tools": [
            {"name": "profile_dataset",  "desc": "Analyse rows, nulls, outliers"},
            {"name": "discover_insights","desc": "Trends, anomalies, top/bottom"},
            {"name": "clean_data",       "desc": "Dedupe, fill nulls, fix types"},
            {"name": "transform_data",   "desc": "NL data transformations"},
            {"name": "vector_search",    "desc": "Semantic search past queries"},
            {"name": "image_to_sql",     "desc": "Screenshot → SQL"},
        ],
    },
    "Export & Notify": {
        "icon": "📤",
        "color": "#8b5cf6",
        "tools": [
            {"name": "export_google_sheets","desc": "Export to Google Sheets"},
            {"name": "email_report",        "desc": "Email PDF + CSV report"},
            {"name": "schedule_report",     "desc": "Recurring scheduled reports"},
        ],
    },
    "Users & Security": {
        "icon": "🛡️",
        "color": "#ef4444",
        "tools": [
            {"name": "mb_user_list",              "desc": "List users"},
            {"name": "mb_user_get",               "desc": "Get user details"},
            {"name": "mb_user_create",            "desc": "Create users"},
            {"name": "mb_user_update",            "desc": "Update users"},
            {"name": "mb_user_disable",           "desc": "Disable users"},
            {"name": "mb_permission_group_list",  "desc": "List permission groups"},
            {"name": "mb_permission_group_create","desc": "Create permission groups"},
        ],
    },
}


@app.get("/mcp-servers")
def mcp_servers():
    """Return MCP server groups with their tool lists for the UI panel."""
    # Merge static catalog with live registered tools
    live_tools = all_tools()
    result = {}
    for server_name, server_info in MCP_SERVERS.items():
        tools_out = []
        for t in server_info["tools"]:
            live = live_tools.get(t["name"])
            tools_out.append({
                "name"   : t["name"],
                "desc"   : live.description if live else t["desc"],
                "emoji"  : live.emoji if live else "🔧",
                "active" : t["name"] in live_tools,
            })
        result[server_name] = {
            "icon"  : server_info["icon"],
            "color" : server_info["color"],
            "tools" : tools_out,
            "count" : len(tools_out),
            "active": sum(1 for t in tools_out if t["active"]),
        }
    return {"servers": result}
