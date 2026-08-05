# frontend/callbacks.py — Enterprise callbacks v5

import json
import uuid
import requests
import dash
from dash import Input, Output, State, ctx, dcc, html, ALL, MATCH
import dash_bootstrap_components as dbc

from frontend.app    import app
from frontend.layout import (
    user_bubble, bot_bubble, render_bot_response, render_dashboard,
    _pill, _status_step, _build_profile_ui,
    ACCENT, ACCENT2, ACCENT3, ACCENT4, ACCENT5,
    DIM, MUTED, BORDER, BG_CARD, BG_DEEP, BG_SIDE, BG_POP,
)

API = "http://127.0.0.1:8000"

BAR_HIDE = {"display": "none"}
BAR_SHOW = {
    "padding": "8px 16px", "background": "#0d1520",
    "border": f"1px solid {BORDER}", "borderRadius": "8px",
    "marginBottom": "8px", "marginLeft": "8px",
    "marginRight": "8px", "display": "block",
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _render_history(history: list) -> list:
    """Render full chat history list into Dash components."""
    welcome = bot_bubble([
        html.Div([
            html.Div("✦ NL → SQL  v5", style={
                "background": f"linear-gradient(90deg,{ACCENT},{ACCENT2})",
                "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent",
                "fontWeight": "700", "fontSize": "1rem", "marginBottom": "8px"}),
            dcc.Markdown(
                "Upload a **CSV** using the **+** button, then ask me anything.\n\n"
                "Click **ℹ About** in the header to see all capabilities.",
                style={"fontSize": "0.88rem", "color": DIM, "lineHeight": "1.6"}),
        ])
    ])
    rendered = [welcome]
    for h in history:
        rendered.append(user_bubble(h["user"]))
        extras = h.get("extras") or h.get("data") or {}
        # Dashboard special render
        if h.get("is_dashboard") and extras.get("panels"):
            rendered.append(bot_bubble([
                dcc.Markdown(h.get("reply",""), style={
                    "fontSize":"0.9rem","color":"#d1d5db","marginBottom":"8px"}),
                render_dashboard(extras),
            ]))
        else:
            rendered.append(bot_bubble(render_bot_response(
                reply      = h.get("reply",""),
                sql        = h.get("sql"),
                columns    = h.get("columns"),
                rows       = h.get("rows"),
                user_msg   = h["user"],
                chart_type = h.get("chart_type"),
                extras     = extras,
                msg_id     = h.get("msg_id"),
            )))
    return rendered


def _first_words(text: str, n: int = 6) -> str:
    """Return first n words of text as a conversation title."""
    words = text.strip().split()
    title = " ".join(words[:n])
    return title + ("…" if len(words) > n else "")


def _save_history_api(session_id: str, title: str, history: list, table: str = ""):
    """Fire-and-forget POST to /history."""
    try:
        requests.post(f"{API}/history", json={
            "session_id": session_id,
            "title":      title,
            "messages":   history,
            "table_name": table,
        }, timeout=4)
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════════════
# HISTORY SIDEBAR CALLBACKS
# ════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("history-list",     "children"),
    Output("sidebar-username", "children"),
    Output("sidebar-role",     "children"),
    Input("history-poll",      "n_intervals"),
    Input("new-chat-btn",      "n_clicks"),
    prevent_initial_call=False,
)
def refresh_history(n_intervals, new_chat):
    """Poll /history every 30s and on new-chat click."""
    try:
        resp  = requests.get(f"{API}/history?limit=60", timeout=4).json()
        convs = resp.get("conversations", [])
        health = requests.get(f"{API}/health", timeout=2).json()
        user  = health.get("current_user", "admin")
        role  = health.get("current_role",  "admin")
    except Exception:
        convs = []
        user  = "admin"
        role  = "admin"

    if not convs:
        empty = html.Div("No conversations yet.\nAsk something to start.",
            style={"color": MUTED, "fontSize": "0.74rem",
                   "padding": "16px 10px", "lineHeight": "1.6"})
        return [empty], user, role

    # Group into Pinned / Today / Yesterday / Older
    from datetime import datetime, timedelta
    now       = datetime.utcnow()
    today     = now.date()
    yesterday = (now - timedelta(days=1)).date()

    groups   = {"📌 Pinned": [], "Today": [], "Yesterday": [], "Recent": []}
    for c in convs:
        if c.get("pinned"):
            groups["📌 Pinned"].append(c)
        else:
            try:
                dt = datetime.fromisoformat(str(c.get("updated_at",""))[:19])
                d  = dt.date()
            except Exception:
                d = today
            if d == today:
                groups["Today"].append(c)
            elif d == yesterday:
                groups["Yesterday"].append(c)
            else:
                groups["Recent"].append(c)

    items = []
    for label, group in groups.items():
        if not group:
            continue
        items.append(html.Div(label, className="hist-section-label"))
        for c in group:
            sid    = c.get("session_id","")
            title  = c.get("title","Untitled")[:32]
            ts     = str(c.get("updated_at",""))[:16].replace("T"," ")
            pinned = bool(c.get("pinned"))
            items.append(html.Div([
                html.Div([
                    html.Span("○", style={
                        "fontSize":"0.7rem","color":MUTED,"marginRight":"7px",
                        "flexShrink":"0"}),
                    html.Div([
                        html.Div(title, className="hist-title"),
                        html.Div(ts,    className="hist-meta"),
                    ], style={"minWidth":"0","flex":"1"}),
                    html.Button("📌" if pinned else "○",
                        id={"type":"hist-pin","index":sid},
                        n_clicks=0, className="hist-pin-btn",
                        title="Pin / unpin"),
                    html.Button("✕",
                        id={"type":"hist-del","index":sid},
                        n_clicks=0, className="hist-del-btn",
                        title="Delete conversation"),
                ], style={"display":"flex","alignItems":"center","width":"100%"}),
                # Hidden store for session id
                dcc.Store(id={"type":"hist-sid","index":sid}, data=sid),
            ], id={"type":"hist-item","index":sid},
               className="hist-item",
               n_clicks=0))

    role_color = {
        "admin":ACCENT,"manager":ACCENT3,"analyst":ACCENT2,"viewer":MUTED
    }.get(role, MUTED)
    role_label = html.Span(role, style={"color": role_color})
    return items, user, role_label


