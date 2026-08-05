# frontend/layout.py — Enterprise UI v5
# Layout: Left history sidebar | Center chat | Right tools panel (collapsed)

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc

# ── Design tokens ─────────────────────────────────────────────────────────────
ACCENT  = "#00d4ff"
ACCENT2 = "#7c3aed"
ACCENT3 = "#10b981"
ACCENT4 = "#f59e0b"
ACCENT5 = "#ef4444"
BG_DEEP = "#0a0c10"
BG_CARD = "#111318"
BG_SIDE = "#0d0f14"
BG_POP  = "#161b24"
BORDER  = "#1e2330"
MUTED   = "#6b7280"
DIM     = "#9ca3af"

SAMPLE_QUERIES = [
    "Which country has the highest GDP?",
    "Show top 10 countries by GDP",
    "Plot GDP vs GDP per capita",
    "Show GDP distribution histogram",
    "Compare top 5 countries by GDP share",
    "Show growth of highest GDP country over time",
    "Countries with GDP above 1 trillion",
    "Correlation between GDP and population",
    "Clean this dataset",
    "Discover insights",
    "Show table schema",
    "Build an executive dashboard",
]

CUSTOM_CSS = """
/* ── Animations ─────────────────────────────────────────────────────── */
@keyframes bounce   {0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-6px)}}
@keyframes fadeIn   {from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@keyframes slideUp  {from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
@keyframes slideRight{from{opacity:0;transform:translateX(-10px)}to{opacity:1;transform:translateX(0)}}
@keyframes pulse    {0%,100%{opacity:1}50%{opacity:.45}}
@keyframes shimmer  {0%{background-position:-200% 0}100%{background-position:200% 0}}

/* ── Chat ────────────────────────────────────────────────────────────── */
#typing-indicator{display:none!important}
#typing-indicator.typing-visible{display:flex!important}
.chat-msg{animation:fadeIn .22s ease}
.stream-step{animation:slideRight .18s ease}

/* ── + Popover menu ──────────────────────────────────────────────────── */
#plus-popover-menu{
  position:absolute;bottom:58px;left:0;z-index:9999;
  background:#161b24;border:1px solid #1e2330;
  border-radius:14px;padding:6px;min-width:220px;
  box-shadow:0 16px 40px rgba(0,0,0,.6);
  animation:slideUp .18s ease;
}
.plus-menu-item{
  display:flex;align-items:center;gap:10px;
  padding:9px 14px;border-radius:8px;cursor:pointer;
  color:#9ca3af;font-size:.82rem;transition:all .12s;
  position:relative;
}
.plus-menu-item:hover{background:#1e2330;color:#f3f4f6}
.plus-menu-item .kbd{
  margin-left:auto;background:#0a0c10;border:1px solid #1e2330;
  border-radius:4px;padding:1px 6px;font-size:.65rem;color:#6b7280;
}

/* ── MCP Server sub-panel ────────────────────────────────────────────── */
#mcp-submenu{
  position:absolute;bottom:58px;left:228px;z-index:9999;
  background:#161b24;border:1px solid #1e2330;
  border-radius:14px;padding:8px;min-width:280px;max-width:320px;
  box-shadow:0 16px 40px rgba(0,0,0,.6);
  animation:slideRight .18s ease;max-height:480px;overflow-y:auto;
}
.server-row{
  display:flex;align-items:center;gap:8px;
  padding:8px 10px;border-radius:8px;cursor:pointer;
  transition:background .12s;border-bottom:1px solid #1e2330;
}
.server-row:last-child{border-bottom:none}
.server-row:hover{background:#1e2330}
.server-tools-panel{
  background:#0a0c10;border-radius:8px;
  padding:6px 8px;margin:2px 0 6px;
  border:1px solid #1e2330;
}
.tool-row{
  display:flex;align-items:center;gap:6px;
  padding:4px 6px;border-radius:5px;
  font-size:.74rem;color:#6b7280;
}
.tool-row:hover{background:#111318;color:#9ca3af}
.toggle-on { width:28px;height:16px;background:#10b981;border-radius:9px;
  position:relative;cursor:pointer;flex-shrink:0;transition:background .2s;}
.toggle-off{ width:28px;height:16px;background:#1e2330;border-radius:9px;
  position:relative;cursor:pointer;flex-shrink:0;transition:background .2s;}
.toggle-on::after,.toggle-off::after{
  content:'';position:absolute;top:2px;width:12px;height:12px;
  background:white;border-radius:50%;transition:left .2s;}
.toggle-on::after {left:14px;}
.toggle-off::after{left:2px;}

/* ── History sidebar ─────────────────────────────────────────────────── */
.hist-item{
  padding:8px 10px;border-radius:8px;cursor:pointer;
  border-left:2px solid transparent;transition:all .14s;
}
.hist-item:hover{background:#111318;border-left-color:#00d4ff}
.hist-item.active{background:#111318;border-left-color:#00d4ff}
.hist-item .hist-title{
  font-size:.78rem;color:#d1d5db;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;max-width:170px;
}
.hist-item .hist-meta{font-size:.65rem;color:#4b5563;margin-top:2px}
.hist-section-label{
  font-size:.6rem;font-weight:700;letter-spacing:.1em;
  color:#374151;text-transform:uppercase;
  padding:8px 10px 3px;
}
.hist-pin-btn{
  background:transparent;border:none;color:#374151;
  font-size:.7rem;cursor:pointer;padding:2px 4px;
  border-radius:4px;transition:color .12s;margin-left:auto;flex-shrink:0;
}
.hist-pin-btn:hover{color:#f59e0b}
.hist-del-btn{
  background:transparent;border:none;color:#374151;
  font-size:.7rem;cursor:pointer;padding:2px 4px;
  border-radius:4px;transition:color .12s;
}
.hist-del-btn:hover{color:#ef4444}

/* ── Buttons & inputs ────────────────────────────────────────────────── */
.send-btn:hover{transform:scale(1.07);box-shadow:0 6px 20px rgba(0,212,255,.4)!important}
.send-btn{transition:all .15s!important}
.plus-btn:hover{background:rgba(0,212,255,.25)!important;transform:scale(1.05)}
.plus-btn{transition:all .15s!important}
.speech-btn-active{background:rgba(239,68,68,.2)!important;border-color:#ef4444!important;
  color:#ef4444!important;animation:pulse 1s infinite!important}
.action-btn:hover{opacity:.85;transform:translateY(-1px)}
.action-btn{transition:all .15s!important}
.upload-zone:hover{border-color:#00d4ff!important;background:#0d1520!important}
#user-input:focus{border-color:#00d4ff!important;
  box-shadow:0 0 0 3px rgba(0,212,255,.12)!important;outline:none!important}

/* ── Chat bubbles ────────────────────────────────────────────────────── */
.chat-bubble-bot:hover{border-color:#2a3040!important}
.kpi-card{transition:transform .15s,box-shadow .15s}
.kpi-card:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,212,255,.15)!important}

/* ── Mode buttons ────────────────────────────────────────────────────── */
.mode-btn.active-mode{background:rgba(0,212,255,.15)!important;
  border-color:#00d4ff!important;color:#00d4ff!important}

/* ── Scrollbar ───────────────────────────────────────────────────────── */
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-track{background:#0a0c10}
::-webkit-scrollbar-thumb{background:#1e2330;border-radius:2px}
::-webkit-scrollbar-thumb:hover{background:#00d4ff40}

/* ── New-chat skeleton shimmer ───────────────────────────────────────── */
.skeleton{
  background:linear-gradient(90deg,#111318 25%,#1e2330 50%,#111318 75%);
  background-size:200% 100%;animation:shimmer 1.4s infinite;
  border-radius:6px;height:10px;
}
"""


