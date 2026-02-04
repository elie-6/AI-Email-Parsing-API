from db import SessionLocal
from models import Email, EmailAIResult
import time
import openai
from datetime import datetime
from config import OPENAI_API_KEY
import json
import re

# status constants
PENDING = "pending"
PROCESSING = "processing"
DONE = "done"
FAILED = "failed"

MAX_RETRIES = 3
RETRY_DELAY = 2
BATCH_SIZE = 10

openai.api_key = OPENAI_API_KEY  # set via env variable 


def ai_parse_email(email):
  
    prompt = f"""
        You are an AI email parser. Classify the email and extract information.
        Instructions:
        - If it's spam, just return: {{"category": "spam"}}.
        - Otherwise, return JSON with:
          - category (lead, support, billing, etc.)
          - intent (request, complaint, inquiry)
          - urgency (low, medium, high)
          - extracted_entities (list any names, emails, phone numbers, prices)
          - summary (one-line summary)
        Email subject: {email.subject}
        Email snippet: {email.snippet}
        Return only JSON.
        """

    response = openai.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    content = response.choices[0].message.content.strip()

    try:
        # attempt normal parse 
        result = json.loads(content)
    except json.JSONDecodeError:
        # try to extract JSON inside any surrounding text
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                raise ValueError(f"AI returned invalid JSON: {content}")
        else:
            raise ValueError(f"AI returned invalid JSON: {content}")

    return result


def parse_batch_real(batch_size=BATCH_SIZE):
    session = SessionLocal()
    
    emails = (
        session.query(Email)
        .filter(Email.ai_parse_status == PENDING)
        .order_by(Email.received_at.asc())
        .limit(batch_size)
        .all()
    )

    print(f"Parsing {len(emails)} emails with AI...")

    to_commit = []  # batch commit

    for email in emails:
        email.ai_parse_status = PROCESSING
        to_commit.append(email)

        success = False
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = ai_parse_email(email)

                if result.get("category") == "spam":
                    print(f"Skipping spam email: {email.subject}")
                    email.ai_parse_status = "spam"
                    success = True
                    break

                ai_result = EmailAIResult(
                    email_id=email.id,
                    category=result.get("category"),
                    intent=result.get("intent"),
                    urgency=result.get("urgency"),
                    extracted_entities=result.get("extracted_entities"),
                    summary=result.get("summary"),
                    confidence=result.get("confidence", 90),
                    model_version="gpt-4.1-mini",
                    created_at=datetime.utcnow()
                )
                to_commit.append(ai_result)

                email.ai_parse_status = DONE
                print(f"Email parsed successfully: {email.subject}")
                success = True
                break

            except ValueError as e:
                print(f"Invalid JSON for email {email.id}: {e}")
                email.ai_parse_status = FAILED
                success = True
                break

            except openai.error.OpenAIError as e:
                # api/network errors 
                print(f"Attempt {attempt} failed for email {email.id}: {e}")
                time.sleep(RETRY_DELAY)

        if not success:
            email.ai_parse_status = FAILED
            print(f"Email marked as FAILED: {email.subject}")

    # batch commit all changes at once
    if to_commit:
        session.add_all(to_commit)
        session.commit()

    session.close()
