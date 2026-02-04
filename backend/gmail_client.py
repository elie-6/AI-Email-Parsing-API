from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from oauth_handler import get_credentials
from models import GmailAccount, Email
from db import SessionLocal
from datetime import datetime

def get_gmail_service(creds):
    """
    build gmail api service.
    """
    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except HttpError as error:
        print(f"Failed to build Gmail service: {error}")
        raise


def fetch_and_store_emails(gmail_account_id: int, max_results=10):
    """
    fetch unread emails for a gmail account and store them in Email table.
    """
    session = SessionLocal()
    gmail_account = session.query(GmailAccount).filter(
        GmailAccount.id == gmail_account_id,
        GmailAccount.is_active == True
    ).first()

    if not gmail_account:
        session.close()
        print(f"Gmail account {gmail_account_id} inactive or not found.")
        return

    creds = get_credentials(gmail_account_id)
    service = get_gmail_service(creds)

    try:
        # fetch unread emails
        results = service.users().messages().list(
            userId='me',
            labelIds=['INBOX', 'UNREAD'],
            maxResults=max_results
        ).execute()

        messages = results.get('messages', [])
        for msg in messages:
            msg_detail = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='full'
            ).execute()

            headers = msg_detail['payload'].get('headers', [])
            snippet = msg_detail.get('snippet', '')

            sender = next((h['value'] for h in headers if h['name'] == 'From'), None)
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), None)

            # skip if already exists
            if session.query(Email).filter(Email.gmail_id == msg['id']).first():
                continue

            email = Email(
                gmail_account_id=gmail_account.id,
                gmail_id=msg['id'],
                thread_id=msg_detail.get('threadId'),
                from_email=sender,
                subject=subject,
                snippet=snippet,
                received_at=datetime.utcnow(),
                ai_parse_status="pending"
            )
            session.add(email)


        gmail_account.last_fetched_at = datetime.utcnow()
        session.commit()
        session.close()

    except HttpError as error:
        session.close()
        print(f"Gmail API error: {error}")
        raise