# ── Smart chart auto-selector ─────────────────────────────────────────────────
def _auto_chart_type(df: pd.DataFrame, hint: str, user_msg: str = "") -> str:
    if hint and hint != "none" and hint in {"bar","line","pie","scatter","histogram"}:
        return hint
    if df is None or df.empty:
        return "none"
    cols     = list(df.columns)
    num_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    cat_cols = [c for c in cols if not pd.api.types.is_numeric_dtype(df[c])]
    year_x   = next((c for c in cols if c.lower() == "year"
                     or (str(c).isdigit() and len(str(c)) == 4)), None)
    n   = len(df)
    msg = user_msg.lower()
    if any(w in msg for w in ("growth","trend","over time","history","year","progress","timeline")):
        return "line"
    if any(w in msg for w in ("share","percent","proportion","composition","pie","breakdown")):
        return "pie" if n <= 12 else "bar"
    if any(w in msg for w in ("distribution","histogram","spread","frequency")):
        return "histogram"
    if any(w in msg for w in ("correlat","scatter","vs ","versus","relationship")):
        return "scatter"
    if year_x:              return "line"
    if n == 1:              return "none"
    if len(num_cols) >= 2 and not cat_cols: return "scatter"
    if n <= 10 and cat_cols: return "pie"
    if n > 50 and len(num_cols) == 1: return "histogram"
    return "bar"


