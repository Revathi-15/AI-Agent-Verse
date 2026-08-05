# AI Agent Verse

A collection of production-grade AI agent projects — NL→SQL platform and Gmail MCP agent.

---

## 🚀 NL → SQL Enterprise Platform

Ask questions in plain English. Get SQL, interactive charts, PDF reports, and insights — automatically.

### What it does

| Capability | Description |
|---|---|
| 💬 Natural Language → SQL | Type a question, get a query + results + chart |
| 📊 Smart Charts | Auto-selects bar / line / pie / scatter / histogram |
| 🤖 Multi-Agent Pipeline | Planner → Schema → SQL → Validation → Viz → Explanation |
| 📧 Email Reports | Sends PDF + CSV via SMTP |
| 🗓️ Scheduled Reports | Daily / weekly / monthly recurring emails |
| 📗 Google Sheets Export | One-click export to a new spreadsheet |
| 🖼️ Image → SQL | Upload a dashboard screenshot → AI infers the SQL |
| 🔮 Semantic History | Finds similar past queries using vector search |
| 🎓 SQL Tutor | Explains SQL, shows alternatives, optimization tips |
| 🎤 Voice Input | Browser speech recognition + OpenAI Whisper |
| 📋 Audit Log | Every query tracked — user, time, SQL, rows, elapsed |
| 👍 Feedback Loop | Thumbs up/down stored to improve prompts |
| 🛡️ User Permissions | Admin / Manager / Analyst / Viewer roles |

### Tech Stack

| Layer | Tech |
|---|---|
| Backend | Python · FastAPI · SQLite / PostgreSQL |
| Frontend | Plotly Dash · Dash Bootstrap Components |
| LLMs | OpenAI GPT-4o · Claude 3.5 Sonnet · Gemini 2.0 (switchable) |
| Charts | Plotly Express |
| PDF | ReportLab |
| Voice | OpenAI Whisper API |
| Scheduling | `schedule` library (background thread) |
| Vector Search | TF-IDF cosine similarity (local, no external API) |

---

## ⚡ Quick Start

```bash
# 1. Clone
git clone https://github.com/Revathi-15/AI-Agent-Verse.git
cd AI-Agent-Verse

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp nl_to_sql/.env.example nl_to_sql/.env
# Open .env and add your API key(s)

# 5. Run
cd nl_to_sql
python run.py
```

Opens at **http://127.0.0.1:8050** · API at **http://127.0.0.1:8000**

---

## 🔑 Minimum .env Required

```env
LLM_PROVIDER=openai          # openai | claude | gemini
OPENAI_API_KEY=sk-...
SQLITE_DB=sqlite.db
```

Everything else (email, Google Sheets, Slack, PostgreSQL) is optional — see `.env.example`.

---

## 📁 Structure

```
AI-Agent-Verse/
├── nl_to_sql/
│   ├── run.py                  # Single entry point — starts everything
│   ├── backend/
│   │   ├── api.py              # FastAPI — all routes
│   │   ├── database.py         # SQLite + PostgreSQL helpers
│   │   ├── llm.py              # OpenAI / Claude / Gemini abstraction
│   │   ├── orchestrator.py     # Multi-agent pipeline
│   │   └── tools/              # 15 MCP tool implementations
│   ├── frontend/
│   │   ├── app.py              # Dash app instance
│   │   ├── layout.py           # UI — 3-column layout + charts
│   │   └── callbacks.py        # All interactivity
│   └── .env.example
├── gmail/                      # Gmail MCP agent
├── requirements.txt
└── README.md
```

---

## 📦 Dependencies

```bash
pip install fastapi uvicorn dash dash-bootstrap-components plotly pandas \
            openai anthropic google-generativeai reportlab openpyxl \
            requests python-dotenv schedule sqlalchemy
```

---

## 📸 Gmail MCP Agent (`gmail/`)

MCP server that gives Claude access to your Gmail — read, send, search emails.

**Setup:** Add `gmail/client-secret.json` from Google Cloud Console, then run `gmail/mcp_gmail.py`.

---

> Built by [Revathi](https://github.com/Revathi-15)
