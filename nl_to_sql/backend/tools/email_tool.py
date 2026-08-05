# email_tool.py — Email a PDF/chart report to any address via SMTP

import io
import os
import smtplib
import ssl
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.base      import MIMEBase
from email import encoders
from datetime import datetime

import pandas as pd
from backend.tools.base  import BaseTool
from backend.database    import state
from dotenv import load_dotenv

_ENV = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
load_dotenv(_ENV)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASSWORD", "")
FROM_ADDR = os.getenv("EMAIL_FROM", SMTP_USER)


def _build_pdf_bytes(df: pd.DataFrame, sql: str, summary: str) -> bytes:
    """Generate a styled PDF report using ReportLab."""
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib            import colors
    from reportlab.lib.styles     import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units      import inch
    from reportlab.platypus       import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, HRFlowable,
    )

    buf    = io.BytesIO()
    doc    = SimpleDocTemplate(buf, pagesize=landscape(letter),
                               leftMargin=0.5*inch, rightMargin=0.5*inch,
                               topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    accent = colors.HexColor("#00d4ff")
    dark   = colors.HexColor("#0a0c10")

    title_style = ParagraphStyle("title", parent=styles["Title"],
                                 textColor=accent, fontSize=18, spaceAfter=4)
    meta_style  = ParagraphStyle("meta",  parent=styles["Normal"],
                                 textColor=colors.grey, fontSize=9, spaceAfter=2)
    body_style  = ParagraphStyle("body",  parent=styles["Normal"],
                                 textColor=colors.HexColor("#333333"), fontSize=10)

    elems = []
    elems.append(Paragraph("NL → SQL  Report", title_style))
    elems.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
        f"Rows: {len(df):,}  |  Columns: {len(df.columns)}",
        meta_style,
    ))
    elems.append(HRFlowable(width="100%", thickness=1, color=accent, spaceAfter=8))

    if summary:
        elems.append(Paragraph("Summary", styles["Heading2"]))
        elems.append(Paragraph(summary, body_style))
        elems.append(Spacer(1, 8))

    if sql and not sql.startswith("--"):
        elems.append(Paragraph("SQL Query", styles["Heading2"]))
        code_style = ParagraphStyle("code", parent=styles["Code"],
                                    backColor=colors.HexColor("#f3f4f6"),
                                    fontSize=8, leading=12)
        elems.append(Paragraph(sql.replace("\n", "<br/>"), code_style))
        elems.append(Spacer(1, 10))

    elems.append(Paragraph("Results", styles["Heading2"]))

    # Table — cap at 100 rows for PDF
    display_df = df.head(100)
    data       = [list(display_df.columns)] + display_df.astype(str).values.tolist()
    col_count  = len(display_df.columns)
    col_width  = (10 * inch) / max(col_count, 1)

    tbl = Table(data, colWidths=[col_width] * col_count, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1,  0), dark),
        ("TEXTCOLOR",     (0, 0), (-1,  0), accent),
        ("FONTNAME",      (0, 0), (-1,  0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f0f4f8")]),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("PADDING",       (0, 0), (-1, -1), 4),
    ]))
    elems.append(tbl)

    if len(df) > 100:
        elems.append(Spacer(1, 6))
        elems.append(Paragraph(
            f"... and {len(df)-100:,} more rows (truncated for PDF).",
            meta_style,
        ))

    doc.build(elems)
    buf.seek(0)
    return buf.read()