def _build_figure(df: pd.DataFrame, chart_type: str, user_msg: str = ""):
    if df is None or df.empty: return None
    chart_type = _auto_chart_type(df, chart_type, user_msg)
    if chart_type == "none": return None

    cols     = list(df.columns)
    num_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    cat_cols = [c for c in cols if not pd.api.types.is_numeric_dtype(df[c])]
    year_x   = next((c for c in cols if c.lower() == "year"
                     or (str(c).isdigit() and len(str(c)) == 4)), None)
    x = year_x if year_x else (cat_cols[0] if cat_cols else cols[0])
    y = num_cols[0] if num_cols else (cols[1] if len(cols) > 1 else cols[0])
    PAL = [ACCENT, ACCENT2, ACCENT3, ACCENT4, "#8b5cf6", "#06b6d4", "#f97316"]
    MAX = 40
    fig = None

    if chart_type == "line":
        df_s = df.sort_values(x) if x in df.columns else df
        if len(num_cols) > 1 and not year_x:
            id_c = cat_cols[:1]
            df_l = df_s.melt(id_vars=id_c, value_vars=num_cols[:8],
                             var_name="Year", value_name="Value")
            fig  = px.line(df_l, x="Year", y="Value",
                           color=id_c[0] if id_c else None,
                           title="Comparison over time", template="plotly_dark",
                           markers=True, line_shape="spline", color_discrete_sequence=PAL)
        else:
            fig = px.line(df_s, x=x, y=y, title=f"{y} over {x}",
                          template="plotly_dark", markers=True, line_shape="spline",
                          color_discrete_sequence=[ACCENT])
            fig.update_traces(fill="tozeroy", fillcolor=f"{ACCENT}18")
        fig.update_traces(line_width=2.5, marker_size=7)

    elif chart_type == "bar":
        dfp   = (df.sort_values(y, ascending=False).head(MAX)
                 if y in df.columns else df.head(MAX))
        n     = len(dfp)
        title = f"Top {n} {x} by {y}" if len(df) > MAX else f"{y} by {x}"
        fig   = px.bar(dfp, x=x, y=y, title=title, template="plotly_dark",
                       color=y, color_continuous_scale="Teal",
                       text_auto=".2s" if n > 1 else False)
        fig.update_traces(marker_line_width=0, textfont_size=9)
        fig.update_layout(xaxis_tickangle=-35 if n > 8 else 0)

    elif chart_type == "pie":
        dfp = df.head(12)
        fig = px.pie(dfp, names=x, values=y, title=f"{y} share",
                     template="plotly_dark", color_discrete_sequence=PAL, hole=0.35)
        fig.update_traces(textposition="inside", textinfo="percent+label",
                          pull=[0.03] * len(dfp))

    elif chart_type == "scatter":
        y2  = num_cols[1] if len(num_cols) > 1 else y
        col = cat_cols[0] if cat_cols and cat_cols[0] != x else None
        fig = px.scatter(df, x=y, y=y2, color=col,
                         hover_name=x if cat_cols else None,
                         title=f"{y2} vs {y}", template="plotly_dark",
                         color_discrete_sequence=PAL, opacity=0.75)
        fig.update_traces(marker_size=8, marker_line_width=0.4,
                          marker_line_color="white")

    elif chart_type == "histogram":
        fig = px.histogram(df, x=y, title=f"Distribution of {y}",
                           template="plotly_dark", color_discrete_sequence=[ACCENT],
                           nbins=min(30, max(10, len(df)//3)), marginal="box")
        fig.update_traces(marker_line_width=0.4, marker_line_color=BG_DEEP)

    if fig:
        fig.update_layout(
            paper_bgcolor=BG_DEEP, plot_bgcolor=BG_DEEP,
            font_color="#e5e7eb", font_family="Inter, sans-serif",
            title_font=dict(size=13, color=DIM),
            margin=dict(l=12, r=12, t=44, b=52 if len(df) > 8 else 28),
            coloraxis_colorbar=dict(thickness=10, tickfont_size=9),
            xaxis=dict(gridcolor=BORDER, tickfont_size=9, zeroline=False),
            yaxis=dict(gridcolor=BORDER, tickfont_size=9, zeroline=False, tickformat=".3s"),
            legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=BORDER, font_size=10,
                        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hoverlabel=dict(bgcolor=BG_CARD, bordercolor=BORDER,
                            font_size=11, font_family="Inter"),
        )
    return fig


# ── Small UI helpers ──────────────────────────────────────────────────────────
def _pill(text: str, color: str) -> html.Span:
    return html.Span(text, style={
        "background": f"{color}15", "color": color,
        "border": f"1px solid {color}30", "borderRadius": "20px",
        "padding": "2px 10px", "fontSize": "0.7rem", "fontWeight": "600"})


def _section_label(text: str) -> html.Div:
    return html.Div(text, style={"color": MUTED, "fontSize": "0.6rem",
        "fontWeight": "700", "letterSpacing": ".12em",
        "textTransform": "uppercase", "marginBottom": "6px"})


def _mode_btn(label: str, btn_id: str) -> html.Button:
    return html.Button(label, id=btn_id, n_clicks=0, className="mode-btn",
        style={"background": "transparent", "border": f"1px solid {BORDER}",
               "borderRadius": "6px", "color": DIM, "fontSize": "0.7rem",
               "padding": "4px 10px", "cursor": "pointer", "transition": "all .15s"})


def user_bubble(text: str) -> html.Div:
    return html.Div(html.Div([
        html.Span("You", style={"fontSize": "0.6rem", "color": "rgba(255,255,255,.4)",
            "fontWeight": "700", "letterSpacing": ".06em",
            "display": "block", "marginBottom": "3px"}),
        html.Span(text, style={"fontSize": "0.88rem", "lineHeight": "1.55"}),
    ], className="chat-bubble-user chat-msg", style={
        "background": "linear-gradient(135deg,#1d4ed8,#0369a1)", "color": "#f0f9ff",
        "padding": "10px 16px 12px", "borderRadius": "16px 16px 4px 16px",
        "maxWidth": "68%", "boxShadow": "0 4px 20px rgba(0,148,255,.2)"}),
    className="d-flex justify-content-end",
    style={"marginBottom": "4px", "paddingRight": "8px"})


def bot_bubble(children) -> html.Div:
    return html.Div(html.Div(children, className="chat-bubble-bot chat-msg", style={
        "background": BG_CARD, "border": f"1px solid {BORDER}",
        "padding": "12px 16px", "borderRadius": "4px 16px 16px 16px",
        "maxWidth": "96%", "boxShadow": "0 4px 16px rgba(0,0,0,.4)",
        "transition": "border-color .2s"}),
    className="d-flex justify-content-start",
    style={"marginBottom": "6px", "paddingLeft": "8px"})


def typing_indicator() -> html.Div:
    def dot(d): return html.Span(style={
        "width": "6px", "height": "6px", "borderRadius": "50%",
        "background": ACCENT, "display": "inline-block", "margin": "0 2px",
        "animation": f"bounce 1.1s ease-in-out {d}s infinite"})
    return html.Div(html.Div([dot(0), dot(.18), dot(.36)], style={
        "padding": "10px 14px", "background": BG_CARD,
        "border": f"1px solid {BORDER}",
        "borderRadius": "4px 14px 14px 14px",
        "display": "inline-flex", "alignItems": "center"}),
    id="typing-indicator", className="d-flex justify-content-start",
    style={"paddingLeft": "8px", "marginBottom": "8px"})


def _status_step(text: str, step: int, total: int, done: bool = False) -> html.Div:
    color = ACCENT3 if done else ACCENT
    bar_w = f"{int(step / total * 100)}%" if total else "100%"
    return html.Div([
        html.Div([
            html.Span(text, style={"fontSize": "0.78rem", "color": color, "fontWeight": "500"}),
            html.Span(f" {step}/{total}", style={"fontSize": "0.7rem", "color": MUTED, "marginLeft": "6px"}),
        ]),
        html.Div(html.Div(style={"width": bar_w, "height": "2px", "background": color,
            "borderRadius": "2px", "transition": "width .3s"}),
        style={"background": BORDER, "borderRadius": "2px", "height": "2px", "marginTop": "4px"}),
    ], className="stream-step", style={"marginBottom": "4px"})


def _feedback_row(msg_id: int, sql: str, query: str) -> html.Div:
    return html.Div([
        html.Span("Was this helpful?",
            style={"color": MUTED, "fontSize": "0.72rem", "marginRight": "8px"}),
        html.Button("👍", id={"type": "thumbs-up",   "index": msg_id}, n_clicks=0,
            style={"background": "transparent", "border": f"1px solid {BORDER}",
                   "borderRadius": "6px", "color": DIM, "fontSize": "0.85rem",
                   "padding": "2px 8px", "cursor": "pointer", "marginRight": "4px"}),
        html.Button("👎", id={"type": "thumbs-down", "index": msg_id}, n_clicks=0,
            style={"background": "transparent", "border": f"1px solid {BORDER}",
                   "borderRadius": "6px", "color": DIM, "fontSize": "0.85rem",
                   "padding": "2px 8px", "cursor": "pointer"}),
        html.Span(id={"type": "feedback-ack",  "index": msg_id},
            style={"fontSize": "0.7rem", "color": ACCENT3, "marginLeft": "8px"}),
        dcc.Store(id={"type": "feedback-data", "index": msg_id},
            data={"sql": sql, "query": query}),
    ], style={"marginTop": "10px", "display": "flex", "alignItems": "center"})


def _build_profile_ui(prof: dict) -> list:
    def stat_pill(v, lbl, col):
        return html.Div([
            html.Div(v, style={"color": col, "fontWeight": "700", "fontSize": "0.88rem"}),
            html.Div(lbl, style={"color": MUTED, "fontSize": "0.62rem"}),
        ], style={"background": f"{col}10", "border": f"1px solid {col}25",
                  "borderRadius": "8px", "padding": "4px 10px", "textAlign": "center"})
    items = [
        html.Div("DATA PROFILE", style={"color": MUTED, "fontSize": "0.6rem",
            "fontWeight": "700", "letterSpacing": ".12em", "marginBottom": "8px"}),
        html.Div([
            stat_pill(f"{prof['rows']:,}", "rows", ACCENT),
            stat_pill(str(prof['cols']), "cols", ACCENT2),
        ], style={"display": "flex", "gap": "6px", "marginBottom": "6px"}),
        html.Div(f"Cols: {', '.join(prof.get('meta_cols', []))}", style={
            "color": DIM, "fontSize": "0.68rem", "lineHeight": "1.5"}),
    ]
    if prof.get("year_cols"):
        items.append(html.Div(f"Years: {prof['year_cols']}",
            style={"color": DIM, "fontSize": "0.68rem"}))
    if prof.get("best_year"):
        items.append(html.Div(f"Best year: {prof['best_year']}",
            style={"color": ACCENT, "fontSize": "0.68rem",
                   "fontWeight": "600", "marginTop": "4px"}))
    return [html.Div(items)]


# ── Bot response renderer ─────────────────────────────────────────────────────
def render_bot_response(reply, sql, columns, rows, user_msg,
                        chart_type=None, extras=None, msg_id=None) -> list:
    parts = [dcc.Markdown(reply or "", style={
        "fontSize": "0.9rem", "lineHeight": "1.6",
        "color": "#d1d5db", "marginBottom": "8px"})]

    # SQL accordion
    if sql and not sql.startswith("--"):
        parts.append(html.Details([
            html.Summary(html.Span([
                html.Span("⌗ ", style={"color": ACCENT}), "View SQL"]),
                style={"cursor": "pointer", "color": MUTED,
                       "fontSize": "0.72rem", "userSelect": "none"}),
            html.Div(dcc.Markdown(f"```sql\n{sql}\n```",
                style={"fontSize": "0.73rem", "margin": "6px 0 0"}),
                style={"background": "#0a0c10", "border": f"1px solid {BORDER}",
                       "borderRadius": "6px", "padding": "8px 12px", "marginTop": "6px"}),
        ], style={"marginBottom": "10px"}))

    extras = extras or {}

    # Tutor content
    if extras.get("tutor_text"):
        parts.append(html.Div(dcc.Markdown(extras["tutor_text"],
            style={"fontSize": "0.84rem", "lineHeight": "1.7", "color": "#d1d5db"}),
            style={"background": "#0d1520", "border": f"1px solid {BORDER}",
                   "borderRadius": "8px", "padding": "12px 16px", "marginBottom": "10px"}))

    # Optimizer
    if extras.get("llm_analysis"):
        parts.append(html.Div([
            html.Div("⚡ Query Analysis", style={"color": ACCENT4, "fontSize": "0.7rem",
                "fontWeight": "700", "letterSpacing": ".1em", "marginBottom": "6px"}),
            dcc.Markdown(extras["llm_analysis"],
                style={"fontSize": "0.82rem", "lineHeight": "1.6", "color": "#d1d5db"}),
        ], style={"background": "#0d1520", "border": f"1px solid {ACCENT4}25",
                  "borderRadius": "8px", "padding": "12px 16px", "marginBottom": "10px"}))

    # Vector search results
    if extras.get("results") and not rows:
        vr = extras["results"]
        parts.append(html.Div([
            html.Div("🔮 Similar Past Queries", style={"color": ACCENT2,
                "fontSize": "0.7rem", "fontWeight": "700",
                "letterSpacing": ".1em", "marginBottom": "8px"}),
            html.Div([
                html.Div([
                    html.Span(str(r.get("score", "")),
                        style={"background": f"{ACCENT2}20", "color": ACCENT2,
                               "borderRadius": "4px", "padding": "1px 6px",
                               "fontSize": "0.66rem", "marginRight": "8px"}),
                    html.Span(r.get("query", "")[:60],
                        style={"color": DIM, "fontSize": "0.8rem"}),
                ], style={"marginBottom": "5px",
                          "borderBottom": f"1px solid {BORDER}", "paddingBottom": "5px"})
                for r in vr[:5]
            ]),
        ], style={"background": BG_DEEP, "border": f"1px solid {BORDER}",
                  "borderRadius": "8px", "padding": "12px", "marginBottom": "10px"}))

    if not rows or not columns:
        if msg_id is not None:
            parts.append(_feedback_row(msg_id, sql or "", reply or ""))
        return parts

    df = pd.DataFrame(rows, columns=columns)

    # Single-value KPI card
    if len(df) == 1 and len(columns) <= 2:
        num_c = [c for c in columns if pd.api.types.is_numeric_dtype(df[c])]
        cat_c = [c for c in columns if not pd.api.types.is_numeric_dtype(df[c])]
        label = df.iloc[0][cat_c[0]] if cat_c else columns[0]
        val   = df.iloc[0][num_c[0]] if num_c else df.iloc[0][columns[-1]]
        try:
            v   = float(val)
            fmt = (f"${v/1e12:.2f}T" if abs(v) >= 1e12 else
                   f"${v/1e9:.2f}B"  if abs(v) >= 1e9  else
                   f"${v/1e6:.2f}M"  if abs(v) >= 1e6  else f"{v:,.2f}")
        except Exception:
            fmt = str(val)
        parts.append(html.Div([
            html.Div(str(label),
                style={"color": DIM, "fontSize": "0.8rem", "marginBottom": "4px"}),
            html.Div(fmt, style={
                "background": f"linear-gradient(90deg,{ACCENT},{ACCENT2})",
                "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent",
                "fontWeight": "800", "fontSize": "2rem", "lineHeight": "1.1"}),
            html.Div(num_c[0] if num_c else "",
                style={"color": MUTED, "fontSize": "0.7rem", "marginTop": "2px"}),
        ], className="kpi-card", style={
            "background": BG_DEEP, "border": f"1px solid {BORDER}",
            "borderLeft": f"3px solid {ACCENT}", "borderRadius": "8px",
            "padding": "14px 18px", "marginBottom": "10px", "display": "inline-block"}))
        if msg_id is not None:
            parts.append(_feedback_row(msg_id, sql or "", reply or ""))
        return parts

    # Stats pills
    parts.append(html.Div([
        html.Span(f"  {len(df)} rows", style={
            "background": "#0d2137", "color": ACCENT,
            "border": f"1px solid {ACCENT}30", "borderRadius": "20px",
            "padding": "2px 10px", "fontSize": "0.7rem",
            "marginRight": "6px", "fontWeight": "600"}),
        html.Span(f"  {len(columns)} columns", style={
            "background": "#120d2e", "color": ACCENT2,
            "border": f"1px solid {ACCENT2}30", "borderRadius": "20px",
            "padding": "2px 10px", "fontSize": "0.7rem", "fontWeight": "600"}),
    ], style={"marginBottom": "10px"}))

    # Data table
    parts.append(html.Div(dash_table.DataTable(
        data=rows, columns=[{"name": c, "id": c} for c in columns],
        page_size=10, sort_action="native", filter_action="native",
        style_table={"overflowX": "auto", "borderRadius": "8px",
                     "border": f"1px solid {BORDER}"},
        style_header={"backgroundColor": "#0a0c10", "color": ACCENT,
            "fontWeight": "700", "fontSize": "0.67rem",
            "border": f"1px solid {BORDER}", "textTransform": "uppercase",
            "letterSpacing": "0.08em", "padding": "8px 14px"},
        style_cell={"backgroundColor": BG_CARD, "color": "#cbd5e1",
            "fontSize": "0.79rem", "border": f"1px solid {BORDER}",
            "padding": "8px 14px", "textAlign": "left",
            "fontFamily": "Inter, sans-serif",
            "whiteSpace": "normal", "height": "auto"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#0e1117"},
            {"if": {"state": "selected"},
             "backgroundColor": f"{ACCENT}12", "border": f"1px solid {ACCENT}60"}],
        style_filter={"backgroundColor": "#0a0c10", "color": DIM,
            "border": f"1px solid {BORDER}", "fontSize": "0.74rem"},
    ), style={"marginBottom": "12px"}))

    # Smart chart
    resolved = _auto_chart_type(df, chart_type or "none", user_msg or "")
    if resolved != "none":
        fig = _build_figure(df, resolved, user_msg or "")
        if fig:
            icons = {"bar":"📊","line":"📈","pie":"🥧","scatter":"🔵","histogram":"📉"}
            parts.append(html.Div(
                html.Span(f"{icons.get(resolved,'')} {resolved.capitalize()} chart",
                    style={"color": MUTED, "fontSize": "0.66rem",
                           "fontWeight": "600", "letterSpacing": ".08em",
                           "textTransform": "uppercase"}),
                style={"marginBottom": "4px"}))
            parts.append(dcc.Graph(figure=fig,
                config={"displayModeBar": True, "responsive": True,
                        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                        "toImageButtonOptions": {"format": "png", "filename": "chart"}},
                style={"height": "400px", "borderRadius": "10px",
                       "overflow": "hidden", "border": f"1px solid {BORDER}",
                       "marginTop": "4px"}))

    if msg_id is not None:
        parts.append(_feedback_row(msg_id, sql or "", reply or ""))
    return parts


# ── Dashboard panel renderer ──────────────────────────────────────────────────
def render_dashboard(data: dict) -> html.Div:
    panels = data.get("panels", [])
    if not panels:
        return html.Div("No panels generated.", style={"color": MUTED})
    cards = []
    for panel in panels:
        ptype = panel.get("type")
        title = panel.get("title", "")
        if ptype == "kpi":
            kpi_items = panel.get("data", [])
            cards.append(html.Div([
                html.Div(title, style={"color": MUTED, "fontSize": "0.64rem",
                    "fontWeight": "700", "letterSpacing": ".1em",
                    "textTransform": "uppercase", "marginBottom": "8px"}),
                html.Div([
                    html.Div([
                        html.Div(k.get("value",""),
                            style={"color": ACCENT, "fontWeight": "800", "fontSize": "1.4rem"}),
                        html.Div(k.get("label",""),
                            style={"color": DIM, "fontSize": "0.72rem"}),
                        html.Div(k.get("sub",""),
                            style={"color": MUTED, "fontSize": "0.64rem"}),
                    ], className="kpi-card", style={
                        "background": BG_DEEP, "border": f"1px solid {BORDER}",
                        "borderTop": f"2px solid {ACCENT}", "borderRadius": "8px",
                        "padding": "12px 16px", "flex": "1", "minWidth": "100px"})
                    for k in kpi_items
                ], style={"display": "flex", "gap": "8px", "flexWrap": "wrap"}),
            ], style={"marginBottom": "12px"}))
            continue
        rows_data = panel.get("rows", [])
        cols_data = panel.get("columns", [])
        if not rows_data:
            continue
        df  = pd.DataFrame(rows_data, columns=cols_data)
        fig = _build_figure(df, ptype, title)
        if fig:
            cards.append(html.Div(dcc.Graph(figure=fig,
                config={"displayModeBar": False, "responsive": True},
                style={"height": "300px", "borderRadius": "8px",
                       "border": f"1px solid {BORDER}"}),
            style={"marginBottom": "12px"}))
    return html.Div(cards)


# ── Welcome / capability panel (shown when no data loaded) ───────────────────
def _welcome_capability_panel() -> html.Div:
    capabilities = [
        {
            "emoji": "💬", "title": "Natural Language → SQL",
            "color": ACCENT,
            "example": '"Show me total revenue by product for last 30 days"',
            "desc": "Uses ai_sql_generate → Runs query → Returns formatted results + chart",
        },
        {
            "emoji": "📊", "title": "Instant Dashboard Creation",
            "color": ACCENT4,
            "example": '"Create an executive dashboard for e-commerce sales"',
            "desc": "Uses mb_dashboard_template_executive → Full interactive dashboard",
        },
        {
            "emoji": "🔍", "title": "Deep Database Exploration",
            "color": ACCENT2,
            "example": '"What tables are related to orders and show relationships"',
            "desc": "Uses db_relationships_detect → Complete ER diagram info",
        },
        {
            "emoji": "🛡️", "title": "Enterprise-Grade Security",
            "color": ACCENT5,
            "example": '"DROP TABLE users"',
            "desc": "Destructive SQL is blocked at the database level. All queries are logged in the audit trail.",
        },
        {
            "emoji": "🔮", "title": "Semantic History Search",
            "color": "#8b5cf6",
            "example": '"Show the report I generated last week"',
            "desc": "Uses vector_search → Finds similar past queries semantically",
        },
        {
            "emoji": "🤖", "title": "Multi-Agent Pipeline",
            "color": ACCENT3,
            "example": '"Analyse this dataset deeply"',
            "desc": "Planner → Schema → SQL → Validation → Visualization → Explanation",
        },
    ]
    cards = []
    for cap in capabilities:
        cards.append(html.Div([
            html.Div([
                html.Span(cap["emoji"], style={"fontSize": "1.1rem", "marginRight": "8px"}),
                html.Span(cap["title"], style={
                    "color": cap["color"], "fontWeight": "600", "fontSize": "0.82rem"}),
            ], style={"marginBottom": "6px", "display": "flex", "alignItems": "center"}),
            html.Div(cap["example"], style={
                "background": BG_DEEP, "color": DIM, "fontSize": "0.74rem",
                "fontFamily": "monospace", "padding": "5px 10px",
                "borderRadius": "6px", "marginBottom": "5px",
                "border": f"1px solid {cap['color']}20"}),
            html.Div(cap["desc"], style={"color": MUTED, "fontSize": "0.72rem"}),
        ], style={
            "background": BG_CARD, "border": f"1px solid {BORDER}",
            "borderLeft": f"3px solid {cap['color']}",
            "borderRadius": "8px", "padding": "12px 14px", "marginBottom": "8px",
        }))

    return html.Div([
        html.Div([
            html.Div("✦ NL → SQL  v5", style={
                "background": f"linear-gradient(90deg,{ACCENT},{ACCENT2})",
                "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent",
                "fontWeight": "800", "fontSize": "1.1rem", "marginBottom": "6px"}),
            html.Div("What Can You Do?", style={
                "color": "#e5e7eb", "fontSize": "0.92rem",
                "fontWeight": "600", "marginBottom": "4px"}),
            dcc.Markdown(
                "Upload a **CSV** with **+**, then ask anything in natural language.",
                style={"fontSize": "0.82rem", "color": DIM, "lineHeight": "1.5",
                       "marginBottom": "14px"}),
        ]),
        html.Div(cards),
        # Tool count badge row
        html.Div([
            html.Span("🔧 ", style={"fontSize": "0.8rem"}),
            html.Span("15 active tools", style={
                "color": ACCENT3, "fontWeight": "600", "fontSize": "0.78rem"}),
            html.Span("  ·  ", style={"color": BORDER}),
            html.Span("134 in catalog", style={"color": DIM, "fontSize": "0.78rem"}),
            html.Span("  ·  ", style={"color": BORDER}),
            html.Span("Full audit trail enabled", style={"color": MUTED, "fontSize": "0.78rem"}),
        ], style={"marginTop": "12px", "display": "flex",
                  "alignItems": "center", "flexWrap": "wrap", "gap": "4px"}),
    ])


# ── Left history sidebar ──────────────────────────────────────────────────────
def _history_sidebar() -> html.Div:
    return html.Div([
        # Top: logo + new chat button
        html.Div([
            html.Div([
                html.Span("NL", style={
                    "background": f"linear-gradient(90deg,{ACCENT},{ACCENT2})",
                    "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent",
                    "fontWeight": "800", "fontSize": "1rem"}),
                html.Span("→SQL", style={"color": "#4b5563", "fontWeight": "300", "fontSize": "0.9rem"}),
            ]),
            html.Button("+ New", id="new-chat-btn", n_clicks=0, style={
                "background": f"{ACCENT}15", "border": f"1px solid {ACCENT}30",
                "borderRadius": "8px", "color": ACCENT, "fontSize": "0.75rem",
                "fontWeight": "600", "padding": "5px 12px", "cursor": "pointer",
                "transition": "all .15s",
            }),
        ], style={"display": "flex", "justifyContent": "space-between",
                  "alignItems": "center", "padding": "14px 12px 10px",
                  "borderBottom": f"1px solid {BORDER}"}),

        # Search conversations
        html.Div(dbc.Input(
            id="hist-search", type="text", placeholder="Search conversations...",
            style={"background": BG_DEEP, "color": "#f3f4f6",
                   "border": f"1px solid {BORDER}", "borderRadius": "8px",
                   "fontSize": "0.76rem", "padding": "7px 10px"}),
        style={"padding": "8px 10px"}),

        # History list (filled by callback)
        html.Div(id="history-list", style={
            "flex": "1", "overflowY": "auto", "padding": "0 6px 8px"}),

        # Bottom: user badge
        html.Div([
            html.Div("👤", style={"fontSize": "1rem", "marginRight": "8px"}),
            html.Div([
                html.Div(id="sidebar-username",
                    style={"color": DIM, "fontSize": "0.75rem", "fontWeight": "600"}),
                html.Div(id="sidebar-role",
                    style={"color": MUTED, "fontSize": "0.62rem"}),
            ]),
        ], style={"display": "flex", "alignItems": "center",
                  "padding": "10px 12px", "borderTop": f"1px solid {BORDER}",
                  "background": BG_SIDE}),

        dcc.Interval(id="history-poll", interval=30_000, n_intervals=0),
    ], style={
        "width": "220px", "flexShrink": "0",
        "background": BG_SIDE, "borderRight": f"1px solid {BORDER}",
        "height": "100vh", "display": "flex", "flexDirection": "column",
        "overflowY": "hidden",
    })


# ── Right settings/tools column ───────────────────────────────────────────────
def _tools_sidebar() -> html.Div:
    return html.Div([
        # Data profile card
        html.Div(id="profile-panel", style={"minHeight": "10px"}),
        html.Div(style={"height": "1px", "background": BORDER, "margin": "10px 0"}),

        # Health
        html.Div(id="health-status", style={"fontSize": "0.75rem", "minHeight": "36px"}),
        dcc.Interval(id="health-poll", interval=6_000, n_intervals=0),
        html.Div(style={"height": "1px", "background": BORDER, "margin": "10px 0"}),

        # Mode selector
        _section_label("Mode"),
        html.Div([
            _mode_btn("💬 Chat",       "chat-mode"),
            _mode_btn("🎓 Tutor",      "tutor-mode"),
            _mode_btn("🔀 Transform",  "transform-mode"),
            _mode_btn("📊 Dashboard",  "dashboard-mode"),
            _mode_btn("🤖 Multi-Agent","multiagent-mode"),
        ], style={"display": "flex", "flexWrap": "wrap",
                  "gap": "4px", "marginBottom": "10px"}),
        dcc.Store(id="active-mode", data="chat"),
        html.Div(style={"height": "1px", "background": BORDER, "margin": "10px 0"}),

        # Export
        _section_label("Export"),
        html.Div([
            html.A(dbc.Button("CSV",   size="sm", outline=True, color="success",
                className="action-btn me-1 mb-1",
                style={"fontSize": "0.68rem", "borderRadius": "6px"}),
                href="http://127.0.0.1:8000/export", target="_blank"),
            html.A(dbc.Button("Excel", size="sm", outline=True, color="info",
                className="action-btn me-1 mb-1",
                style={"fontSize": "0.68rem", "borderRadius": "6px"}),
                href="http://127.0.0.1:8000/export/excel", target="_blank"),
            html.A(dbc.Button("JSON",  size="sm", outline=True, color="warning",
                className="action-btn me-1 mb-1",
                style={"fontSize": "0.68rem", "borderRadius": "6px"}),
                href="http://127.0.0.1:8000/export/json", target="_blank"),
            html.A(dbc.Button("PDF",   size="sm", outline=True, color="danger",
                className="action-btn mb-1",
                style={"fontSize": "0.68rem", "borderRadius": "6px"}),
                href="http://127.0.0.1:8000/export/pdf", target="_blank"),
        ], style={"marginBottom": "6px"}),
        dbc.Button("📗 Google Sheets", id="gsheets-btn", size="sm", outline=True,
            color="success", className="action-btn w-100 mb-1",
            style={"fontSize": "0.68rem", "borderRadius": "6px"}),
        dbc.Button("📧 Email Report", id="open-email-btn", size="sm", outline=True,
            color="primary", className="action-btn w-100 mb-1",
            style={"fontSize": "0.68rem", "borderRadius": "6px"}),
        dbc.Button("🗓️ Schedule",    id="open-sched-btn", size="sm", outline=True,
            color="secondary", className="action-btn w-100 mb-1",
            style={"fontSize": "0.68rem", "borderRadius": "6px"}),
        html.Div(id="gsheets-status",
            style={"fontSize": "0.7rem", "marginTop": "4px", "minHeight": "14px"}),
        html.Div(style={"height": "1px", "background": BORDER, "margin": "10px 0"}),

        # Audit log
        dbc.Button("📋 Audit Log", id="audit-btn", size="sm", outline=True,
            color="secondary", className="action-btn w-100 mb-1",
            style={"fontSize": "0.68rem", "borderRadius": "6px"}),
        html.Div(id="audit-panel"),
        html.Div(style={"height": "1px", "background": BORDER, "margin": "10px 0"}),

        # Sample queries
        _section_label("Try a query"),
        html.Div([
            html.Button(q, id={"type": "sample-btn", "index": i}, n_clicks=0,
                className="sample-btn",
                style={"background": "transparent", "border": f"1px solid {BORDER}",
                       "borderRadius": "6px", "color": DIM, "fontSize": "0.68rem",
                       "padding": "4px 8px", "marginBottom": "4px", "marginRight": "4px",
                       "cursor": "pointer", "display": "inline-block"})
            for i, q in enumerate(SAMPLE_QUERIES)
        ], className="mt-1"),
    ], style={
        "width": "210px", "flexShrink": "0",
        "background": BG_SIDE, "borderLeft": f"1px solid {BORDER}",
        "height": "100vh", "overflowY": "auto", "padding": "12px",
    })


# ── Claude-style + popover menu (rendered into DOM, shown/hidden by JS) ───────
def _plus_popover() -> html.Div:
    """
    Floating popover that appears above the + button.
    Contains: Upload files/CSV | MCP Connectors (with sub-panel) | Web Search
    The sub-panel for MCP servers is a second floating div rendered beside it.
    """
    return html.Div([
        # ── Main + menu ───────────────────────────────────────────────────────
        html.Div([
            # Upload CSV / images row
            html.Div([
                html.Span("📎", style={"fontSize": "1rem"}),
                html.Div([
                    html.Div("Add files or photos",
                        style={"fontSize": "0.82rem", "color": "#e5e7eb", "fontWeight": "500"}),
                    html.Div("CSV, TSV, images",
                        style={"fontSize": "0.68rem", "color": MUTED}),
                ]),
                html.Span("Ctrl+U", style={
                    "marginLeft": "auto", "background": "#0a0c10",
                    "border": f"1px solid {BORDER}", "borderRadius": "4px",
                    "padding": "1px 6px", "fontSize": "0.62rem", "color": MUTED}),
            ], id="plus-upload-row", className="plus-menu-item",
               style={"cursor": "pointer"}),

            html.Div(style={"height": "1px", "background": BORDER, "margin": "2px 0"}),

            # MCP Connectors row (hoverable → shows sub-panel)
            html.Div([
                html.Span("⚡", style={"fontSize": "1rem"}),
                html.Div([
                    html.Div("Connectors",
                        style={"fontSize": "0.82rem", "color": "#e5e7eb", "fontWeight": "500"}),
                    html.Div("MCP servers & tools",
                        style={"fontSize": "0.68rem", "color": MUTED}),
                ]),
                html.Span("›", style={"marginLeft": "auto", "color": MUTED, "fontSize": "1rem"}),
            ], id="plus-connectors-row", className="plus-menu-item"),

            # Tool access row
            html.Div([
                html.Span("🔧", style={"fontSize": "1rem"}),
                html.Div([
                    html.Div("Tool access",
                        style={"fontSize": "0.82rem", "color": "#e5e7eb", "fontWeight": "500"}),
                    html.Div(id="tool-count-badge",
                        style={"fontSize": "0.68rem", "color": MUTED}),
                ]),
                html.Span("›", style={"marginLeft": "auto", "color": MUTED, "fontSize": "1rem"}),
            ], id="plus-tools-row", className="plus-menu-item"),

            html.Div(style={"height": "1px", "background": BORDER, "margin": "2px 0"}),

            # Web search row
            html.Div([
                html.Span("🌐", style={"fontSize": "1rem"}),
                html.Div("Web search",
                    style={"fontSize": "0.82rem", "color": "#e5e7eb", "fontWeight": "500"}),
            ], className="plus-menu-item",
               style={"cursor": "pointer", "opacity": "0.5"}),
        ], id="plus-popover-menu",
           style={"display": "none"}),  # hidden by default

        # ── MCP server sub-panel (shown on hover of Connectors row) ──────────
        html.Div(id="mcp-submenu", style={"display": "none"},
            children=[
                html.Div([
                    html.Div("MCP SERVERS", style={
                        "color": MUTED, "fontSize": "0.6rem", "fontWeight": "700",
                        "letterSpacing": ".1em", "padding": "4px 4px 8px"}),
                    html.Div(id="mcp-server-list"),
                ]),
            ]),

        # ── Upload modal (triggered by plus-upload-row click) ─────────────────
        _upload_modal(),
    ])


# ── Upload modal ──────────────────────────────────────────────────────────────
def _about_modal() -> dbc.Modal:
    """About modal — shows the full capability panel when user clicks ℹ About."""
    return dbc.Modal([
        dbc.ModalHeader(
            dbc.ModalTitle(html.Div([
                html.Span("✦ NL → SQL", style={
                    "background": f"linear-gradient(90deg,{ACCENT},{ACCENT2})",
                    "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent",
                    "fontWeight": "800", "fontSize": "1.1rem"}),
                html.Span("  v5", style={
                    "background": f"{ACCENT}20", "color": ACCENT,
                    "border": f"1px solid {ACCENT}40", "borderRadius": "20px",
                    "padding": "1px 8px", "fontSize": "0.65rem", "fontWeight": "700",
                    "verticalAlign": "middle", "marginLeft": "6px"}),
            ])),
            close_button=True,
            style={"background": BG_CARD, "borderBottom": f"1px solid {BORDER}",
                   "color": "#e5e7eb"}),
        dbc.ModalBody(
            html.Div([_welcome_capability_panel()],
                style={"overflowY": "auto", "maxHeight": "70vh"}),
            style={"background": BG_CARD}),
        dbc.ModalFooter(
            html.Small("NL→SQL Enterprise Platform · All queries logged in audit trail",
                style={"color": MUTED}),
            style={"background": BG_CARD, "borderTop": f"1px solid {BORDER}"}),
    ], id="about-modal", is_open=False, size="lg",
    style={"fontFamily": "Inter, sans-serif"}, contentClassName="border-0")
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("📂 Upload Data"), close_button=True,
            style={"background": BG_CARD, "borderBottom": f"1px solid {BORDER}",
                   "color": "#e5e7eb"}),
        dbc.ModalBody([
            dcc.Upload(id="csv-upload",
                children=html.Div([
                    html.Div("📂", style={"fontSize": "2.5rem", "marginBottom": "8px"}),
                    html.Div("Drag & drop CSV / TSV files here",
                        style={"color": DIM, "fontSize": "0.88rem"}),
                    html.Div(["or ", html.Span("browse files",
                        style={"color": ACCENT, "textDecoration": "underline",
                               "cursor": "pointer"})],
                        style={"color": MUTED, "fontSize": "0.8rem", "marginTop": "4px"}),
                ], style={"textAlign": "center"}),
                className="upload-zone",
                style={"border": f"2px dashed {BORDER}", "borderRadius": "12px",
                       "padding": "40px 20px", "cursor": "pointer",
                       "background": BG_SIDE, "transition": "all .2s"},
                multiple=True),
            html.Div(id="upload-status", className="mt-3",
                style={"fontSize": "0.8rem", "minHeight": "20px"}),
            html.Hr(style={"borderColor": BORDER, "margin": "14px 0"}),
            html.Div("🖼️ Upload Dashboard Screenshot → Image-to-SQL",
                style={"color": DIM, "fontSize": "0.78rem",
                       "marginBottom": "6px", "fontWeight": "600"}),
            dcc.Upload(id="image-upload",
                children=html.Div("📸 Drop a dashboard screenshot here",
                    style={"textAlign": "center", "padding": "14px",
                           "color": MUTED, "fontSize": "0.78rem"}),
                style={"border": f"1px dashed {BORDER}", "borderRadius": "8px",
                       "background": BG_DEEP, "cursor": "pointer"},
                accept="image/*", multiple=False),
            html.Div(id="image-upload-status",
                style={"fontSize": "0.76rem", "marginTop": "6px"}),
        ], style={"background": BG_CARD}),
        dbc.ModalFooter(
            html.Small("Files stored locally in data/",
                style={"color": MUTED}),
            style={"background": BG_CARD, "borderTop": f"1px solid {BORDER}"}),
    ], id="upload-modal", is_open=False, size="lg",
    style={"fontFamily": "Inter, sans-serif"},
    backdrop=True, scrollable=False, contentClassName="border-0")


