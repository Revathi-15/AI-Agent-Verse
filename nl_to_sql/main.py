import os
import sqlite3
import webbrowser
import pandas as pd
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from anthropic import Anthropic
from sql import csv_to_sqlite
import plotly.express as px

# Load environment variables
load_dotenv()
DB_PATH = os.getenv("SQLITE_DB") or "sqlite.db"
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")

# Initialize MCP and Claude
mcp = FastMCP("NL_TO_SQL_BOT")
claude = Anthropic(api_key=CLAUDE_API_KEY) if CLAUDE_API_KEY else None

os.makedirs("data", exist_ok=True)

# Global variables
uploaded_table = None
last_sql = None
last_df = None

def quote(name):
    return f'"{name}"'

def get_table_schema(table_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(f'PRAGMA table_info({quote(table_name)})')
    schema = "\n".join([f"{row[1]} ({row[2]})" for row in cursor.fetchall()])
    conn.close()
    return schema

@mcp.tool()
def upload_csv(file_path: str) -> str:
    global uploaded_table

    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        return f"File does not exist or cannot be accessed: {abs_path}"

    filename = os.path.basename(abs_path)
    target_path = os.path.join("data", filename)

    try:
        with open(abs_path, "r", encoding="utf-8") as src, open(target_path, "w", encoding="utf-8") as dest:
            dest.write(src.read())
    except Exception as e:
        return f"Failed to read/write file: {e}"

    uploaded_table = csv_to_sqlite(target_path, DB_PATH)
    if not uploaded_table:
        return "CSV uploaded, but failed to convert to SQLite table."

    # Rename if hyphens exist
    sanitized = uploaded_table.replace("-", "_")
    if sanitized != uploaded_table:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(f'ALTER TABLE {quote(uploaded_table)} RENAME TO {quote(sanitized)}')
        conn.commit()
        conn.close()
        uploaded_table = sanitized

    return f"CSV file loaded and converted to table: **{uploaded_table}**"

@mcp.tool()
def nl_to_sql(query: str) -> str:
    global uploaded_table, last_sql, last_df

    if not uploaded_table:
        return "No CSV file uploaded yet. Please upload a file using `upload_csv()`."

    if not claude:
        return "Claude API key missing or invalid. Please set CLAUDE_API_KEY in your .env file."

    schema = get_table_schema(uploaded_table)

    prompt = f"""
You are a professional SQL generator. A user uploaded a CSV file, which is now a SQLite table named "{uploaded_table}".

The schema of the table is:
{schema}

Your task is to convert natural language questions into pure SQL queries. DO NOT provide JavaScript, Python, explanations, markdown, or anything else — only valid SQL.

Wrap table and column names in double quotes.

Here is the user’s question:
\"\"\"{query}\"\"\"

Respond with only the SQL query.
""".strip()

    try:
        response = claude.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=300,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        sql = response.content[0].text.strip()
        if sql.startswith("```sql"):
            sql = sql.replace("```sql", "").replace("```", "").strip()

        last_sql = sql
        conn = sqlite3.connect(DB_PATH)
        last_df = pd.read_sql_query(sql, conn)
        conn.close()

        export_for_dash()  # Auto-export for Dash dashboard
        webbrowser.open("http://127.0.0.1:8050") 
        
        return f"**Generated SQL Query:**\n```sql\n{sql}\n```\n\n**Query Result:**\n{last_df.to_markdown(index=False)}"

    except Exception as e:
        return f"**Generated SQL Query:**\n```sql\n{last_sql if last_sql else '[NO SQL GENERATED]'}\n```\n\n**Error executing SQL query:**\n```\n{e}\n```"

@mcp.tool()
def run_sql_manual(sql: str) -> str:
    global last_df, last_sql

    try:
        conn = sqlite3.connect(DB_PATH)
        last_df = pd.read_sql_query(sql, conn)
        conn.close()
        last_sql = sql
        export_for_dash()
        return last_df.to_string(index=False)
    except Exception as e:
        return f"Error running SQL manually:\n{e}"

@mcp.tool()
def show_answer() -> str:
    global last_df

    if last_df is None or last_df.empty:
        return "No result to display."
    return last_df.to_string(index=False)

@mcp.tool()
def show_table_head(n: int = 5) -> str:
    global uploaded_table
    if not uploaded_table:
        return "No table uploaded."

    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(f'SELECT * FROM {quote(uploaded_table)} LIMIT {n}', conn)
        conn.close()
        return df.to_string(index=False)
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def export_for_dash() -> str:
    global last_df, last_sql
    os.makedirs("data", exist_ok=True)
    csv_path = os.path.join("data", "last_result.csv")
    txt_path = os.path.join("data", "last_response.txt")

    try:
        if last_df is None:
            pd.DataFrame().to_csv(csv_path, index=False)
            return "No data available, empty CSV saved."

        last_df.to_csv(csv_path, index=False)

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"SQL Query:\n{last_sql}\n\n")
            f.write("Result Preview:\n")
            f.write(last_df.head().to_string(index=False))

        return "Result exported for Dash successfully."
    except Exception as e:
        return f"Error exporting: {e}"


@mcp.tool()
def show_plot(x_column: str, y_column: str, kind: str = "bar") -> str:
    global last_df

    if last_df is None or last_df.empty:
        return "No data available to plot. Please run a query first."

    if x_column not in last_df.columns or y_column not in last_df.columns:
        return f"Invalid column names. Available columns: {', '.join(last_df.columns)}"

    try:
        fig = None
        if kind == "bar":
            fig = px.bar(last_df, x=x_column, y=y_column, hover_data=last_df.columns)
        elif kind == "line":
            fig = px.line(last_df, x=x_column, y=y_column, hover_data=last_df.columns)
        elif kind == "scatter":
            fig = px.scatter(last_df, x=x_column, y=y_column, hover_data=last_df.columns)
        else:
            return "Unsupported plot type. Use 'bar', 'line', or 'scatter'."

        os.makedirs("data", exist_ok=True)
        graph_path = os.path.join("data", "last_plot.html")
        fig.write_html(graph_path, auto_open=True)

        return f"Graph generated successfully. Open `data/last_plot.html` to view it."

    except Exception as e:
        return f"Error generating graph: {e}"

if __name__ == "__main__":
    mcp.run()
