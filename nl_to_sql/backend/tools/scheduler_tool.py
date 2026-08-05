# scheduler_tool.py — Schedule recurring reports (daily/weekly/monthly)
#
# Uses Python's `schedule` library for lightweight in-process scheduling.
# Jobs are persisted to SQLite so they survive restarts.

import os
import json
import sqlite3
import threading
from datetime import datetime, time as dt_time

from backend.tools.base import BaseTool
from backend.database   import DB_PATH

_schedule_lock   = threading.Lock()
_scheduler_thread: threading.Thread | None = None


# ── DB persistence ────────────────────────────────────────────────────────────

def _ensure_scheduler_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _scheduled_jobs (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT,
            query     TEXT,
            recipient TEXT,
            frequency TEXT,       -- daily | weekly | monthly
            day_of_week TEXT,     -- mon|tue|wed|thu|fri|sat|sun  (for weekly)
            run_time  TEXT,       -- HH:MM  (24-hour)
            table_n   TEXT,
            enabled   INTEGER DEFAULT 1,
            last_run  TEXT,
            next_run  TEXT,
            created   TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_job(name: str, query: str, recipient: str,
             frequency: str, day_of_week: str, run_time: str, table: str) -> int:
    _ensure_scheduler_table()
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.execute(
        "INSERT INTO _scheduled_jobs "
        "(name, query, recipient, frequency, day_of_week, run_time, table_n, created) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (name, query, recipient, frequency, day_of_week, run_time, table,
         datetime.now().isoformat(timespec="seconds")),
    )
    job_id = cur.lastrowid
    conn.commit()
    conn.close()
    return job_id


def list_jobs() -> list[dict]:
    _ensure_scheduler_table()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, name, query, recipient, frequency, day_of_week, run_time, "
        "table_n, enabled, last_run, next_run, created "
        "FROM _scheduled_jobs ORDER BY id DESC"
    ).fetchall()
    conn.close()
    keys = ["id","name","query","recipient","frequency","day_of_week","run_time",
            "table","enabled","last_run","next_run","created"]
    return [dict(zip(keys, r)) for r in rows]


def delete_job(job_id: int) -> bool:
    _ensure_scheduler_table()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM _scheduled_jobs WHERE id=?", (job_id,))
    conn.commit()
    conn.close()
    return True


def toggle_job(job_id: int, enabled: bool) -> bool:
    _ensure_scheduler_table()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE _scheduled_jobs SET enabled=? WHERE id=?",
                 (1 if enabled else 0, job_id))
    conn.commit()
    conn.close()
    return True


def _mark_run(job_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE _scheduled_jobs SET last_run=? WHERE id=?",
                 (datetime.now().isoformat(timespec="seconds"), job_id))
    conn.commit()
    conn.close()


# ── Scheduler thread ──────────────────────────────────────────────────────────

def _run_job(job: dict):
    """Execute a single scheduled job: run query → email result."""
    try:
        from backend.database import run_query, quote, state, get_schema
        from backend.llm      import generate_sql, call_llm

        table  = job["table"]
        query  = job["query"]
        schema = get_schema(table)
        sql    = generate_sql(table, schema, query)
        df     = run_query(sql)

        if df.empty:
            return

        state["df"]  = df
        state["sql"] = sql

        # Generate summary
        summary = call_llm(
            f"Write a 2-sentence summary of this scheduled report result.\n"
            f"Query: {query}\nRows: {len(df)}\nColumns: {list(df.columns)}",
            max_tokens=100, temperature=0.3,
        )

        # Send email
        from backend.tools.email_tool import EmailReportTool
        EmailReportTool().run(
            table=table, df_store={},
            to=job["recipient"],
            subject=f"Scheduled Report: {job['name']}",
            body_text=f"Your scheduled report '{job['name']}' is ready.",
            df=df, sql=sql, summary=summary,
        )

        _mark_run(job["id"])
    except Exception as e:
        print(f"[Scheduler] Job '{job['name']}' failed: {e}")


def start_scheduler():
    """Start the background scheduler thread. Call once at app startup."""
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return

    try:
        import schedule
        import time

        def _loop():
            while True:
                with _schedule_lock:
                    schedule.run_pending()
                # Also check DB jobs every minute
                _tick_db_jobs()
                time.sleep(30)

        _scheduler_thread = threading.Thread(target=_loop, daemon=True, name="scheduler")
        _scheduler_thread.start()
    except ImportError:
        print("[Scheduler] 'schedule' not installed — run: pip install schedule")


