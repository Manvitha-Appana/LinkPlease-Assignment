import base64
import hashlib
import hmac
import os

from fastapi import FastAPI, BackgroundTasks, Header, HTTPException, Request, status
from dotenv import load_dotenv

from app.database import initialize_database, get_stats
from app.models import RuleCreate
from app.rules import create_rule
from app.webhook import WebhookEvent
from app.worker import process_webhook
load_dotenv()


app = FastAPI()

initialize_database()


@app.get("/")
def home():
    return {"message": "LinkPlease backend is running"}


@app.post("/rules", status_code=status.HTTP_201_CREATED)
def create_rule_endpoint(rule: RuleCreate):
    return create_rule(
        rule.keyword,
        rule.dm_message
    )


@app.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_pseudogram_signature: str = Header(
        None,
        alias="X-PseudoGram-Signature"
    )
):
    body = await request.body()

    api_key = os.getenv("PSEUDOGRAM_API_KEY")

    if api_key:
        api_key = api_key.strip()

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="PSEUDOGRAM_API_KEY is not configured"
        )

    if not x_pseudogram_signature:
        raise HTTPException(
            status_code=401,
            detail="Missing webhook signature"
        )

    signature_header = x_pseudogram_signature.strip()

    if not signature_header.startswith("sha256="):
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature"
        )

    received_sig = signature_header[7:].lower()

    # The PseudoGram API key is formatted as base64(email).secret_token
    # Depending on simulator implementation, the HMAC secret is either the full key or the secret token portion
    candidate_keys = [api_key.encode("utf-8")]
    if "." in api_key:
        secret_part = api_key.split(".", 1)[1]
        candidate_keys.append(secret_part.encode("utf-8"))
        try:
            padded = secret_part + "=" * (-len(secret_part) % 4)
            candidate_keys.append(base64.b64decode(padded))
        except Exception:
            pass

    signature_valid = False
    for candidate in candidate_keys:
        expected_sig = hmac.new(
            candidate,
            body,
            hashlib.sha256
        ).hexdigest().lower()
        if hmac.compare_digest(received_sig, expected_sig):
            signature_valid = True
            break

    if not signature_valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature"
        )

    event = WebhookEvent.model_validate_json(body)

    background_tasks.add_task(
        process_webhook,
        event
    )

    return {
        "message": "Webhook received",
        "event_id": event.event_id
    }

@app.get("/stats")
def stats():
    return get_stats()