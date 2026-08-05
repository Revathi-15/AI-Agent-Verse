"""
run.py — Single entry point
============================
    python run.py

Starts:
  1. FastAPI backend  → http://127.0.0.1:8000
  2. Scheduler thread → background (recurring email reports)
  3. Dash frontend    → http://127.0.0.1:8050

Stop with Ctrl+C.
"""

import sys
import os
import threading
import time
import webbrowser
import uvicorn

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BACKEND_PORT  = 8000
FRONTEND_PORT = 8050
HOST          = "127.0.0.1"


def _run_backend():
    from backend.api import app as fastapi_app
    uvicorn.run(
        fastapi_app,
        host      = HOST,
        port      = BACKEND_PORT,
        log_level = "warning",
    )


def start_backend():
    t = threading.Thread(target=_run_backend, daemon=True, name="fastapi")
    t.start()
    import socket
    for _ in range(40):
        try:
            with socket.create_connection((HOST, BACKEND_PORT), timeout=0.1):
                break
        except OSError:
            time.sleep(0.1)
    print(f"  ✓ Backend  →  http://{HOST}:{BACKEND_PORT}")


def start_scheduler():
    """Start the recurring-report scheduler in a background thread."""
    try:
        from backend.tools.scheduler_tool import start_scheduler as _start
        _start()
        print("  ✓ Scheduler → running (checks every 30s)")
    except Exception as e:
        print(f"  ⚠ Scheduler not started: {e}")


def _open_browser():
    time.sleep(2.5)
    webbrowser.open(f"http://{HOST}:{FRONTEND_PORT}")


def start_frontend():
    from frontend.app    import app
    from frontend.layout import build_layout
    import frontend.callbacks  # noqa: F401 — registers callbacks

    app.layout = build_layout()

    print(f"  ✓ Frontend →  http://{HOST}:{FRONTEND_PORT}")
    print("\n  Press Ctrl+C to stop all servers.\n")

    app.run(
        host         = HOST,
        port         = FRONTEND_PORT,
        debug        = False,
        use_reloader = False,
    )


if __name__ == "__main__":
    print("\n🚀  NL → SQL Enterprise Platform  v5")
    print("─" * 42)

    start_backend()
    start_scheduler()

    threading.Thread(target=_open_browser, daemon=True, name="browser").start()

    start_frontend()   # blocks until Ctrl+C