@app.callback(
    Output("chat-history",        "children",  allow_duplicate=True),
    Output("chat-store",          "data",      allow_duplicate=True),
    Output("current-session-id",  "data",      allow_duplicate=True),
    Input({"type":"hist-item","index":ALL}, "n_clicks"),
    State({"type":"hist-sid","index":ALL},  "data"),
    prevent_initial_call=True,
)
def load_conversation(clicks, sids):
    if not any(c for c in (clicks or []) if c):
        return dash.no_update, dash.no_update, dash.no_update
    # Find which one was clicked
    triggered = ctx.triggered_id
    if not triggered:
        return dash.no_update, dash.no_update, dash.no_update
    sid = triggered.get("index","")
    if not sid:
        return dash.no_update, dash.no_update, dash.no_update
    try:
        conv = requests.get(f"{API}/history/{sid}", timeout=5).json()
    except Exception:
        return dash.no_update, dash.no_update, dash.no_update
    messages = conv.get("messages", [])
    rendered = _render_history(messages)
    return rendered, messages, sid


@app.callback(
    Output("history-list", "children", allow_duplicate=True),
    Input({"type":"hist-del","index":ALL}, "n_clicks"),
    State({"type":"hist-sid","index":ALL}, "data"),
    prevent_initial_call=True,
)
def delete_history_item(clicks, sids):
    if not any(c for c in (clicks or []) if c):
        return dash.no_update
    triggered = ctx.triggered_id
    if not triggered:
        return dash.no_update
    sid = triggered.get("index","")
    try:
        requests.delete(f"{API}/history/{sid}", timeout=4)
    except Exception:
        pass
    return dash.no_update   # history-poll will refresh


@app.callback(
    Output("history-list", "children", allow_duplicate=True),
    Input({"type":"hist-pin","index":ALL}, "n_clicks"),
    State({"type":"hist-sid","index":ALL}, "data"),
    prevent_initial_call=True,
)
def pin_history_item(clicks, sids):
    if not any(c for c in (clicks or []) if c):
        return dash.no_update
    triggered = ctx.triggered_id
    if not triggered:
        return dash.no_update
    sid = triggered.get("index","")
    try:
        resp    = requests.get(f"{API}/history/{sid}", timeout=3).json()
        pinned  = not bool(resp.get("pinned", False))
        requests.patch(f"{API}/history/{sid}/pin",
                       json={"pinned": pinned}, timeout=4)
    except Exception:
        pass
    return dash.no_update


@app.callback(
    Output("chat-history",       "children",  allow_duplicate=True),
    Output("chat-store",         "data",      allow_duplicate=True),
    Output("current-session-id", "data",      allow_duplicate=True),
    Input("new-chat-btn",        "n_clicks"),
    prevent_initial_call=True,
)
def new_chat(n):
    new_sid = str(uuid.uuid4())
    welcome = bot_bubble([
        html.Div([
            html.Div("✦ NL → SQL  v5", style={
                "background": f"linear-gradient(90deg,{ACCENT},{ACCENT2})",
                "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent",
                "fontWeight": "700", "fontSize": "1rem", "marginBottom": "8px"}),
            dcc.Markdown(
                "Upload a **CSV** using the **+** button, then ask me anything.\n\n"
                "Click **ℹ About** in the header to see all capabilities.",
                style={"fontSize": "0.88rem", "color": DIM, "lineHeight": "1.6"}),
            html.Div([
                _pill("💬 NL→SQL",  ACCENT),
                html.Span("·", style={"color": BORDER, "margin": "0 6px"}),
                _pill("📊 Charts",  ACCENT3),
                html.Span("·", style={"color": BORDER, "margin": "0 6px"}),
                _pill("📧 Email",   ACCENT4),
                html.Span("·", style={"color": BORDER, "margin": "0 6px"}),
                _pill("🤖 Agents",  ACCENT2),
            ], style={"marginTop": "10px", "display": "flex",
                      "alignItems": "center", "flexWrap": "wrap", "gap": "4px"}),
        ])
    ])
    return [welcome], [], new_sid


