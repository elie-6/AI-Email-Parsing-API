# backend/add_test_client_new.py
from backend.db import SessionLocal
from backend.models import Client, GmailAccount
import json

session = SessionLocal()

# 1️⃣ create client
client = Client(
    name="Elie Test Client",
    notification_email="elieabisafi6@gmail.com",  
    is_active=True
)
session.add(client)
session.commit()  

# 2️⃣ create GmailAccount with token from file
with open("token.json") as f:
    token_data = json.load(f)

gmail_account = GmailAccount(
    client_id=client.id,
    gmail_address="elieabisafi6@gmail.com",  # must match real Gmail account
    gmail_token=token_data,
    is_active=True
)

session.add(gmail_account)
session.commit()
session.close()

print("Test client and Gmail account added successfully.")
