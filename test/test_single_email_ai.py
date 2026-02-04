# backend/test_single_email_ai.py
from backend.db import SessionLocal
from backend.models import Email
from backend.parser import ai_parse_email, DONE, FAILED

session = SessionLocal()

# fetch a single pending email
email = session.query(Email).filter(Email.ai_parse_status == "pending").first()

if not email:
    print("No pending emails found.")
else:
    print(f"Testing AI parser on email: {email.subject}")

    try:
        result = ai_parse_email(email)
        print("AI result:", result)

        if result.get("category") == "spam":
            email.ai_parse_status = "spam"
        else:
            email.ai_parse_status = DONE

        session.commit()
        print(f"Email status updated to: {email.ai_parse_status}")

    except Exception as e:
        email.ai_parse_status = FAILED
        session.commit()
        print(f"Email parsing failed: {e}")

session.close()