# ════════════════════════════════════════════════════════════════════════════
# + POPOVER MENU  (show/hide + popover, trigger upload modal from it)
# ════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("plus-popover-menu", "style"),
    Input("plus-btn",           "n_clicks"),
    State("plus-popover-menu",  "style"),
    prevent_initial_call=True,
)
def toggle_plus_menu(n, current_style):
    if not n:
        return dash.no_update
    is_visible = current_style and current_style.get("display") != "none"
    return {"display": "none"} if is_visible else {"display": "block"}


@app.callback(
    Output("upload-modal",      "is_open"),
    Output("plus-popover-menu", "style", allow_duplicate=True),
    Input("plus-upload-row",    "n_clicks"),
    State("upload-modal",       "is_open"),
    prevent_initial_call=True,
)
def open_upload_from_menu(n, is_open):
    if not n:
        return dash.no_update, dash.no_update
    return True, {"display": "none"}


# ── MCP submenu toggle (show when hovering Connectors row) ───────────────────
@app.callback(
    Output("mcp-submenu",        "style"),
    Output("mcp-server-list",    "children"),
    Output("tool-count-badge",   "children"),
    Input("plus-connectors-row", "n_clicks"),
    State("mcp-submenu",         "style"),
    State("mcp-toggles",         "data"),
    prevent_initial_call=True,
)
def toggle_mcp_submenu(n, current_style, toggles):
    if not n:
        return dash.no_update, dash.no_update, dash.no_update

    is_visible = current_style and current_style.get("display") != "none"
    if is_visible:
        return {"display": "none"}, dash.no_update, dash.no_update

    # Fetch server list from backend
    try:
        data    = requests.get(f"{API}/mcp-servers", timeout=4).json()
        servers = data.get("servers", {})
    except Exception:
        servers = {}

    toggles = toggles or {}
    total_tools  = sum(s.get("count", 0) for s in servers.values())
    active_tools = sum(s.get("active", 0) for s in servers.values())
    badge_text   = f"{active_tools} active · {total_tools} in catalog"

    server_items = []
    for srv_name, srv in servers.items():
        color    = srv.get("color", ACCENT)
        icon     = srv.get("icon", "🔧")
        count    = srv.get("count", 0)
        active_c = srv.get("active", 0)
        enabled  = toggles.get(srv_name, True)   # default on

        # Build tools sub-list
        tool_rows = [
            html.Div([
                html.Span(t.get("emoji","🔧"), style={"marginRight":"5px","fontSize":"0.8rem"}),
                html.Span(t.get("name",""), style={"fontWeight":"600","fontSize":"0.72rem","color":DIM}),
                html.Span(" — ", style={"color":BORDER}),
                html.Span(t.get("desc",""), style={"color":MUTED,"fontSize":"0.7rem"}),
                html.Span("✓" if t.get("active") else "○",
                    style={"marginLeft":"auto","fontSize":"0.65rem",
                           "color":ACCENT3 if t.get("active") else MUTED,
                           "flexShrink":"0"}),
            ], className="tool-row")
            for t in srv.get("tools", [])
        ]

        toggle_class = "toggle-on" if enabled else "toggle-off"
        server_items.append(html.Div([
            # Server header row
            html.Div([
                html.Span(icon, style={"fontSize":"1rem","marginRight":"8px","flexShrink":"0"}),
                html.Div([
                    html.Div(srv_name,
                        style={"color":"#e5e7eb","fontWeight":"600","fontSize":"0.8rem"}),
                    html.Div(f"{active_c}/{count} tools active",
                        style={"color":MUTED,"fontSize":"0.66rem"}),
                ], style={"flex":"1","minWidth":"0"}),
                # Toggle switch
                html.Div(className=toggle_class,
                    id={"type":"mcp-toggle","index":srv_name},
                    n_clicks=0, title=f"Enable/disable {srv_name}"),
            ], className="server-row"),
            # Tools panel (always shown below each server)
            html.Div(tool_rows,
                className="server-tools-panel",
                id={"type":"server-tools-panel","index":srv_name},
                style={"display":"block" if enabled else "none"}),
        ]))

    submenu_style = {
        "display": "block",
        "position": "absolute", "bottom": "58px", "left": "228px",
        "zIndex": "9999", "background": BG_POP,
        "border": f"1px solid {BORDER}", "borderRadius": "14px",
        "padding": "8px", "minWidth": "300px", "maxWidth": "340px",
        "boxShadow": "0 16px 40px rgba(0,0,0,.6)",
        "maxHeight": "500px", "overflowY": "auto",
    }
    return submenu_style, server_items, badge_text


@app.callback(
    Output("mcp-toggles",                              "data"),
    Output({"type":"server-tools-panel","index":MATCH},"style"),
    Input({"type":"mcp-toggle","index":MATCH},          "n_clicks"),
    State({"type":"mcp-toggle","index":MATCH},          "id"),
    State("mcp-toggles",                               "data"),
    prevent_initial_call=True,
)
def toggle_server(n, toggle_id, toggles):
    if not n:
        return dash.no_update, dash.no_update
    toggles    = toggles or {}
    srv_name   = toggle_id.get("index","")
    new_state  = not toggles.get(srv_name, True)
    toggles[srv_name] = new_state
    panel_style = {"display":"block"} if new_state else {"display":"none"}
    return toggles, panel_style