def _tick_db_jobs():
    """Check DB jobs and fire any that are due."""
    try:
        jobs = list_jobs()
        now  = datetime.now()
        for job in jobs:
            if not job["enabled"]:
                continue
            freq    = job.get("frequency", "daily")
            rt      = job.get("run_time", "08:00")
            try:
                hh, mm = map(int, rt.split(":"))
                due_time = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            except Exception:
                continue

            already_ran = job.get("last_run") and job["last_run"][:10] == now.strftime("%Y-%m-%d")

            if freq == "daily":
                if not already_ran and abs((now - due_time).total_seconds()) < 60:
                    threading.Thread(target=_run_job, args=(job,), daemon=True).start()

            elif freq == "weekly":
                day_map = {"mon":0,"tue":1,"wed":2,"thu":3,"fri":4,"sat":5,"sun":6}
                target_day = day_map.get((job.get("day_of_week") or "mon").lower()[:3], 0)
                if now.weekday() == target_day and not already_ran:
                    if abs((now - due_time).total_seconds()) < 60:
                        threading.Thread(target=_run_job, args=(job,), daemon=True).start()

            elif freq == "monthly":
                if now.day == 1 and not already_ran:
                    if abs((now - due_time).total_seconds()) < 60:
                        threading.Thread(target=_run_job, args=(job,), daemon=True).start()

    except Exception as e:
        print(f"[Scheduler] tick error: {e}")


# ── Tool class ────────────────────────────────────────────────────────────────

class SchedulerTool(BaseTool):
    name        = "schedule_report"
    description = "Schedule a recurring report (daily/weekly/monthly) to be emailed automatically"
    emoji       = "🗓️"

    def run(self, table: str, df_store: dict,
            query:       str = "",
            recipient:   str = "",
            frequency:   str = "weekly",     # daily | weekly | monthly
            day_of_week: str = "monday",     # for weekly jobs
            run_time:    str = "08:00",      # HH:MM 24-hour
            name:        str = "",
            action:      str = "create",     # create | list | delete | toggle
            job_id:      int | None = None,
            enabled:     bool = True,
            **kwargs) -> dict:

        # ── List jobs ──────────────────────────────────────────────────────
        if action == "list":
            jobs = list_jobs()
            if not jobs:
                return {
                    "ok": True,
                    "summary": "No scheduled jobs yet.",
                    "data": {"jobs": []},
                }
            return {
                "ok"     : True,
                "summary": f"Found **{len(jobs)}** scheduled job(s).",
                "data"   : {"jobs": jobs},
                "columns": ["id","name","frequency","run_time","recipient","enabled","last_run"],
                "rows"   : [{k: str(j.get(k,"")) for k in
                             ["id","name","frequency","run_time","recipient","enabled","last_run"]}
                            for j in jobs],
            }

        # ── Delete job ─────────────────────────────────────────────────────
        if action == "delete":
            if job_id is None:
                return {"ok": False, "summary": "Provide job_id to delete.", "data": None}
            delete_job(job_id)
            return {"ok": True, "summary": f"Deleted job #{job_id}.", "data": None}

        # ── Toggle job ─────────────────────────────────────────────────────
        if action == "toggle":
            if job_id is None:
                return {"ok": False, "summary": "Provide job_id to toggle.", "data": None}
            toggle_job(job_id, enabled)
            state_str = "enabled" if enabled else "paused"
            return {"ok": True, "summary": f"Job #{job_id} {state_str}.", "data": None}

        # ── Create job ─────────────────────────────────────────────────────
        if not query:
            return {"ok": False, "summary": "Provide a query to schedule.", "data": None}
        if not recipient:
            return {"ok": False, "summary": "Provide a recipient email.", "data": None}

        job_name = name or f"Scheduled: {query[:40]}"
        job_id   = save_job(
            name        = job_name,
            query       = query,
            recipient   = recipient,
            frequency   = frequency,
            day_of_week = day_of_week,
            run_time    = run_time,
            table       = table,
        )

        freq_str = (
            f"every {day_of_week.capitalize()} at {run_time}" if frequency == "weekly"
            else f"daily at {run_time}" if frequency == "daily"
            else f"monthly on the 1st at {run_time}"
        )

        return {
            "ok"     : True,
            "summary": (
                f"🗓️ Scheduled report **\"{job_name}\"** — {freq_str}.\n"
                f"Will email to **{recipient}**."
            ),
            "data"   : {
                "job_id"   : job_id,
                "name"     : job_name,
                "frequency": freq_str,
                "recipient": recipient,
                "query"    : query,
            },
        }