# ── Email modal ───────────────────────────────────────────────────────────────
def _email_modal() -> dbc.Modal:
    inp = lambda id_, ph, val=None: dbc.Input(
        id=id_, placeholder=ph, value=val,
        style={"background": BG_DEEP, "color": "#f3f4f6",
               "border": f"1px solid {BORDER}", "borderRadius": "6px",
               "fontSize": "0.83rem", "marginBottom": "10px"})
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("📧 Email Report"), close_button=True,
            style={"background": BG_CARD, "borderBottom": f"1px solid {BORDER}",
                   "color": "#e5e7eb"}),
        dbc.ModalBody([
            dbc.Label("To", style={"color": DIM, "fontSize": "0.78rem"}),
            inp("email-to", "finance@example.com"),
            dbc.Label("Subject", style={"color": DIM, "fontSize": "0.78rem"}),
            inp("email-subject", "NL→SQL Report", "NL→SQL Report"),
            dbc.Label("Message (optional)", style={"color": DIM, "fontSize": "0.78rem"}),
            dbc.Textarea(id="email-body", rows=3,
                placeholder="Here is the report you requested...",
                style={"background": BG_DEEP, "color": "#f3f4f6",
                       "border": f"1px solid {BORDER}", "borderRadius": "6px",
                       "fontSize": "0.83rem"}),
            html.Div(id="email-status",
                style={"marginTop": "10px", "fontSize": "0.8rem"}),
        ], style={"background": BG_CARD}),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="email-cancel", color="secondary", size="sm",
                style={"borderRadius": "6px", "marginRight": "8px"}),
            dbc.Button("📧 Send", id="email-send", color="primary", size="sm",
                style={"borderRadius": "6px", "background": ACCENT2, "border": "none"}),
        ], style={"background": BG_CARD, "borderTop": f"1px solid {BORDER}"}),
    ], id="email-modal", is_open=False,
    style={"fontFamily": "Inter, sans-serif"}, contentClassName="border-0")


