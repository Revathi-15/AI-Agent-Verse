# backend/database.py — SQLite helpers, shared state, audit log, feedback, permissions, scheduler

import os
import sqlite3
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

load_dotenv(os.path.join(BASE_DIR, ".env"))
DB_PATH = os.path.join(BASE_DIR, os.getenv("SQLITE_DB", "sqlite.db"))

os.makedirs(DATA_DIR, exist_ok=True)

# ── Shared in-process state ───────────────────────────────────────────────────
state: dict = {
    "table"        : None,
    "sql"          : None,
    "df"           : None,
    "df_store"     : {},
    "current_user" : "admin",        # active username (set by /login)
    "current_role" : "admin",        # active role
}


# ── Core helpers ──────────────────────────────────────────────────────────────
def quote(name: str) -> str:
    return f'"{name}"'


def all_tables() -> list[str]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT IN ("
        "  '_audit_log','_feedback','_vector_store',"
        "  '_scheduled_jobs','_permissions','_live_connections'"
        ") ORDER BY name"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def run_query(sql: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df   = pd.read_sql_query(sql, conn)
    conn.close()
    return df


def get_schema(table: str) -> str:
    conn    = sqlite3.connect(DB_PATH)
    pragma  = conn.execute(f"PRAGMA table_info({quote(table)})").fetchall()
    conn.close()
    col_names = [r[1] for r in pragma]
    col_types = {r[1]: r[2] for r in pragma}

    try:
        sample_df = run_query(f"SELECT * FROM {quote(table)} LIMIT 5")
    except Exception:
        return "\n".join(f"  {r[1]} ({r[2]})" for r in pragma)

    year_cols  = [c for c in col_names if c.isdigit() and len(c) == 4]
    other_cols = [c for c in col_names if c not in year_cols]
    lines = []

    for col in other_cols:
        dtype       = col_types.get(col, "TEXT")
        sample_vals = sample_df[col].dropna().head(3).tolist() if col in sample_df.columns else []
        sample_str  = f"  e.g. {sample_vals}" if sample_vals else ""
        lines.append(f"  {col!r} ({dtype}){sample_str}")

    if year_cols:
        best_year = None
        for yr in sorted(year_cols, reverse=True):
            if yr in sample_df.columns and sample_df[yr].notna().any():
                best_year = yr
                break
        lines.append(
            f"\n  *** YEAR DATA COLUMNS ({min(year_cols)}\u2013{max(year_cols)}) ***"
            f"\n  Each column name IS the year. Use {quote(best_year or year_cols[-1])} for latest data."
            f"\n  Most recent year with data: {best_year or year_cols[-1]}"
        )
        if best_year and best_year in sample_df.columns:
            nonnull = sample_df[
                [c for c in other_cols if c in sample_df.columns] + [best_year]
            ].dropna(subset=[best_year]).head(1)
            if not nonnull.empty:
                lines.append(f"  Sample: {nonnull.iloc[0].to_dict()}")

    unnamed = [c for c in col_names if c.lower().startswith("unnamed")]
    if unnamed:
        lines.append(f"\n  NOTE: Ignore columns {unnamed} \u2014 empty artifacts.")

    return "\n".join(lines)


def get_profile(table: str) -> dict:
    try:
        df        = run_query(f"SELECT * FROM {quote(table)}")
        real_cols = [c for c in df.columns if not c.lower().startswith("unnamed")]
        year_cols = [c for c in real_cols if c.isdigit() and len(c) == 4]
        meta_cols = [c for c in real_cols if c not in year_cols]
        best_year = None
        for yr in sorted(year_cols, reverse=True):
            if df[yr].notna().mean() > 0.5:
                best_year = yr
                break
        return {
            "rows"     : len(df),
            "cols"     : len(real_cols),
            "meta_cols": meta_cols,
            "year_cols": f"{min(year_cols)}\u2013{max(year_cols)}" if year_cols else None,
            "best_year": best_year,
            "null_pct" : {c: round(df[c].isna().mean()*100, 1) for c in meta_cols},
        }
    except Exception as e:
        return {"error": str(e)}


# ── Audit log ─────────────────────────────────────────────────────────────────
def _ensure_audit_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT,
            username    TEXT,
            role        TEXT,
            query       TEXT,
            sql         TEXT,
            rows        INTEGER,
            elapsed_s   REAL,
            error       TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_audit(query: str, sql: str, rows: int,
              elapsed: float, error: str = "") -> None:
    _ensure_audit_table()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO _audit_log (ts, username, role, query, sql, rows, elapsed_s, error) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            datetime.now().isoformat(timespec="seconds"),
            state.get("current_user", "unknown"),
            state.get("current_role", "viewer"),
            query, sql, rows, elapsed, error,
        ),
    )
    conn.commit()
    conn.close()


