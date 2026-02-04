from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from db import SessionLocal
from models import Client, GmailAccount
import json
import time

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
MAX_REFRESH_RETRIES = 3
RETRY_DELAY = 2  # seconds


def run_oauth_flow(client_name: str, client_email: str):
    """
    run oauth flow for a new client and store GmailAccount in db.
    """
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=8080)
    token_dict = json.loads(creds.to_json())

    session = SessionLocal()

    # fetch or create Client
    client = session.query(Client).filter(Client.name == client_name).first()
    if not client:
        client = Client(name=client_name, notification_email=client_email)
        session.add(client)
        session.commit()

    # create GmailAccount
    gmail_account = GmailAccount(
        client_id=client.id,
        gmail_address=creds.id_token.get("email"),  
        gmail_token=token_dict,
        is_active=True
    )
    session.add(gmail_account)
    session.commit()
    session.close()

    return token_dict


def get_credentials(gmail_account_id: int) -> Credentials:
    """
    load Gmail credentials from db, refresh if expired, handle revocation.
    """
    session = SessionLocal()
    gmail_account = session.query(GmailAccount).filter(GmailAccount.id == gmail_account_id).first()
    session.close()

    if not gmail_account:
        raise Exception("Gmail account not found")

    creds = Credentials.from_authorized_user_info(gmail_account.gmail_token, SCOPES)

    # refresh token if expired
    if creds.expired and creds.refresh_token:
        for attempt in range(MAX_REFRESH_RETRIES):
            try:
                creds.refresh(Request())
                # update token in DB
                session = SessionLocal()
                gmail_account = session.query(GmailAccount).filter(GmailAccount.id == gmail_account_id).first()
                gmail_account.gmail_token = json.loads(creds.to_json())
                session.commit()
                session.close()
                break
            except Exception as e:
                print(f"Refresh attempt {attempt+1} failed: {e}")
                time.sleep(RETRY_DELAY)
        else:
            # if failed refresh, we deactivate account
            session = SessionLocal()
            gmail_account = session.query(GmailAccount).filter(GmailAccount.id == gmail_account_id).first()
            gmail_account.is_active = False
            session.commit()
            session.close()
            raise Exception("Failed to refresh token, Gmail account marked inactive")

    if not creds.valid:
        raise Exception("Gmail credentials invalid or revoked")

    return creds