# ════════════════════════════════════════════════════════════════════════════
# CSV UPLOAD
# ════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("upload-status",  "children"),
    Output("profile-panel",  "children"),
    Output("upload-modal",   "is_open", allow_duplicate=True),
    Input("csv-upload",      "contents"),
    State("csv-upload",      "filename"),
    prevent_initial_call=True,
)
def handle_upload(contents_list, filenames):
    if not contents_list:
        return "", [], dash.no_update
    if isinstance(contents_list, str):
        contents_list, filenames = [contents_list], [filenames]
    statuses, last_prof = [], []
    for contents, filename in zip(contents_list, filenames):
        b64 = contents.split(",", 1)[1]
        try:
            resp = requests.post(f"{API}/upload",
                json={"filename": filename, "file_content_b64": b64}, timeout=30)
            if resp.ok:
                statuses.append(html.Span(f"✓ {filename}",
                    style={"color":ACCENT3,"display":"block","fontSize":"0.8rem"}))
            else:
                msg = resp.json().get("detail", resp.text[:80])
                statuses.append(html.Span(f"✗ {filename}: {msg}",
                    style={"color":ACCENT5,"display":"block","fontSize":"0.8rem"}))
                continue
        except Exception as e:
            statuses.append(html.Span(f"⚠ {e}",
                style={"color":ACCENT4,"display":"block"}))
            continue
        try:
            prof = requests.get(f"{API}/profile", timeout=5).json()
            if "error" not in prof:
                last_prof = _build_profile_ui(prof)
        except Exception:
            pass
    return html.Div(statuses), last_prof, False


# ── Image upload → Image-to-SQL ──────────────────────────────────────────────
@app.callback(
    Output("image-upload-status","children"),
    Output("chat-history",       "children",  allow_duplicate=True),
    Output("chat-store",         "data",      allow_duplicate=True),
    Output("msg-counter",        "data",      allow_duplicate=True),
    Input("image-upload",        "contents"),
    State("image-upload",        "filename"),
    State("chat-store",          "data"),
    State("msg-counter",         "data"),
    prevent_initial_call=True,
)
def handle_image_upload(contents, filename, history, msg_counter):
    if not contents:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    try:
        mime_map = {"png":"image/png","jpg":"image/jpeg","jpeg":"image/jpeg",
                    "gif":"image/gif","webp":"image/webp"}
        ext  = (filename or "img.png").rsplit(".", 1)[-1].lower()
        mime = mime_map.get(ext, "image/png")
        b64  = contents.split(",", 1)[1]
        resp = requests.post(f"{API}/image-to-sql",
                             json={"image_b64": b64, "image_mime": mime}, timeout=60)
        data = resp.json()
    except Exception as e:
        return html.Span(f"⚠ {e}", style={"color":ACCENT5}), \
               dash.no_update, dash.no_update, dash.no_update
    msg_counter = (msg_counter or 0) + 1
    history = (history or []) + [{
        "user":       f"[Image: {filename}] → Analyse dashboard",
        "reply":      data.get("summary", data.get("reply","")),
        "sql":        data.get("sql"),
        "columns":    data.get("columns"),
        "rows":       data.get("rows"),
        "chart_type": data.get("chart_type"),
        "extras":     data.get("data"),
        "msg_id":     msg_counter,
    }]
    return (html.Span("✓ Image analysed", style={"color":ACCENT3}),
            _render_history(history), history, msg_counter)


# ════════════════════════════════════════════════════════════════════════════
# HEALTH POLL — status + LLM badge + tools panel + user badge
# ════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("health-status",      "children"),
    Output("header-llm-badge",   "children"),
    Output("current-user-badge", "children"),
    Input("health-poll",         "n_intervals"),
)
def poll_health(n):
    try:
        data   = requests.get(f"{API}/health", timeout=2).json()
        active = data.get("active_table") or (data.get("tables") or ["—"])[0]
        llm    = data.get("llm", "")
        user   = data.get("current_user", "admin")
        role   = data.get("current_role",  "admin")
        role_color = {"admin":ACCENT,"manager":ACCENT3,"analyst":ACCENT2,"viewer":MUTED}.get(role, MUTED)
        status = html.Div([
            html.Span("⬤ ", style={"color":ACCENT3,"fontWeight":"600","fontSize":"0.7rem"}),
            html.Span(active, style={"color":DIM,"fontSize":"0.7rem"}),
        ])
        user_badge = html.Span([
            html.Span(f"👤 {user} ", style={"color":DIM}),
            html.Span(f"[{role}]", style={"color":role_color,"fontWeight":"600"}),
        ])
        return status, f"⚡ {llm}", user_badge
    except Exception:
        return (html.Span("⬤ offline", style={"color":ACCENT5,"fontWeight":"600","fontSize":"0.7rem"}),
                "⚡ offline", "")