class EmailReportTool(BaseTool):
    name        = "email_report"
    description = "Email a PDF report with charts, SQL, and data summary to one or more recipients"
    emoji       = "📧"

    def run(self, table: str, df_store: dict,
            to: str | list[str] = "",
            subject: str = "Your NL→SQL Report",
            body_text: str = "",
            df: pd.DataFrame | None = None,
            sql: str | None = None,
            summary: str | None = None,
            **kwargs) -> dict:
        """
        Args:
            to:         Recipient email(s) — string or list.
            subject:    Email subject line.
            body_text:  Optional plain-text body message.
            df:         DataFrame to attach; defaults to state["df"].
            sql:        SQL string for the report; defaults to state["sql"].
            summary:    Natural-language summary for the report.
        """
        if not to:
            return {"ok": False, "summary": "No recipient address provided.", "data": None}
        if not SMTP_USER or not SMTP_PASS:
            return {
                "ok": False,
                "summary": (
                    "Email not configured. Set SMTP_USER and SMTP_PASSWORD in .env."
                ),
                "data": None,
            }

        df  = df  if df  is not None else state.get("df")
        sql = sql if sql is not None else state.get("sql", "")

        if df is None or df.empty:
            return {"ok": False, "summary": "No data to email. Run a query first.", "data": None}

        recipients = [to] if isinstance(to, str) else to

        try:
            # ── Build PDF attachment ────────────────────────────────────────
            pdf_bytes = _build_pdf_bytes(df, sql or "", summary or "")

            # ── Build email ─────────────────────────────────────────────────
            msg = MIMEMultipart("mixed")
            msg["From"]    = FROM_ADDR
            msg["To"]      = ", ".join(recipients)
            msg["Subject"] = subject

            html_body = f"""
<html><body style="font-family:Arial,sans-serif;background:#f9fafb;padding:24px">
  <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;
              padding:32px;box-shadow:0 2px 8px rgba(0,0,0,.08)">
    <h2 style="color:#0a0c10;margin-top:0">
      NL → SQL Report
      <span style="color:#00d4ff;font-size:.75em"> v4</span>
    </h2>
    <p style="color:#6b7280;font-size:.9em">
      Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
    </p>
    <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0"/>
    <p style="color:#374151">
      {body_text or "Please find your requested data report attached as a PDF."}
    </p>
    <div style="background:#f3f4f6;border-radius:8px;padding:12px 16px;margin:16px 0">
      <strong style="color:#374151">Quick Stats</strong><br/>
      <span style="color:#6b7280;font-size:.85em">
        📊 {len(df):,} rows · {len(df.columns)} columns
        {f" · SQL: <code style='font-size:.8em'>{(sql or '')[:80]}...</code>" if sql else ""}
      </span>
    </div>
    {f'<p style="color:#374151"><strong>Summary:</strong> {summary}</p>' if summary else ""}
    <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0"/>
    <p style="color:#9ca3af;font-size:.75em">
      Sent by NL→SQL Agent Platform
    </p>
  </div>
</body></html>
"""
            msg.attach(MIMEText(html_body, "html"))

            # PDF attachment
            part = MIMEBase("application", "pdf")
            part.set_payload(pdf_bytes)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename=report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            )
            msg.attach(part)

            # CSV attachment
            csv_buf = io.StringIO()
            df.to_csv(csv_buf, index=False)
            csv_part = MIMEBase("text", "csv")
            csv_part.set_payload(csv_buf.getvalue().encode())
            encoders.encode_base64(csv_part)
            csv_part.add_header(
                "Content-Disposition",
                "attachment; filename=data.csv",
            )
            msg.attach(csv_part)

            # ── Send ────────────────────────────────────────────────────────
            context = ssl.create_default_context()
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(FROM_ADDR, recipients, msg.as_string())

            return {
                "ok"     : True,
                "summary": f"📧 Report emailed to **{', '.join(recipients)}** with PDF + CSV attachments.",
                "data"   : {
                    "recipients" : recipients,
                    "subject"    : subject,
                    "rows_sent"  : len(df),
                    "pdf_bytes"  : len(pdf_bytes),
                },
            }

        except ImportError as e:
            return {
                "ok": False,
                "summary": f"Missing library: {e}. Run: pip install reportlab",
                "data": None,
            }
        except smtplib.SMTPAuthenticationError:
            return {
                "ok": False,
                "summary": (
                    "SMTP authentication failed. "
                    "Check SMTP_USER / SMTP_PASSWORD in .env. "
                    "For Gmail, use an App Password."
                ),
                "data": None,
            }
        except Exception as e:
            return {"ok": False, "summary": f"Email failed: {e}", "data": None}
