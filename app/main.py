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

    expected_signature = hmac.new(
        api_key.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    expected_header = f"sha256={expected_signature}"

    if not hmac.compare_digest(
        x_pseudogram_signature,
        expected_header
    ):
       
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