# ════════════════════════════════════════════════════════════════════════════
# MODE BUTTONS
# ════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("active-mode",     "data"),
    Output("chat-mode",       "className"),
    Output("tutor-mode",      "className"),
    Output("transform-mode",  "className"),
    Output("dashboard-mode",  "className"),
    Output("multiagent-mode", "className"),
    Input("chat-mode",        "n_clicks"),
    Input("tutor-mode",       "n_clicks"),
    Input("transform-mode",   "n_clicks"),
    Input("dashboard-mode",   "n_clicks"),
    Input("multiagent-mode",  "n_clicks"),
    prevent_initial_call=True,
)
def switch_mode(c1, c2, c3, c4, c5):
    t = ctx.triggered_id or "chat-mode"
    modes = {"chat-mode":"chat","tutor-mode":"tutor","transform-mode":"transform",
             "dashboard-mode":"dashboard","multiagent-mode":"multiagent"}
    active = modes.get(t, "chat")
    cls = lambda bid: "mode-btn active-mode" if bid == t else "mode-btn"
    return (active, cls("chat-mode"), cls("tutor-mode"), cls("transform-mode"),
            cls("dashboard-mode"), cls("multiagent-mode"))


# ── Sample query fill ─────────────────────────────────────────────────────────
@app.callback(
    Output("user-input", "value"),
    Input({"type":"sample-btn","index":ALL}, "n_clicks"),
    State({"type":"sample-btn","index":ALL}, "children"),
    prevent_initial_call=True,
)
def fill_sample(clicks, labels):
    t = ctx.triggered_id
    if not t or not any(clicks):
        return dash.no_update
    return labels[t["index"]]


# ════════════════════════════════════════════════════════════════════════════
# MAIN SEND MESSAGE — security guard + streaming + history save
# ════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("chat-history",        "children",  allow_duplicate=True),
    Output("chat-store",          "data",      allow_duplicate=True),
    Output("user-input",          "value",     allow_duplicate=True),
    Output("typing-indicator",    "className"),
    Output("stream-status-bar",   "children"),
    Output("stream-status-bar",   "style"),
    Output("msg-counter",         "data",      allow_duplicate=True),
    Output("last-query-store",    "data"),
    Output("current-session-id",  "data",      allow_duplicate=True),
    Input("send-btn",             "n_clicks"),
    Input("user-input",           "n_submit"),
    State("user-input",           "value"),
    State("chat-store",           "data"),
    State("active-mode",          "data"),
    State("msg-counter",          "data"),
    State("current-session-id",   "data"),
    prevent_initial_call=True,
)
def send_message(n_clicks, n_submit, user_msg, history, mode, msg_counter, session_id):
    HIDDEN  = "d-flex justify-content-start"

    if not user_msg or not user_msg.strip():
        return (dash.no_update,) * 9

    user_msg    = user_msg.strip()
    history     = history or []
    mode        = mode or "chat"
    msg_counter = (msg_counter or 0) + 1
    msg_id      = msg_counter

    steps_ui = []
    final    = None

    # ── Pick streaming endpoint based on mode ─────────────────────────────────
    endpoint = f"{API}/multi-agent" if mode == "multiagent" else f"{API}/stream"

    # ── SSE streaming ─────────────────────────────────────────────────────────
    try:
        with requests.post(endpoint,
                           json={"message": user_msg},
                           stream=True, timeout=90) as resp:
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    evt = json.loads(payload)
                except Exception:
                    continue
                etype = evt.get("type")
                if etype == "status":
                    step  = int(evt.get("step", len(steps_ui) + 1))
                    total = int(evt.get("total", 5))
                    steps_ui.append(_status_step(evt.get("text",""), step, total))
                elif etype == "agent_result":
                    steps_ui.append(html.Div(
                        html.Span(f"  ✓ [{evt.get('agent','')}] {evt.get('text','')}",
                            style={"fontSize":"0.7rem","color":ACCENT3}),
                        style={"marginBottom":"2px"}))
                elif etype == "result":
                    final = evt
                elif etype == "error":
                    final = {"reply": f"⚠ {evt.get('text','Error')}",
                             "error": evt.get("text")}
    except requests.exceptions.ConnectionError:
        final = {"reply": "⚠ **Cannot reach backend.** Is `python run.py` running?",
                 "error": "connection refused"}
    except Exception as e:
        # Fallback to synchronous endpoints
        ep_map = {"tutor":"/tutor","transform":"/transform","dashboard":"/dashboard"}
        ep = ep_map.get(mode, "/chat")
        try:
            r     = requests.post(f"{API}{ep}",
                        json={"message": user_msg, "mode": mode}, timeout=60)
            final = r.json()
        except Exception as e2:
            final = {"reply": f"⚠ Error: {e2}", "error": str(e2)}

    if not final:
        final = {"reply": "No response received.", "error": "no result"}

    extras = final.get("extras") or final.get("data") or {}
    reply  = final.get("reply") or final.get("summary") or ""

    # ── Dashboard special render ──────────────────────────────────────────────
    is_dash = mode == "dashboard" and extras.get("panels")
    history = history + [{
        "user":         user_msg,
        "reply":        reply,
        "sql":          final.get("sql"),
        "columns":      final.get("columns"),
        "rows":         final.get("rows"),
        "error":        final.get("error"),
        "chart_type":   final.get("chart_type"),
        "extras":       extras,
        "msg_id":       msg_id,
        "is_dashboard": is_dash,
    }]

    # ── Save to history store ─────────────────────────────────────────────────
    if not session_id:
        session_id = str(uuid.uuid4())
    _save_history_api(session_id, _first_words(user_msg), history)

    rendered  = _render_history(history)
    bar_style = BAR_HIDE if not steps_ui else BAR_SHOW

    return (rendered, history, "", HIDDEN,
            steps_ui, bar_style, msg_counter, user_msg, session_id)


