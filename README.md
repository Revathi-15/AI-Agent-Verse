# AI Agent Verse

A collection of AI-powered agent projects built with Python, FastAPI, Dash, and Claude/OpenAI/Gemini.

---

## Projects

### NL → SQL Enterprise Platform (`nl_to_sql/`)

Ask questions in plain English — get SQL, charts, and insights from your data.

**Features**
- Natural language → SQL → interactive charts (bar, line, pie, scatter, histogram)
- 6-agent pipeline: Planner → Schema → SQL → Validation → Visualization → Explanation
- Streaming responses with step-by-step status
- Smart auto-chart selection based on data shape
- Google Sheets export
- Email reports (PDF + CSV via SMTP)
- Scheduled recurring reports (daily / weekly / monthly)
- Voice input (browser Web Speech API + OpenAI Whisper)
- Image-to-SQL: upload a dashboard screenshot → AI infers the SQL
- Vector semantic search over query history
- SQL Tutor mode: explains SQL, suggests alternatives, gives optimization tips
- Natural language dashboard builder
- Live DB connections: PostgreSQL, MySQL, SQLite
- User permissions: Admin / Manager / Analyst / Viewer
- Audit log: every query tracked with user, time, SQL, rows, elapsed
- Feedback loop: 👍 / 👎 stored to improve prompts
- Conversation history with 2-day auto-expiry (PostgreSQL or SQLite)
- 15 active MCP tools · 134 in catalog

**Stack**
- Backend: FastAPI + SQLite/PostgreSQL
- Frontend: Plotly Dash + Bootstrap
- LLMs: OpenAI GPT-4o / Claude 3.5 / Gemini 2.0 (switchable)

**Quick Start**

```bash
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Mac/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp nl_to_sql/.env.example nl_to_sql/.env
# Edit .env and add your API keys

# 4. Run
cd nl_to_sql
python run.py
```

Opens automatically at `http://127.0.0.1:8050`

**Environment Variables**

See `nl_to_sql/.env.example` for all required and optional keys.

---

### Gmail MCP Agent (`gmail/`)

MCP server for Gmail — read, send, search emails via Claude.

---

## Repository Structure

```
AI Agent Verse/
├── nl_to_sql/
│   ├── backend/
│   │   ├── api.py            # FastAPI routes
│   │   ├── database.py       # SQLite/PostgreSQL helpers
│   │   ├── llm.py            # LLM abstraction layer
│   │   ├── orchestrator.py   # Multi-agent orchestration
│   │   └── tools/            # 15 MCP tool implementations
│   ├── frontend/
│   │   ├── app.py            # Dash app instance
│   │   ├── layout.py         # UI layout + chart builder
│   │   └── callbacks.py      # All Dash callbacks
│   ├── data/                 # CSV data files (gitignored)
│   ├── run.py                # Single entry point
│   └── .env.example          # Environment template
├── gmail/
│   ├── mcp_gmail.py
│   └── tools/
└── requirements.txt
```
