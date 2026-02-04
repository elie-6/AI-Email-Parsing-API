
from backend.oauth_handler import get_credentials
from backend.gmail_client import fetch_and_store_emails
from backend.db import SessionLocal
from backend.models import Client, GmailAccount, Email

def test_ingestion_existing_client(client_name="Elie Test Client", max_results=5):
    session = SessionLocal()

    # 1️⃣ Fetch the client and Gmail account from DB
    client = session.query(Client).filter(Client.name == client_name).first()
    if not client:
        print(f"No client found with name '{client_name}'")
        return

    gmail_account = session.query(GmailAccount).filter(GmailAccount.client_id == client.id).first()
    if not gmail_account:
        print(f"No Gmail account found for client '{client_name}'")
        return

    print(f"Testing ingestion for client: {client.name}, Gmail: {gmail_account.gmail_address}")

    # 2️⃣ Refresh credentials to verify
    creds = get_credentials(gmail_account.id)
    print(f"Credentials valid? {creds.valid}, expired? {creds.expired}")

    # 3️⃣ Fetch and store emails
    print(f"Fetching up to {max_results} unread emails...")
    fetch_and_store_emails(gmail_account.id, max_results=max_results)

    # 4️⃣ Verify emails in DB
    emails = session.query(Email).filter(Email.gmail_account_id == gmail_account.id).all()
    print(f"{len(emails)} emails stored in DB:")
    for e in emails:
        print(f"- {e.subject} | From: {e.from_email} | Status: {e.ai_parse_status}")

    # 5️⃣ Verify last_fetched_at updated
    session.refresh(gmail_account)
    print(f"Last fetched at: {gmail_account.last_fetched_at}")

    session.close()


if __name__ == "__main__":
    test_ingestion_existing_client()