# ════════════════════════════════════════════════════════════════════════════
# FEEDBACK  👍 / 👎
# ════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output({"type":"feedback-ack", "index":MATCH}, "children"),
    Input({"type":"thumbs-up",     "index":MATCH}, "n_clicks"),
    Input({"type":"thumbs-down",   "index":MATCH}, "n_clicks"),
    State({"type":"feedback-data", "index":MATCH}, "data"),
    prevent_initial_call=True,
)
def handle_feedback(up, down, fb_data):
    t = ctx.triggered_id
    if not t or (not up and not down):
        return dash.no_update
    rating = 1 if t["type"] == "thumbs-up" else -1
    try:
        requests.post(f"{API}/feedback", json={
            "query":  (fb_data or {}).get("query", ""),
            "sql":    (fb_data or {}).get("sql", ""),
            "rating": rating,
        }, timeout=4)
    except Exception:
        pass
    return "✓ Thanks!" if rating == 1 else "✓ Noted"


# ════════════════════════════════════════════════════════════════════════════
# AUDIT LOG PANEL
# ════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("audit-panel", "children"),
    Output("audit-panel", "style"),
    Input("audit-btn",    "n_clicks"),
    State("audit-panel",  "style"),
    prevent_initial_call=True,
)
def toggle_audit(n, cur_style):
    if cur_style and cur_style.get("display") == "block":
        return dash.no_update, {"display": "none"}
    try:
        entries = requests.get(f"{API}/audit?limit=20", timeout=4).json().get("entries", [])
    except Exception:
        return html.Span("Cannot load audit log.",
            style={"color":MUTED,"fontSize":"0.74rem"}), {"display":"block"}
    if not entries:
        return html.Span("No entries yet.",
            style={"color":MUTED,"fontSize":"0.74rem"}), {"display":"block"}

    rows = []
    for e in entries:
        rows.append(html.Div([
            html.Div([
                html.Span(str(e.get("ts",""))[:16],
                    style={"color":MUTED,"fontSize":"0.6rem","marginRight":"4px"}),
                html.Span(e.get("username",""),
                    style={"color":ACCENT3,"fontSize":"0.6rem","marginRight":"4px"}),
                html.Span(f"[{e.get('role','')}]",
                    style={"color":MUTED,"fontSize":"0.58rem"}),
            ]),
            html.Div(str(e.get("query",""))[:55],
                style={"color":DIM,"fontSize":"0.7rem"}),
            html.Div([
                html.Span(f"{e.get('rows',0)} rows",
                    style={"color":ACCENT2,"fontSize":"0.6rem","marginRight":"6px"}),
                html.Span(f"{e.get('elapsed_s',0):.2f}s",
                    style={"color":ACCENT4,"fontSize":"0.6rem"}),
            ]),
        ], style={"borderBottom":f"1px solid {BORDER}",
                  "paddingBottom":"4px","marginBottom":"4px"}))

    panel = html.Div([
        html.Div("AUDIT LOG", style={"color":MUTED,"fontSize":"0.6rem",
            "fontWeight":"700","letterSpacing":".1em","marginBottom":"6px"}),
        html.Div(rows, style={"maxHeight":"180px","overflowY":"auto"}),
    ])
    return panel, {"display":"block","marginTop":"6px"}


# ════════════════════════════════════════════════════════════════════════════
# GOOGLE SHEETS
# ════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("gsheets-status", "children"),
    Input("gsheets-btn",     "n_clicks"),
    State("last-query-store","data"),
    prevent_initial_call=True,
)
def export_to_sheets(n, last_query):
    if not n:
        return dash.no_update
    try:
        resp = requests.post(f"{API}/export/google-sheets",
            json={"to":"","subject":f"NL→SQL: {(last_query or 'Export')[:40]}"},
            timeout=30)
        data = resp.json()
        if data.get("ok"):
            url = data.get("data",{}).get("url","")
            return html.Div([
                html.Span("✓ Exported! ", style={"color":ACCENT3,"fontSize":"0.7rem"}),
                html.A("Open →", href=url, target="_blank",
                    style={"color":ACCENT,"fontSize":"0.7rem"}),
            ])
        return html.Span(data.get("summary","Failed")[:60],
            style={"color":ACCENT5,"fontSize":"0.7rem"})
    except Exception as e:
        return html.Span(str(e)[:60], style={"color":ACCENT5,"fontSize":"0.7rem"})


# ════════════════════════════════════════════════════════════════════════════
# EMAIL MODAL
# ════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("email-modal", "is_open"),
    Input("open-email-btn","n_clicks"),
    Input("email-cancel",  "n_clicks"),
    State("email-modal",   "is_open"),
    prevent_initial_call=True,
)
def toggle_email_modal(o, c, is_open):
    return not is_open