def get_audit_log(limit: int = 50) -> list[dict]:
    _ensure_audit_table()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT ts, username, role, query, sql, rows, elapsed_s, error "
        "FROM _audit_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    keys = ["ts", "username", "role", "query", "sql", "rows", "elapsed_s", "error"]
    return [dict(zip(keys, r)) for r in rows]


# ── Feedback store ────────────────────────────────────────────────────────────
def _ensure_feedback_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _feedback (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            ts      TEXT,
            username TEXT,
            query   TEXT,
            sql     TEXT,
            rating  INTEGER,
            comment TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_feedback(query: str, sql: str, rating: int, comment: str = "") -> None:
    _ensure_feedback_table()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO _feedback (ts, username, query, sql, rating, comment) VALUES (?,?,?,?,?,?)",
        (
            datetime.now().isoformat(timespec="seconds"),
            state.get("current_user", "unknown"),
            query, sql, rating, comment,
        ),
    )
    conn.commit()
    conn.close()


def get_feedback_stats() -> dict:
    """Return aggregate feedback stats for improving prompts."""
    _ensure_feedback_table()
    conn  = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM _feedback").fetchone()[0]
    pos   = conn.execute("SELECT COUNT(*) FROM _feedback WHERE rating > 0").fetchone()[0]
    neg   = conn.execute("SELECT COUNT(*) FROM _feedback WHERE rating < 0").fetchone()[0]
    # Worst-rated queries (most useful for prompt improvement)
    worst = conn.execute(
        "SELECT query, sql, comment FROM _feedback WHERE rating < 0 ORDER BY id DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return {
        "total"     : total,
        "positive"  : pos,
        "negative"  : neg,
        "score_pct" : round(pos / total * 100, 1) if total else 0,
        "worst_queries": [{"query": r[0], "sql": r[1], "comment": r[2]} for r in worst],
    }


# ── Permissions ───────────────────────────────────────────────────────────────
ROLES = ("admin", "manager", "analyst", "viewer")

ROLE_PERMISSIONS = {
    "admin"  : {"can_query", "can_upload", "can_export", "can_email", "can_schedule",
                "can_clean", "can_transform", "can_view_audit", "can_manage_users"},
    "manager": {"can_query", "can_upload", "can_export", "can_email", "can_schedule",
                "can_view_audit"},
    "analyst": {"can_query", "can_upload", "can_export"},
    "viewer" : {"can_query"},
}


def _ensure_permissions_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _permissions (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            role     TEXT DEFAULT 'viewer',
            email    TEXT,
            created  TEXT,
            last_seen TEXT
        )
    """)
    # Seed admin user
    conn.execute("""
        INSERT OR IGNORE INTO _permissions (username, role, email, created)
        VALUES ('admin', 'admin', '', ?)
    """, (datetime.now().isoformat(timespec="seconds"),))
    conn.commit()
    conn.close()


def get_user(username: str) -> dict | None:
    _ensure_permissions_table()
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute(
        "SELECT username, role, email, created, last_seen FROM _permissions WHERE username=?",
        (username,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return dict(zip(["username", "role", "email", "created", "last_seen"], row))


def upsert_user(username: str, role: str, email: str = "") -> dict:
    _ensure_permissions_table()
    if role not in ROLES:
        raise ValueError(f"Invalid role '{role}'. Choose from: {ROLES}")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO _permissions (username, role, email, created)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET role=excluded.role, email=excluded.email
    """, (username, role, email, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    return {"username": username, "role": role, "permissions": list(ROLE_PERMISSIONS[role])}


def list_users() -> list[dict]:
    _ensure_permissions_table()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT username, role, email, created, last_seen FROM _permissions ORDER BY username"
    ).fetchall()
    conn.close()
    return [dict(zip(["username","role","email","created","last_seen"], r)) for r in rows]


