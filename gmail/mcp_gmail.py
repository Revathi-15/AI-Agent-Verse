import os
from dotenv import load_dotenv
from anthropic import Anthropic
from mcp.server.fastmcp import FastMCP
from tools.gmail_tools import GmailTool
from tools.googles_apis import create_service

# Load .env variables
load_dotenv()
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
claude = Anthropic(api_key=CLAUDE_API_KEY) if CLAUDE_API_KEY else None

# Create working directory
work_dir = os.path.dirname(__file__)
secret_path = os.path.join(work_dir, "client-secret.json")
gmail_tool = GmailTool(secret_path)

# Initialize MCP
mcp = FastMCP("GMAIL")

# Claude-based Gmail text analyzer
@mcp.tool()
def analyze_gmail_query(query: str) -> str:
    """
    Use Claude to analyze a Gmail-related natural language command.
    """
    if not claude:
        return "Claude API key missing. Please set CLAUDE_API_KEY in your .env file."

    try:
        response = claude.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=300,
            temperature=0,
            messages=[{"role": "user", "content": f"Analyze this Gmail request: {query}"}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Error querying Claude: {e}"

# Gmail tools via decorators
@mcp.tool()
def send_email(to: str, subject: str, body: str) -> str:
    return gmail_tool.send_email(to, subject, body)

@mcp.tool()
def get_email_message_details(message_id: str) -> str:
    return gmail_tool.get_email_message_details(message_id)

@mcp.tool()
def get_email_message_body(message_id: str) -> str:
    return gmail_tool.get_email_message_body(message_id)

@mcp.tool()
def search_emails(query: str = None) -> str:
    return gmail_tool.search_emails(query)

@mcp.tool()
def delete_email_message(message_id: str) -> str:
    return gmail_tool.delete_email_message(message_id)

if __name__ == "__main__":
    print("Running Gmail MCP Tool Server...")
    print(f"Registered tools: {list(mcp.tools.keys())}")
    mcp.run()