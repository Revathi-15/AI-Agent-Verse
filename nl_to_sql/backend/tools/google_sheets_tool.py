# google_sheets_tool.py — Export query results to Google Sheets automatically

import os
import json
import pandas as pd
from backend.tools.base import BaseTool
from backend.database import run_query, quote, state

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CREDS_PATH  = os.path.join(BASE_DIR, "google_service_account.json")
OAUTH_PATH  = os.path.join(os.path.dirname(BASE_DIR), "gmail", "client-secret.json")


def _get_sheets_service():
    """Return a Google Sheets API service object using service account or OAuth."""
    from googleapiclient.discovery import build

    # Option 1: Service account (preferred for production)
    if os.path.exists(CREDS_PATH):
        from google.oauth2 import service_account
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = service_account.Credentials.from_service_account_file(
            CREDS_PATH, scopes=scopes
        )
        return build("sheets", "v4", credentials=creds)

    # Option 2: OAuth flow (reuse gmail credentials)
    token_path = os.path.join(
        os.path.dirname(BASE_DIR), "gmail", "token files", "token_sheets_v1.json"
    )
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        elif os.path.exists(OAUTH_PATH):
            flow = InstalledAppFlow.from_client_secrets_file(OAUTH_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
            os.makedirs(os.path.dirname(token_path), exist_ok=True)
            with open(token_path, "w") as f:
                f.write(creds.to_json())
        else:
            raise RuntimeError(
                "No Google credentials found. Place google_service_account.json in "
                "nl_to_sql/ or run Gmail OAuth first."
            )
    return build("sheets", "v4", credentials=creds)


def _get_drive_service():
    """Return Google Drive service (needed to set spreadsheet permissions)."""
    from googleapiclient.discovery import build

    if os.path.exists(CREDS_PATH):
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(
            CREDS_PATH,
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        return build("drive", "v3", credentials=creds)
    return None


class GoogleSheetsTool(BaseTool):
    name        = "export_google_sheets"
    description = "Export the last query result (or any DataFrame) to a new Google Spreadsheet and return its URL"
    emoji       = "📗"

    def run(self, table: str, df_store: dict,
            title: str = "NL→SQL Export",
            share_email: str | None = None,
            df: pd.DataFrame | None = None,
            **kwargs) -> dict:
        """
        Args:
            title:       Spreadsheet title.
            share_email: If provided, share the sheet with this email address.
            df:          DataFrame to export; defaults to state["df"].
        """
        try:
            df = df if df is not None else state.get("df")
            if df is None or df.empty:
                return {
                    "ok": False,
                    "summary": "No data to export. Run a query first.",
                    "data": None,
                }

            service = _get_sheets_service()
            sheets  = service.spreadsheets()

            # ── 1. Create spreadsheet ───────────────────────────────────────
            body = {
                "properties": {"title": title},
                "sheets": [{"properties": {"title": "Results", "index": 0}}],
            }
            spreadsheet = sheets.create(body=body).execute()
            ss_id = spreadsheet["spreadsheetId"]
            url   = f"https://docs.google.com/spreadsheets/d/{ss_id}"

            # ── 2. Write header + data ──────────────────────────────────────
            header   = [list(df.columns)]
            data_rows = df.astype(str).values.tolist()
            all_rows  = header + data_rows

            sheets.values().update(
                spreadsheetId=ss_id,
                range="Results!A1",
                valueInputOption="RAW",
                body={"values": all_rows},
            ).execute()

            # ── 3. Format header row (bold + colour) ────────────────────────
            requests_body = [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": 0,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {"red": 0.04, "green": 0.08, "blue": 0.16},
                                "textFormat": {
                                    "foregroundColor": {"red": 0.0, "green": 0.83, "blue": 1.0},
                                    "bold": True,
                                    "fontSize": 10,
                                },
                            }
                        },
                        "fields": "userEnteredFormat(backgroundColor,textFormat)",
                    }
                },
                {
                    "autoResizeDimensions": {
                        "dimensions": {
                            "sheetId": 0,
                            "dimension": "COLUMNS",
                            "startIndex": 0,
                            "endIndex": len(df.columns),
                        }
                    }
                },
            ]
            sheets.batchUpdate(
                spreadsheetId=ss_id, body={"requests": requests_body}
            ).execute()

            # ── 4. Optional share ────────────────────────────────────────────
            if share_email:
                drive = _get_drive_service()
                if drive:
                    drive.permissions().create(
                        fileId=ss_id,
                        body={"type": "user", "role": "writer", "emailAddress": share_email},
                        fields="id",
                    ).execute()

            return {
                "ok"     : True,
                "summary": f"✅ Exported **{len(df)}** rows to Google Sheets.",
                "data"   : {
                    "url"           : url,
                    "spreadsheet_id": ss_id,
                    "rows_exported" : len(df),
                    "cols_exported" : len(df.columns),
                    "shared_with"   : share_email,
                },
            }

        except ImportError as e:
            return {
                "ok": False,
                "summary": (
                    f"Missing library: {e}. "
                    "Run: pip install google-api-python-client google-auth-oauthlib"
                ),
                "data": None,
            }
        except Exception as e:
            return {"ok": False, "summary": f"Google Sheets export failed: {e}", "data": None}
