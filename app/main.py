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


@app.get("/version")
def version():
    return {"version": "v3_prod"}


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

    signature_raw = (
        x_pseudogram_signature
        or request.headers.get("x-pseudogram-signature")
        or request.headers.get("x-pseudogram-signature-256")
        or request.headers.get("x-hub-signature-256")
        or request.headers.get("signature")
        or ""
    ).strip()

    if not signature_raw:
        raise HTTPException(
            status_code=401,
            detail="Missing webhook signature"
        )

    # Extract hex digest after prefix if present
    if signature_raw.lower().startswith("sha256="):
        received_sig = signature_raw[7:].strip().lower()
    elif signature_raw.lower().startswith("sha256:"):
        received_sig = signature_raw[7:].strip().lower()
    else:
        received_sig = signature_raw.strip().lower()

    # Candidate keys: full API key, secret token part, decoded token, email, and email b64
    candidate_keys = [api_key.encode("utf-8")]
    if "." in api_key:
        parts = api_key.split(".", 1)
        # Secret token part
        candidate_keys.append(parts[1].encode("utf-8"))
        try:
            padded_secret = parts[1] + "=" * (-len(parts[1]) % 4)
            candidate_keys.append(base64.b64decode(padded_secret))
        except Exception:
            pass
        # Email part
        try:
            padded_email = parts[0] + "=" * (-len(parts[0]) % 4)
            decoded_email = base64.b64decode(padded_email)
            candidate_keys.append(decoded_email)
            candidate_keys.append(decoded_email.decode("utf-8").strip().encode("utf-8"))
        except Exception:
            pass
        candidate_keys.append(parts[0].encode("utf-8"))

    # Candidate bodies: raw wire bytes, stripped, newlines, and canonical JSON serializations
    candidate_bodies = [body, body.strip(), body.rstrip(b"\r\n"), body + b"\n", body + b"\r\n"]
    try:
        parsed_json = json.loads(body)
        candidate_bodies.extend([
            json.dumps(parsed_json).encode("utf-8"),
            json.dumps(parsed_json, separators=(",", ":")).encode("utf-8"),
            json.dumps(parsed_json, sort_keys=True).encode("utf-8"),
            json.dumps(parsed_json, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            json.dumps(parsed_json, indent=2).encode("utf-8"),
            json.dumps(parsed_json, indent=4).encode("utf-8"),
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