def has_permission(permission: str, username: str | None = None) -> bool:
    """Check if a user has a specific permission."""
    user = username or state.get("current_user", "admin")
    u    = get_user(user)
    role = u["role"] if u else state.get("current_role", "admin")
    return permission in ROLE_PERMISSIONS.get(role, set())


def touch_user(username: str):
    """Update last_seen timestamp."""
    _ensure_permissions_table()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE _permissions SET last_seen=? WHERE username=?",
        (datetime.now().isoformat(timespec="seconds"), username),
    )
    conn.commit()
    conn.close()


# ── Live DB connections registry ──────────────────────────────────────────────
def _ensure_connections_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _live_connections (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT UNIQUE,
            db_type  TEXT,    -- postgresql | mysql | snowflake | bigquery | redshift | sqlite
            host     TEXT,
            port     INTEGER,
            database TEXT,
            username TEXT,
            password TEXT,    -- stored encrypted in production; plain for demo
            extra    TEXT,    -- JSON for extra params (project_id, warehouse, etc.)
            created  TEXT,
            enabled  INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()


def save_connection(name: str, db_type: str, host: str = "", port: int = 5432,
                    database: str = "", username: str = "", password: str = "",
                    extra: dict | None = None) -> int:
    _ensure_connections_table()
    import json
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.execute("""
        INSERT INTO _live_connections (name, db_type, host, port, database, username, password, extra, created)
        VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT(name) DO UPDATE SET
          db_type=excluded.db_type, host=excluded.host, port=excluded.port,
          database=excluded.database, username=excluded.username,
          password=excluded.password, extra=excluded.extra
    """, (name, db_type, host, port, database, username, password,
          json.dumps(extra or {}), datetime.now().isoformat(timespec="seconds")))
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid


def list_connections() -> list[dict]:
    _ensure_connections_table()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, name, db_type, host, port, database, username, enabled, created "
        "FROM _live_connections ORDER BY name"
    ).fetchall()
    conn.close()
    keys = ["id","name","db_type","host","port","database","username","enabled","created"]
    return [dict(zip(keys, r)) for r in rows]


def query_live_connection(connection_name: str, sql: str) -> pd.DataFrame:
    """Execute SQL against a live external database connection."""
    _ensure_connections_table()
    import json
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute(
        "SELECT db_type, host, port, database, username, password, extra "
        "FROM _live_connections WHERE name=? AND enabled=1",
        (connection_name,),
    ).fetchone()
    conn.close()

    if not row:
        raise ValueError(f"Connection '{connection_name}' not found or disabled.")

    db_type, host, port, database, username, password, extra_json = row
    extra = json.loads(extra_json or "{}")

    if db_type in ("postgresql", "postgres"):
        import sqlalchemy as sa
        url = sa.engine.URL.create("postgresql+psycopg2",
            host=host, port=port, database=database,
            username=username, password=password)
        engine = sa.create_engine(url, pool_pre_ping=True)
        with engine.connect() as c:
            return pd.read_sql_query(sql, c)

    elif db_type == "mysql":
        import sqlalchemy as sa
        url = sa.engine.URL.create("mysql+pymysql",
            host=host, port=port or 3306, database=database,
            username=username, password=password)
        engine = sa.create_engine(url, pool_pre_ping=True)
        with engine.connect() as c:
            return pd.read_sql_query(sql, c)

    elif db_type == "sqlite":
        target = host or database  # use host field as file path for sqlite
        conn2  = sqlite3.connect(target)
        df     = pd.read_sql_query(sql, conn2)
        conn2.close()
        return df

    else:
        raise NotImplementedError(
            f"Live connection for '{db_type}' is registered but driver not installed. "
            f"Install: sqlalchemy + the appropriate dialect driver."
        )


# ── Vector store helpers (imported from tool but also usable directly) ────────
def ensure_all_tables():
    """Create all system tables at startup."""
    _ensure_audit_table()
    _ensure_feedback_table()
    _ensure_permissions_table()
    _ensure_connections_table()
    # Vector store table
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _vector_store (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ts       TEXT,
            query    TEXT,
            sql      TEXT,
            reply    TEXT,
            table_n  TEXT,
            rows     INTEGER,
            tokens   TEXT
        )
    """)
    # Scheduler table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _scheduled_jobs (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT,
            query     TEXT,
            recipient TEXT,
            frequency TEXT,
            day_of_week TEXT,
            run_time  TEXT,
            table_n   TEXT,
            enabled   INTEGER DEFAULT 1,
            last_run  TEXT,
            next_run  TEXT,
            created   TEXT
        )
    """)
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# CONVERSATION HISTORY — dual-store: PostgreSQL primary, SQLite fallback
# Conversations auto-expire after 2 days.
# ══════════════════════════════════════════════════════════════════════════════
import json as _json
from datetime import datetime, timedelta