# ── Schedule modal ────────────────────────────────────────────────────────────
def _schedule_modal() -> dbc.Modal:
    sel = lambda id_, opts, val: dbc.Select(id=id_, options=opts, value=val,
        style={"background": BG_DEEP, "color": "#f3f4f6",
               "border": f"1px solid {BORDER}", "borderRadius": "6px",
               "fontSize": "0.83rem", "marginBottom": "10px"})
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("🗓️ Schedule Report"), close_button=True,
            style={"background": BG_CARD, "borderBottom": f"1px solid {BORDER}",
                   "color": "#e5e7eb"}),
        dbc.ModalBody([
            dbc.Label("Email recipient", style={"color": DIM, "fontSize": "0.78rem"}),
            dbc.Input(id="sched-email", placeholder="manager@company.com",
                style={"background": BG_DEEP, "color": "#f3f4f6",
                       "border": f"1px solid {BORDER}", "borderRadius": "6px",
                       "fontSize": "0.83rem", "marginBottom": "10px"}),
            dbc.Label("Frequency", style={"color": DIM, "fontSize": "0.78rem"}),
            sel("sched-freq",
                [{"label":"Daily","value":"daily"},
                 {"label":"Weekly","value":"weekly"},
                 {"label":"Monthly (1st)","value":"monthly"}], "weekly"),
            dbc.Label("Day (weekly)", style={"color": DIM, "fontSize": "0.78rem"}),
            sel("sched-day",
                [{"label": d, "value": d.lower()}
                 for d in ["Monday","Tuesday","Wednesday","Thursday","Friday"]], "monday"),
            dbc.Label("Time (HH:MM)", style={"color": DIM, "fontSize": "0.78rem"}),
            dbc.Input(id="sched-time", value="08:00",
                style={"background": BG_DEEP, "color": "#f3f4f6",
                       "border": f"1px solid {BORDER}", "borderRadius": "6px",
                       "fontSize": "0.83rem", "marginBottom": "10px"}),
            html.Div(id="sched-status",
                style={"marginTop": "6px", "fontSize": "0.8rem"}),
        ], style={"background": BG_CARD}),
        dbc.ModalFooter([
            dbc.Button("Cancel",      id="sched-cancel", color="secondary", size="sm",
                style={"borderRadius": "6px", "marginRight": "8px"}),
            dbc.Button("🗓️ Schedule", id="sched-save",   color="primary",   size="sm",
                style={"borderRadius": "6px", "background": ACCENT3, "border": "none"}),
        ], style={"background": BG_CARD, "borderTop": f"1px solid {BORDER}"}),
    ], id="schedule-modal", is_open=False,
    style={"fontFamily": "Inter, sans-serif"}, contentClassName="border-0")


