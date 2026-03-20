"""Email service.

Ported from v0.7.5 email_server.py (port 8093).
Cloud mode: SMTP sending via aiosmtplib, IMAP reading via aioimaplib.
Falls back to demo mode with sample emails if no credentials configured.
"""

from __future__ import annotations

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from ..config import settings

# Demo emails for when no IMAP credentials are configured
DEMO_EMAILS = [
    {
        "id": "demo_1",
        "from": "alice@example.com",
        "subject": "Project Status Update",
        "date": "2026-03-19T09:00:00",
        "body": "Hi, just wanted to give you a quick update on the AI Workflow project. We've completed Phase 2 migration and are now testing. Everything looks good so far.",
        "category": "primary",
        "read": False,
    },
    {
        "id": "demo_2",
        "from": "noreply@github.com",
        "subject": "[AI-Workflow-Cloud] New pull request #12",
        "date": "2026-03-18T16:30:00",
        "body": "wangqioo opened a new pull request: feat: add workflow engine module. Review requested.",
        "category": "updates",
        "read": True,
    },
    {
        "id": "demo_3",
        "from": "bob@company.com",
        "subject": "Meeting Notes - Sprint Review",
        "date": "2026-03-17T14:00:00",
        "body": "Attached are the meeting notes from today's sprint review. Key decisions: 1) Move to cloud-first architecture 2) Deploy on Docker Compose 3) React frontend next sprint.",
        "category": "primary",
        "read": True,
    },
]


async def get_inbox(limit: int = 20) -> list[dict]:
    """Get inbox emails. Returns demo emails if IMAP not configured."""
    # TODO: Real IMAP integration with aioimaplib when credentials available
    return DEMO_EMAILS[:limit]


async def get_email(email_id: str) -> dict | None:
    for e in DEMO_EMAILS:
        if e["id"] == email_id:
            return e
    return None


async def send_email(to: str, subject: str, body: str, html: bool = False) -> dict:
    """Send email via SMTP."""
    smtp_host = getattr(settings, "smtp_host", "")
    smtp_port = getattr(settings, "smtp_port", 587)
    smtp_user = getattr(settings, "smtp_user", "")
    smtp_pass = getattr(settings, "smtp_pass", "")

    if not smtp_host or not smtp_user:
        return {"status": "demo_mode", "message": f"Email would be sent to {to}: {subject}"}

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html" if html else "plain", "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return {"status": "sent", "to": to, "subject": subject}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def summarize_email(email_id: str) -> dict:
    """AI summarize an email."""
    email = await get_email(email_id)
    if not email:
        return {"error": "Email not found"}

    from ..llm.provider import get_llm_provider
    llm = get_llm_provider()
    messages = [
        {"role": "system", "content": "Summarize this email in 1-2 sentences. Include: key topic, action items, urgency level (low/medium/high)."},
        {"role": "user", "content": f"From: {email['from']}\nSubject: {email['subject']}\n\n{email['body']}"},
    ]
    result = await llm.chat(messages, max_tokens=200, temperature=0.3)
    return {"email_id": email_id, "summary": result.get("content", "")}