_PG_URL = os.getenv("POSTGRES_URL", "")  # e.g. postgresql://user:pass@host/db


def _pg_conn():
    """Return a psycopg2 connection or None if not configured/available."""
    if not _PG_URL:
        return None
    try:
        import psycopg2
        return psycopg2.connect(_PG_URL)
    except Exception:
        return None


def _ensure_history_pg(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversation_history (
            id          SERIAL PRIMARY KEY,
            session_id  TEXT NOT NULL,
            title       TEXT,
            username    TEXT DEFAULT 'admin',
            messages    JSONB NOT NULL DEFAULT '[]',
            table_name  TEXT,
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            updated_at  TIMESTAMPTZ DEFAULT NOW(),
            pinned      BOOLEAN DEFAULT FALSE
        )
    """)
    # Auto-purge trigger: delete rows older than 2 days unless pinned
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_history_updated
        ON conversation_history(updated_at)
        WHERE NOT pinned
    """)
    conn.commit()
    cur.close()


def _ensure_history_sqlite():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _conversation_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL,
            title       TEXT,
            username    TEXT DEFAULT 'admin',
            messages    TEXT NOT NULL DEFAULT '[]',
            table_name  TEXT,
            created_at  TEXT,
            updated_at  TEXT,
            pinned      INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


# ── Public API ────────────────────────────────────────────────────────────────

def save_conversation(session_id: str, title: str, messages: list,
                      table_name: str = "", username: str = "admin",
                      pinned: bool = False) -> str:
    """Upsert a conversation. Returns session_id."""
    now = datetime.utcnow().isoformat()
    pg  = _pg_conn()
    if pg:
        try:
            _ensure_history_pg(pg)
            cur = pg.cursor()
            cur.execute("""
                INSERT INTO conversation_history
                    (session_id, title, username, messages, table_name, created_at, updated_at, pinned)
                VALUES (%s,%s,%s,%s,%s,NOW(),NOW(),%s)
                ON CONFLICT (session_id) DO UPDATE
                  SET title=EXCLUDED.title,
                      messages=EXCLUDED.messages,
                      table_name=EXCLUDED.table_name,
                      updated_at=NOW(),
                      pinned=EXCLUDED.pinned
            """, (session_id, title, username,
                  _json.dumps(messages), table_name, pinned))
            pg.commit()
            cur.close()
            pg.close()
            return session_id
        except Exception:
            try: pg.close()
            except Exception: pass

    # SQLite fallback
    _ensure_history_sqlite()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO _conversation_history
            (session_id, title, username, messages, table_name, created_at, updated_at, pinned)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(session_id) DO UPDATE
          SET title=excluded.title,
              messages=excluded.messages,
              table_name=excluded.table_name,
              updated_at=excluded.updated_at,
              pinned=excluded.pinned
    """, (session_id, title, username,
          _json.dumps(messages), table_name, now, now, 1 if pinned else 0))
    conn.commit()
    conn.close()
    return session_id


def list_conversations(username: str = "admin", limit: int = 50) -> list[dict]:
    """Return recent conversations, newest first, excluding expired non-pinned."""
    cutoff = (datetime.utcnow() - timedelta(days=2)).isoformat()
    pg = _pg_conn()
    if pg:
        try:
            _ensure_history_pg(pg)
            cur = pg.cursor()
            cur.execute("""
                SELECT session_id, title, username, table_name,
                       created_at, updated_at, pinned,
                       jsonb_array_length(messages) as msg_count
                FROM conversation_history
                WHERE username = %s
                  AND (pinned = TRUE OR updated_at > NOW() - INTERVAL '2 days')
                ORDER BY pinned DESC, updated_at DESC
                LIMIT %s
            """, (username, limit))
            rows = cur.fetchall()
            cur.close()
            pg.close()
            keys = ["session_id","title","username","table_name",
                    "created_at","updated_at","pinned","msg_count"]
            result = []
            for r in rows:
                d = dict(zip(keys, r))
                d["created_at"] = str(d["created_at"])
                d["updated_at"] = str(d["updated_at"])
                result.append(d)
            return result
        except Exception:
            try: pg.close()
            except Exception: pass

    # SQLite fallback
    _ensure_history_sqlite()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT session_id, title, username, table_name,
               created_at, updated_at, pinned,
               LENGTH(messages) as msg_len
        FROM _conversation_history
        WHERE username = ?
          AND (pinned = 1 OR updated_at > ?)
        ORDER BY pinned DESC, updated_at DESC
        LIMIT ?
    """, (username, cutoff, limit)).fetchall()
    conn.close()
    keys = ["session_id","title","username","table_name",
            "created_at","updated_at","pinned","msg_len"]
    return [dict(zip(keys, r)) for r in rows]