@app.callback(
    Output("email-status","children"),
    Output("email-modal", "is_open", allow_duplicate=True),
    Input("email-send",   "n_clicks"),
    State("email-to",     "value"),
    State("email-subject","value"),
    State("email-body",   "value"),
    prevent_initial_call=True,
)
def send_email(n, to, subject, body):
    if not n or not to:
        return dash.no_update, dash.no_update
    try:
        resp = requests.post(f"{API}/email-report",
            json={"to":to,"subject":subject or "NL→SQL Report","body":body or ""},
            timeout=30)
        data = resp.json()
        if data.get("ok"):
            return html.Span("✓ Sent!", style={"color":ACCENT3}), False
        return html.Span(data.get("summary","Failed")[:80],
            style={"color":ACCENT5}), dash.no_update
    except Exception as e:
        return html.Span(str(e), style={"color":ACCENT5}), dash.no_update


# ════════════════════════════════════════════════════════════════════════════
# SCHEDULE MODAL
# ════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("schedule-modal","is_open"),
    Input("open-sched-btn", "n_clicks"),
    Input("sched-cancel",   "n_clicks"),
    State("schedule-modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_sched_modal(o, c, is_open):
    return not is_open


@app.callback(
    Output("sched-status",  "children"),
    Output("schedule-modal","is_open", allow_duplicate=True),
    Input("sched-save",     "n_clicks"),
    State("sched-email",    "value"),
    State("sched-freq",     "value"),
    State("sched-day",      "value"),
    State("sched-time",     "value"),
    State("last-query-store","data"),
    prevent_initial_call=True,
)
def save_schedule(n, email, freq, day, t, last_query):
    if not n or not email:
        return dash.no_update, dash.no_update
    query = last_query or "Show top 10 records"
    try:
        resp = requests.post(f"{API}/schedule", json={
            "query":query,"recipient":email,
            "frequency":freq or "weekly","day_of_week":day or "monday",
            "run_time":t or "08:00","action":"create",
        }, timeout=10)
        data = resp.json()
        if data.get("ok"):
            return html.Span("✓ Scheduled!", style={"color":ACCENT3}), False
        return html.Span(data.get("summary","Failed")[:80],
            style={"color":ACCENT5}), dash.no_update
    except Exception as e:
        return html.Span(str(e), style={"color":ACCENT5}), dash.no_update


# ════════════════════════════════════════════════════════════════════════════
# SPEECH — browser Web Speech API (clientside)
# ════════════════════════════════════════════════════════════════════════════

app.clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) return window.dash_clientside.no_update;
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) {
            alert("Speech recognition requires Chrome or Edge.");
            return window.dash_clientside.no_update;
        }
        const rec = new SR();
        rec.lang = 'en-US';
        rec.interimResults = false;
        rec.maxAlternatives = 1;
        rec.start();
        return new Promise(function(resolve) {
            rec.onresult = function(e) {
                resolve(e.results[0][0].transcript);
            };
            rec.onerror = function() {
                resolve(window.dash_clientside.no_update);
            };
        });
    }
    """,
    Output("user-input", "value", allow_duplicate=True),
    Input("speech-btn",  "n_clicks"),
    prevent_initial_call=True,
)


# ════════════════════════════════════════════════════════════════════════════
# ABOUT MODAL  — ℹ About button in header
# ════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("about-modal", "is_open"),
    Input("about-btn",    "n_clicks"),
    State("about-modal",  "is_open"),
    prevent_initial_call=True,
)
def toggle_about(n, is_open):
    if not n:
        return dash.no_update
    return not is_open


# ════════════════════════════════════════════════════════════════════════════
# HISTORY SIDEBAR — popover + connectors + new-chat callbacks
# ════════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("plus-popover-menu", "style"),
    Input("plus-btn",           "n_clicks"),
    State("plus-popover-menu",  "style"),
    prevent_initial_call=True,
)
def toggle_plus_menu(n, cur_style):
    if not n:
        return dash.no_update
    visible = cur_style and cur_style.get("display") != "none"
    return {"display": "none"} if visible else {"display": "block"}


@app.callback(
    Output("upload-modal",      "is_open",              allow_duplicate=True),
    Output("plus-popover-menu", "style",                allow_duplicate=True),
    Input("plus-upload-row",    "n_clicks"),
    State("upload-modal",       "is_open"),
    prevent_initial_call=True,
)
def open_upload_from_menu(n, is_open):
    if not n:
        return dash.no_update, dash.no_update
    return True, {"display": "none"}


@app.callback(
    Output("mcp-submenu",      "style"),
    Output("mcp-server-list",  "children"),
    Output("tool-count-badge", "children"),
    Input("plus-connectors-row","n_clicks"),
    State("mcp-submenu",       "style"),
    State("mcp-toggles",       "data"),
    prevent_initial_call=True,
)
def toggle_mcp_submenu(n, cur_style, toggles):
    if not n:
        return dash.no_update, dash.no_update, dash.no_update

    visible = cur_style and cur_style.get("display") != "none"
    if visible:
        return {"display": "none"}, dash.no_update, dash.no_update

    try:
        data    = requests.get(f"{API}/mcp-servers", timeout=4).json()
        servers = data.get("servers", {})
    except Exception:
        servers = {}

    toggles      = toggles or {}
    total_tools  = sum(s.get("count", 0)  for s in servers.values())
    active_tools = sum(s.get("active", 0) for s in servers.values())
    badge        = f"{active_tools} active · {total_tools} in catalog"

    items = []
    for srv_name, srv in servers.items():
        color   = srv.get("color", ACCENT)
        icon    = srv.get("icon",  "🔧")
        count   = srv.get("count", 0)
        active_c= srv.get("active",0)
        enabled = toggles.get(srv_name, True)

        tool_rows = [
            html.Div([
                html.Span(t.get("emoji","🔧"),
                    style={"marginRight":"5px","fontSize":"0.8rem"}),
                html.Span(t.get("name",""),
                    style={"fontWeight":"600","fontSize":"0.72rem","color":DIM}),
                html.Span(" — ", style={"color":BORDER}),
                html.Span(t.get("desc",""),
                    style={"color":MUTED,"fontSize":"0.7rem"}),
                html.Span("✓" if t.get("active") else "○",
                    style={"marginLeft":"auto","fontSize":"0.65rem","flexShrink":"0",
                           "color":ACCENT3 if t.get("active") else MUTED}),
            ], style={"display":"flex","alignItems":"center","gap":"4px",
                      "padding":"4px 6px","borderRadius":"5px",
                      "fontSize":"0.72rem","color":MUTED})
            for t in srv.get("tools", [])
        ]

        toggle_cls = "toggle-on" if enabled else "toggle-off"
        items.append(html.Div([
            html.Div([
                html.Span(icon, style={"fontSize":"1rem","marginRight":"8px","flexShrink":"0"}),
                html.Div([
                    html.Div(srv_name,
                        style={"color":"#e5e7eb","fontWeight":"600","fontSize":"0.8rem"}),
                    html.Div(f"{active_c}/{count} tools",
                        style={"color":MUTED,"fontSize":"0.66rem"}),
                ], style={"flex":"1","minWidth":"0"}),
                html.Div(className=toggle_cls,
                    id={"type":"mcp-toggle","index":srv_name},
                    n_clicks=0, title=f"Toggle {srv_name}"),
            ], style={"display":"flex","alignItems":"center","gap":"8px",
                      "padding":"8px 10px","borderRadius":"8px","cursor":"pointer",
                      "borderBottom":f"1px solid {BORDER}"}),
            html.Div(tool_rows,
                id={"type":"server-tools-panel","index":srv_name},
                style={"background":"#0a0c10","borderRadius":"8px","padding":"6px 8px",
                       "margin":"2px 0 6px","border":f"1px solid {BORDER}",
                       "display":"block" if enabled else "none"}),
        ]))

    submenu_style = {
        "display":"block","position":"absolute",
        "bottom":"58px","left":"228px","zIndex":"9999",
        "background":BG_POP,"border":f"1px solid {BORDER}",
        "borderRadius":"14px","padding":"8px",
        "minWidth":"300px","maxWidth":"340px",
        "boxShadow":"0 16px 40px rgba(0,0,0,.6)",
        "maxHeight":"500px","overflowY":"auto",
    }
    return submenu_style, items, badge


@app.callback(
    Output("mcp-toggles",                               "data"),
    Output({"type":"server-tools-panel","index":MATCH}, "style"),
    Input({"type":"mcp-toggle","index":MATCH},          "n_clicks"),
    State({"type":"mcp-toggle","index":MATCH},          "id"),
    State("mcp-toggles",                               "data"),
    prevent_initial_call=True,
)
def toggle_server(n, toggle_id, toggles):
    if not n:
        return dash.no_update, dash.no_update
    toggles   = toggles or {}
    srv_name  = toggle_id.get("index", "")
    new_state = not toggles.get(srv_name, True)
    toggles[srv_name] = new_state
    return toggles, {"display":"block"} if new_state else {"display":"none"}


@app.callback(
    Output("chat-history",       "children",  allow_duplicate=True),
    Output("chat-store",         "data",      allow_duplicate=True),
    Output("current-session-id", "data",      allow_duplicate=True),
    Input("new-chat-btn",        "n_clicks"),
    prevent_initial_call=True,
)
def new_chat_btn(n):
    new_sid = str(uuid.uuid4())
    welcome = bot_bubble([
        html.Div([
            html.Div("✦ NL → SQL  v5", style={
                "background": f"linear-gradient(90deg,{ACCENT},{ACCENT2})",
                "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent",
                "fontWeight": "700", "fontSize": "1rem", "marginBottom": "8px"}),
            dcc.Markdown(
                "Upload a **CSV** using the **+** button, then ask me anything.\n\n"
                "Click **ℹ About** to see all capabilities.",
                style={"fontSize": "0.88rem", "color": DIM, "lineHeight": "1.6"}),
            html.Div([
                _pill("💬 NL→SQL", ACCENT),
                html.Span("·", style={"color": BORDER, "margin": "0 6px"}),
                _pill("📊 Charts", ACCENT3),
                html.Span("·", style={"color": BORDER, "margin": "0 6px"}),
                _pill("🤖 Agents", ACCENT2),
            ], style={"marginTop":"10px","display":"flex",
                      "alignItems":"center","flexWrap":"wrap","gap":"4px"}),
        ])
    ])
    return [welcome], [], new_sid
