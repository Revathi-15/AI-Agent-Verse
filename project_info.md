# AI-Powered Chatbot: Natural Language to SQL using Claude & MCP
## Objective
## Build an AI chatbot powered by Anthropic Claude using Model Context Protocol (MCP). The chatbot will:
- Convert user queries in natural language to SQL
- Execute those queries on a SQL database
- Display results (including plots) in a Dash-based frontend interface


## Deliverables
### FastMCP Backend
- Create a /chat endpoint to handle user queries.
- Register a tool named nl_to_sql_converter using FastMCP.
- Workflow:
		- Natural Language Input → JSON Parameters → SQL Query → Execute on DB → Return Results
		- Use Claude API to extract SQL parameters (e.g. table, filters, columns) from user input.

### Dash Frontend
- Build a minimal chat UI:
	- Input box to send messages to the /chat endpoint.
	- Display chatbot responses.
	- Visualize query results with graphs where applicable (e.g. using Plotly).

### Database Setup
- Connect to any SQL database of your choice (e.g. SQLite, PostgreSQL, MySQL).
- Ensure schema is well-documented for testing SQL generation.