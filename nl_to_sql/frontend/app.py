"""
frontend/app.py
===============
Dash application instance.
Import `app` from here in layout.py, callbacks.py, and run.py.
Keeping initialisation separate avoids circular imports.
"""

import dash
import dash_bootstrap_components as dbc
from frontend.layout import CUSTOM_CSS

app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.DARKLY,
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap",
    ],
    title="NL → SQL Chatbot",
    update_title=None,
    suppress_callback_exceptions=True,
)

# Inject bounce keyframe + hover CSS for buttons, input, bubbles
app.index_string = app.index_string.replace(
    "</head>",
    f"<style>{CUSTOM_CSS}</style></head>",
)

server = app.server