# ── Header ────────────────────────────────────────────────────────────────────
def _header() -> html.Div:
    return html.Div(dbc.Row([
        dbc.Col(html.Div([
            html.Span("NL", style={
                "background": f"linear-gradient(90deg,{ACCENT},{ACCENT2})",
                "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent",
                "fontWeight": "800", "fontSize": "1.2rem", "letterSpacing": "-0.02em"}),
            html.Span(" → SQL", style={
                "color": "#e5e7eb", "fontWeight": "300", "fontSize": "1rem"}),
            html.Span("  v5", style={
                "background": f"{ACCENT}20", "color": ACCENT,
                "border": f"1px solid {ACCENT}40", "borderRadius": "20px",
                "padding": "1px 7px", "fontSize": "0.58rem", "fontWeight": "700",
                "letterSpacing": ".1em", "verticalAlign": "middle", "marginLeft": "7px"}),
        ]), width="auto", className="d-flex align-items-center"),
        dbc.Col(html.Div(id="header-llm-badge",
            style={"fontSize": "0.7rem", "color": MUTED}),
            className="d-flex align-items-center"),
        dbc.Col(html.Div([
            html.Span("⬤ ", style={"color": ACCENT3, "fontSize": "0.5rem"}),
            html.Span("Live", style={"color": DIM, "fontSize": "0.7rem"}),
            html.Span(" | ", style={"color": BORDER, "margin": "0 6px"}),
            html.Span(id="current-user-badge",
                style={"color": MUTED, "fontSize": "0.68rem"}),
            html.Span(" | ", style={"color": BORDER, "margin": "0 6px"}),
            html.Button("ℹ About", id="about-btn", n_clicks=0, style={
                "background": f"{ACCENT}12", "border": f"1px solid {ACCENT}30",
                "borderRadius": "20px", "color": ACCENT, "fontSize": "0.62rem",
                "fontWeight": "600", "padding": "2px 10px", "cursor": "pointer",
                "transition": "all .15s",
            }),
        ]), width="auto", className="d-flex align-items-center ms-auto"),
    ], align="center", className="g-0"), style={
        "background": f"linear-gradient(90deg,{BG_DEEP},{BG_CARD})",
        "borderBottom": f"1px solid {BORDER}",
        "padding": "9px 20px", "height": "50px", "flexShrink": "0",
    })


