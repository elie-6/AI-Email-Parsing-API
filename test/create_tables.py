# backend/create_tables.py
from backend.db import engine, Base
from backend.models import Client, GmailAccount, Email, EmailAIResult, Notification

# This reads all imported models and creates corresponding tables in the DB
Base.metadata.create_all(bind=engine)
print("All tables created!")
