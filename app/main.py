import base64
import hashlib
import hmac
import json
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

    # Candidate keys: full API key, secret token part, and base64-decoded token part
    candidate_keys = [api_key.encode("utf-8")]
    if "." in api_key:
        secret_part = api_key.split(".", 1)[1]
        candidate_keys.append(secret_part.encode("utf-8"))
        try:
            padded = secret_part + "=" * (-len(secret_part) % 4)
            candidate_keys.append(base64.b64decode(padded))
        except Exception:
            pass

    # Candidate bodies: raw wire bytes, plus canonical JSON serializations
    candidate_bodies = [body]
    try:
        import json
        parsed_json = json.loads(body)
        candidate_bodies.extend([
            json.dumps(parsed_json).encode("utf-8"),
            json.dumps(parsed_json, separators=(",", ":")).encode("utf-8"),
            json.dumps(parsed_json, sort_keys=True).encode("utf-8"),
            json.dumps(parsed_json, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            json.dumps(parsed_json, indent=2).encode("utf-8"),
        ])
    except Exception:
        pass

    signature_valid = False
    for candidate_key in candidate_keys:
        for candidate_body in candidate_bodies:
            expected_sig = hmac.new(
                candidate_key,
                candidate_body,
                hashlib.sha256
            ).hexdigest().lower()
            if hmac.compare_digest(received_sig, expected_sig):
                signature_valid = True
                break
        if signature_valid:
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