# ── Center chat area ──────────────────────────────────────────────────────────
def _chat_area() -> html.Div:
    return html.Div([
        # Scrollable history — starts with a clean greeting bubble
        html.Div(id="chat-history",
            children=[bot_bubble([
                html.Div([
                    html.Div("✦ NL → SQL  v5", style={
                        "background": f"linear-gradient(90deg,{ACCENT},{ACCENT2})",
                        "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent",
                        "fontWeight": "700", "fontSize": "1rem", "marginBottom": "8px"}),
                    dcc.Markdown(
                        "Upload a **CSV** using the **+** button, then ask me anything.\n\n"
                        "I can query data, build dashboards, generate charts, email reports, "
                        "and much more. Click **ℹ About** in the header to see all capabilities.",
                        style={"fontSize": "0.88rem", "color": DIM, "lineHeight": "1.6"}),
                    html.Div([
                        _pill("💬 NL→SQL",  ACCENT),
                        html.Span("·", style={"color": BORDER, "margin": "0 6px"}),
                        _pill("📊 Charts",  ACCENT3),
                        html.Span("·", style={"color": BORDER, "margin": "0 6px"}),
                        _pill("📧 Email",   ACCENT4),
                        html.Span("·", style={"color": BORDER, "margin": "0 6px"}),
                        _pill("🤖 Agents",  ACCENT2),
                    ], style={"marginTop": "12px", "display": "flex",
                              "alignItems": "center", "flexWrap": "wrap", "gap": "4px"}),
                ])
            ])],
            style={"flex": "1", "overflowY": "auto",
                   "padding": "20px 24px 8px",
                   "display": "flex", "flexDirection": "column"}),

        # Streaming status bar
        html.Div(id="stream-status-bar", children=[], style={"display": "none"}),

        typing_indicator(),

        # ── Input row ─────────────────────────────────────────────────────────
        html.Div([
            # + button (triggers popover)
            html.Div([
                html.Button("+", id="plus-btn", n_clicks=0,
                    title="Upload CSV, connect MCP servers",
                    className="plus-btn",
                    style={"background": f"{ACCENT}18",
                           "border": f"1px solid {ACCENT}35",
                           "borderRadius": "50%", "width": "36px", "height": "36px",
                           "color": ACCENT, "fontSize": "1.2rem", "fontWeight": "700",
                           "cursor": "pointer", "display": "flex",
                           "alignItems": "center", "justifyContent": "center",
                           "flexShrink": "0"}),
                # Popover container (positioned relative to + button)
                _plus_popover(),
            ], style={"position": "relative", "flexShrink": "0"}),

            # Speech button
            html.Button("🎤", id="speech-btn", n_clicks=0, title="Click to speak",
                style={"background": "transparent", "border": f"1px solid {BORDER}",
                       "borderRadius": "50%", "width": "36px", "height": "36px",
                       "color": DIM, "fontSize": "0.92rem", "cursor": "pointer",
                       "display": "flex", "alignItems": "center",
                       "justifyContent": "center", "flexShrink": "0",
                       "transition": "all .15s"}),

            # Text input
            dbc.Input(id="user-input", type="text", n_submit=0,
                placeholder="Ask anything about your data...",
                style={"background": "#111318", "color": "#f3f4f6",
                       "border": f"1.5px solid {BORDER}", "borderRadius": "28px",
                       "padding": "11px 20px", "fontSize": "0.87rem", "flex": "1",
                       "transition": "border-color .2s, box-shadow .2s"}),

            # Send button
            html.Button("➤", id="send-btn", n_clicks=0, className="send-btn",
                style={"background": f"linear-gradient(135deg,{ACCENT},{ACCENT2})",
                       "border": "none", "borderRadius": "50%",
                       "width": "42px", "height": "42px", "color": "#fff",
                       "fontSize": "1rem", "cursor": "pointer",
                       "display": "flex", "alignItems": "center",
                       "justifyContent": "center",
                       "boxShadow": f"0 4px 14px {ACCENT}50",
                       "flexShrink": "0"}),
        ], style={"display": "flex", "gap": "8px", "alignItems": "center",
                  "padding": "12px 20px 16px", "flexShrink": "0",
                  "background": f"linear-gradient(0deg,{BG_DEEP} 80%,transparent)"}),

        dcc.Store(id="speech-result", data=""),
        dcc.Store(id="last-query-store", data=""),
        dcc.Store(id="current-session-id", data=""),
    ], style={"flex": "1", "display": "flex", "flexDirection": "column",
              "height": "100vh", "background": "#0e1117", "minWidth": "0"})


# ── Root layout ───────────────────────────────────────────────────────────────
def build_layout() -> html.Div:
    return html.Div([
        dcc.Store(id="chat-store",   data=[]),
        dcc.Store(id="msg-counter",  data=0),
        dcc.Store(id="mcp-toggles",  data={}),   # {server_name: bool}
        _email_modal(),
        _schedule_modal(),
        _about_modal(),
        _header(),
        # Three-column body
        html.Div([
            _history_sidebar(),
            _chat_area(),
            _tools_sidebar(),
        ], style={"display": "flex", "height": "calc(100vh - 50px)",
                  "overflow": "hidden"}),
    ], style={"fontFamily": "'Inter', sans-serif", "height": "100vh",
              "overflow": "hidden", "background": BG_DEEP})
