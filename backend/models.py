from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean, func, ForeignKey
from sqlalchemy.orm import relationship
from db import Base  


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, unique=True)
    
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    notification_email = Column(String, nullable=False)  # where alerts go
    
    is_active = Column(Boolean, default=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


    gmail_accounts = relationship("GmailAccount", back_populates="client")
    notifications = relationship("Notification", back_populates="client")


class GmailAccount(Base):
    __tablename__ = "gmail_accounts"

    id = Column(Integer, primary_key=True)

    client_id = Column(Integer, ForeignKey("clients.id"), index=True)

    gmail_address = Column(String, nullable=False, index=True)
    gmail_token = Column(JSON, nullable=False)

    is_active = Column(Boolean, default=True, index=True)
    last_fetched_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


    client = relationship("Client", back_populates="gmail_accounts")
    emails = relationship("Email", back_populates="gmail_account")


class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True)

    gmail_account_id = Column(Integer, ForeignKey("gmail_accounts.id"), index=True)

    gmail_id = Column(String, unique=True, index=True)
    thread_id = Column(String, index=True)

    from_email = Column(String, index=True)
    subject = Column(String)
    snippet = Column(String)

    received_at = Column(DateTime(timezone=True), index=True)

    ai_parse_status = Column(String, default="pending", index=True)
    ai_parse_version = Column(String)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


    gmail_account = relationship("GmailAccount", back_populates="emails")
    ai_result = relationship("EmailAIResult", back_populates="email", uselist=False)
    notifications = relationship("Notification", back_populates="email")



class EmailAIResult(Base):
    __tablename__ = "email_ai_results"

    id = Column(Integer, primary_key=True)

    email_id = Column(Integer, ForeignKey("emails.id"), unique=True, index=True)

    category = Column(String, index=True)        # lead, support, spam, billing
    intent = Column(String, index=True)          # request, complaint, inquiry
    urgency = Column(String, index=True)         # low / medium / high

    extracted_entities = Column(JSON)            # names, phones, prices
    summary = Column(String)

    confidence = Column(Integer)                 # 0–100

    model_version = Column(String)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


    email = relationship("Email", back_populates="ai_result")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)

    client_id = Column(Integer, ForeignKey("clients.id"), index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), index=True)

    channel = Column(String)   # email, webhook, slack 
    status = Column(String, default="pending")

    sent_to = Column(String)
    error_message = Column(String)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


    client = relationship("Client", back_populates="notifications")
    email = relationship("Email", back_populates="notifications")
