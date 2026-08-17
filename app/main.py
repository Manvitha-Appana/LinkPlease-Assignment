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

    api_key_fingerprint = hashlib.sha256(
        api_key.encode("utf-8")
    ).hexdigest()

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

    expected_signature = hmac.new(
        api_key.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest().lower()

    if not hmac.compare_digest(
        received_sig,
        expected_signature
    ):
        print(
            "WEBHOOK_SIGNATURE_DIAGNOSTIC:",
            f"api_key_fingerprint={api_key_fingerprint}",
            f"raw_body_length={len(body)}",
            f"raw_body_sha256={hashlib.sha256(body).hexdigest()}",
            f"received_signature_length={len(received_sig)}",
            f"expected_signature_length={len(expected_signature)}",
            f"received_signature_fingerprint={hashlib.sha256(received_sig.encode('utf-8')).hexdigest()}",
            f"expected_signature_fingerprint={hashlib.sha256(expected_signature.encode('utf-8')).hexdigest()}"
        )
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