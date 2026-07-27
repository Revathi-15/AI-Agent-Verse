import dash
from dash import dcc, html
import pandas as pd
import plotly.express as px
from dash.dependencies import Input, Output
import os

# Paths to MCP output files
DATA_PATH = r"C:\Users\SANGAM REVATHI\AppData\Local\AnthropicClaude\app-0.12.55\data\last_result.csv"
PLOT_PATH = r"C:\Users\SANGAM REVATHI\AppData\Local\AnthropicClaude\app-0.12.55\data\last_plot.html"

app = dash.Dash(__name__)

# Layout
app.layout = html.Div([
    html.H1("Auto-updating Data Visualization"),
    dcc.Interval(
        id="interval-component",
        interval=5 * 1000,  # update every 5 seconds
        n_intervals=0
    ),
    dcc.Graph(id="live-graph")
])

# Callback to refresh plot
@app.callback(
    Output("live-graph", "figure"),
    Input("interval-component", "n_intervals")
)
def update_graph(n):
    if os.path.exists(DATA_PATH):
        try:
            df = pd.read_csv(DATA_PATH)
            if df.empty:
                return px.scatter(title="No Data Available")

            # Pick first 2 columns automatically
            cols = df.columns
            if len(cols) >= 2:
                fig = px.line(df, x=cols[0], y=cols[1], title="Latest Query Result")

                # Reverse Y-axis so higher values appear at the bottom
                fig.update_layout(yaxis=dict(autorange="reversed"))
            else:
                fig = px.scatter(title="Not enough columns to plot")

            # Save updated plot to HTML
            fig.write_html(PLOT_PATH)

            return fig
        except Exception as e:
            return px.scatter(title=f"Error reading CSV: {e}")
    else:
        return px.scatter(title="Waiting for Data...")

if __name__ == "__main__":
    app.run(debug=True)
