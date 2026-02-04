
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from db import SessionLocal
from models import Email, Notification
from config import EMAIL_FROM, EMAIL_APP_PASSWORD, SMTP_PORT


SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = SMTP_PORT

SERVICE_EMAIL = EMAIL_FROM
SERVICE_EMAIL_PASSWORD = EMAIL_APP_PASSWORD


def send_email(to_email: str, subject: str, body: str):
    msg = MIMEMultipart()
    msg["From"] = SERVICE_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SERVICE_EMAIL, SERVICE_EMAIL_PASSWORD)
        server.send_message(msg)


def notify_clients_for_done_emails():
    session = SessionLocal()


    emails = (
        session.query(Email)
        .filter(Email.ai_parse_status == "done")
        .outerjoin(Notification, Notification.email_id == Email.id)
        .filter(Notification.id.is_(None))
        .all()
    )

    print(f"Notifier: {len(emails)} emails to notify")

    for email in emails:
        client = email.gmail_account.client
        ai = email.ai_result

        if not client.notification_email:
            print(f"Client {client.id} has no notification email")
            continue

        subject = f"New email processed: {email.subject}"

        body = f"""
Hi {client.name},

A new email has been processed by our AI system.

From: {email.from_email}
Subject: {email.subject}
Received at: {email.received_at}

Summary:
{ai.summary}

Category: {ai.category}
Intent: {ai.intent}
Urgency: {ai.urgency}

— Your AI assistant
        """.strip()

        notification = Notification(
            client_id=client.id,
            email_id=email.id,
            channel="email",
            sent_to=client.notification_email,
            status="pending",
        )

        session.add(notification)
        session.flush() 

        try:
            send_email(client.notification_email, subject, body)

            notification.status = "sent"
            print(f"Notification sent for email {email.id}")

        except Exception as e:
            notification.status = "failed"
            notification.error_message = str(e)
            print(f"Notification failed for email {email.id}: {e}")

    session.commit()
    session.close()
