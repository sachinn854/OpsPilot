"""
Email delivery utility — sends digest and notification emails via SMTP.

Supports any SMTP server (Gmail, Outlook, SendGrid, etc.).
Configure via SMTP_* settings in .env.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.config import settings

logger = logging.getLogger("copilot.email")


def _smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def send_email(to: str, subject: str, body_text: str, body_html: str | None = None) -> bool:
    """Send an email. Returns True on success, False on failure."""
    if not _smtp_configured():
        logger.warning("SMTP not configured — email not sent to %s", to)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
    msg["To"]      = to

    msg.attach(MIMEText(body_text, "plain"))
    if body_html:
        msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, to, msg.as_string())
        logger.info("Email sent to %s — %s", to, subject)
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to, exc)
        return False


def _slack_digest_html(subject: str, body: str) -> str:
    """Convert the plain-text Slack digest into a simple HTML email."""
    # Convert Slack markdown (*bold*, _italic_) to basic HTML
    import re
    html_body = body
    html_body = re.sub(r"\*(.+?)\*", r"<strong>\1</strong>", html_body)
    html_body = re.sub(r"_(.+?)_",   r"<em>\1</em>",         html_body)
    html_body = html_body.replace("---", "<hr>")
    html_body = html_body.replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body        {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                   background: #f5f5f5; margin: 0; padding: 20px; }}
    .card       {{ background: #fff; border-radius: 10px; max-width: 640px;
                   margin: 0 auto; padding: 32px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }}
    .header     {{ border-bottom: 2px solid #6366f1; padding-bottom: 16px; margin-bottom: 24px; }}
    .title      {{ font-size: 20px; font-weight: 700; color: #1e1e2e; margin: 0; }}
    .subtitle   {{ font-size: 13px; color: #888; margin-top: 4px; }}
    .body       {{ font-size: 14px; line-height: 1.8; color: #333; }}
    hr          {{ border: none; border-top: 1px solid #eee; margin: 20px 0; }}
    .footer     {{ margin-top: 32px; font-size: 12px; color: #aaa; text-align: center; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="title">📋 {subject}</div>
      <div class="subtitle">AI Operations Copilot — Slack Digest</div>
    </div>
    <div class="body">{html_body}</div>
    <div class="footer">
      You're receiving this because email digest is enabled in your OpsPilot settings.<br>
      <a href="#" style="color:#6366f1">Manage preferences</a>
    </div>
  </div>
</body>
</html>"""


def send_slack_digest(to: str, digest_text: str, period: str) -> bool:
    """Send a formatted Slack digest email."""
    subject = f"OpsPilot {period} Digest"
    html    = _slack_digest_html(subject, digest_text)
    return send_email(to, subject, digest_text, html)