def load_conversation(session_id: str) -> dict | None:
    """Load a single conversation's messages."""
    pg = _pg_conn()
    if pg:
        try:
            _ensure_history_pg(pg)
            cur = pg.cursor()
            cur.execute("""
                SELECT session_id, title, username, messages, table_name,
                       created_at, updated_at, pinned
                FROM conversation_history WHERE session_id = %s
            """, (session_id,))
            row = cur.fetchone()
            cur.close(); pg.close()
            if not row:
                return None
            keys = ["session_id","title","username","messages","table_name",
                    "created_at","updated_at","pinned"]
            d = dict(zip(keys, row))
            d["messages"]   = d["messages"] if isinstance(d["messages"], list) else _json.loads(d["messages"] or "[]")
            d["created_at"] = str(d["created_at"])
            d["updated_at"] = str(d["updated_at"])
            return d
        except Exception:
            try: pg.close()
            except Exception: pass

    _ensure_history_sqlite()
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute("""
        SELECT session_id, title, username, messages, table_name,
               created_at, updated_at, pinned
        FROM _conversation_history WHERE session_id = ?
    """, (session_id,)).fetchone()
    conn.close()
    if not row:
        return None
    keys = ["session_id","title","username","messages","table_name",
            "created_at","updated_at","pinned"]
    d = dict(zip(keys, row))
    d["messages"] = _json.loads(d["messages"] or "[]")
    return d


def delete_conversation(session_id: str) -> bool:
    pg = _pg_conn()
    if pg:
        try:
            cur = pg.cursor()
            cur.execute("DELETE FROM conversation_history WHERE session_id=%s", (session_id,))
            pg.commit(); cur.close(); pg.close()
            return True
        except Exception:
            try: pg.close()
            except Exception: pass
    _ensure_history_sqlite()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM _conversation_history WHERE session_id=?", (session_id,))
    conn.commit(); conn.close()
    return True


def pin_conversation(session_id: str, pinned: bool) -> bool:
    pg = _pg_conn()
    if pg:
        try:
            cur = pg.cursor()
            cur.execute("UPDATE conversation_history SET pinned=%s WHERE session_id=%s",
                        (pinned, session_id))
            pg.commit(); cur.close(); pg.close()
            return True
        except Exception:
            try: pg.close()
            except Exception: pass
    _ensure_history_sqlite()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE _conversation_history SET pinned=? WHERE session_id=?",
                 (1 if pinned else 0, session_id))
    conn.commit(); conn.close()
    return True


def purge_old_conversations() -> int:
    """Delete non-pinned conversations older than 2 days. Returns count deleted."""
    cutoff = (datetime.utcnow() - timedelta(days=2)).isoformat()
    pg = _pg_conn()
    if pg:
        try:
            cur = pg.cursor()
            cur.execute("""
                DELETE FROM conversation_history
                WHERE pinned = FALSE AND updated_at < NOW() - INTERVAL '2 days'
            """)
            count = cur.rowcount
            pg.commit(); cur.close(); pg.close()
            return count
        except Exception:
            try: pg.close()
            except Exception: pass
    _ensure_history_sqlite()
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.execute(
        "DELETE FROM _conversation_history WHERE pinned=0 AND updated_at < ?", (cutoff,))
    count = cur.rowcount
    conn.commit(); conn.close()
    return count
