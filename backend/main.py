from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from db import get_db
from models import Client, GmailAccount, Email
from parser import parse_batch_real
from gmail_client import fetch_and_store_emails
from utils import (
    verify_password,
    hash_password,
    create_access_token,
    get_current_user,
)


app = FastAPI(title="LeadApp Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models 
class EmailParsedOut(BaseModel):
    id: int
    subject: Optional[str]
    snippet: Optional[str]
    from_email: Optional[str]
    received_at: Optional[datetime]
    category: Optional[str]
    intent: Optional[str]
    urgency: Optional[str]
    summary: Optional[str]
    confidence: Optional[int]


class SignupIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# routes 
@app.post("/signup", response_model=TokenOut)
def signup(data: SignupIn, db: Session = Depends(get_db)):

    if db.query(Client).filter(Client.name == data.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")

    client = Client(
        name=data.username,
        notification_email="",
        is_active=True,
        password_hash=hash_password(data.password),
    )

    db.add(client)
    db.commit()
    db.refresh(client)

    token = create_access_token({"sub": client.id})
    return {"access_token": token}


@app.post("/login", response_model=TokenOut)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    client = db.query(Client).filter(Client.name == form_data.username).first()
    if not client or not verify_password(
        form_data.password, client.password_hash
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": str(client.id)})
    return {"access_token": token}



@app.get("/dashboard/emails", response_model=List[EmailParsedOut])
def dashboard_emails(
    limit: int = 50,
    offset: int = 0,
    current_user: Client = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    emails = (
        db.query(Email)
        .options(selectinload(Email.ai_result))
        .join(GmailAccount, Email.gmail_account_id == GmailAccount.id)
        .filter(GmailAccount.client_id == current_user.id)
        .filter(Email.ai_parse_status == "done")
        .order_by(Email.received_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return [
        EmailParsedOut(
            id=e.id,
            subject=e.subject,
            snippet=e.snippet,
            from_email=e.from_email,
            received_at=e.received_at,
            category=e.ai_result.category if e.ai_result else None,
            intent=e.ai_result.intent if e.ai_result else None,
            urgency=e.ai_result.urgency if e.ai_result else None,
            summary=e.ai_result.summary if e.ai_result else None,
            confidence=e.ai_result.confidence if e.ai_result else None,
        )
        for e in emails
    ]


@app.get("/dashboard/email/{email_id}", response_model=EmailParsedOut)
def dashboard_email(
    email_id: int,
    current_user: Client = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    email = (
        db.query(Email)
        .options(selectinload(Email.ai_result))
        .join(GmailAccount, Email.gmail_account_id == GmailAccount.id)
        .filter(GmailAccount.client_id == current_user.id)
        .filter(Email.id == email_id)
        .first()
    )

    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    ai = email.ai_result
    return EmailParsedOut(
        id=email.id,
        subject=email.subject,
        snippet=email.snippet,
        from_email=email.from_email,
        received_at=email.received_at,
        category=ai.category if ai else None,
        intent=ai.intent if ai else None,
        urgency=ai.urgency if ai else None,
        summary=ai.summary if ai else None,
        confidence=ai.confidence if ai else None,
    )


# Trigger fetch + parse 
def _fetch_store_parse(gmail_account_id: int):
    fetch_and_store_emails(gmail_account_id, max_results=2)


@app.post("/dashboard/parse")
def trigger_parse(
    background_tasks: BackgroundTasks,
    current_user: Client = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    gmail_accounts = (
        db.query(GmailAccount)
        .filter(
            GmailAccount.client_id == current_user.id,
            GmailAccount.is_active.is_(True),
        )
        .all()
    )

    if not gmail_accounts:
        raise HTTPException(status_code=400, detail="No connected Gmail accounts")

    for ga in gmail_accounts:
        background_tasks.add_task(_fetch_store_parse, ga.id)

    background_tasks.add_task(parse_batch_real, 10)

    return {
        "status": "queued",
        "accounts": len(gmail_accounts),
    }



@app.get("/health")
def health():
    return {"status": "ok"}
