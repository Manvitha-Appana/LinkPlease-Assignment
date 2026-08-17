import os
import time
import threading
import requests
from dotenv import load_dotenv


load_dotenv()

PSEUDOGRAM_BASE_URL = "https://pseudogram-api.onrender.com"

_send_lock = threading.Lock()
_last_send_time = 0.0


def send_dm(recipient_user_id: str, message: str, comment_id: str):
    global _last_send_time

    api_key = os.getenv("PSEUDOGRAM_API_KEY")
    if api_key:
        api_key = api_key.strip()

    url = f"{PSEUDOGRAM_BASE_URL}/v1/dm/send"

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "recipient_user_id": recipient_user_id,
        "message": message,
        "comment_id": comment_id
    }

    max_attempts = 15

    for attempt in range(max_attempts):
        with _send_lock:
            # Respect rate limit of 10 requests per 60s (~1 req per 6s average)
            now = time.time()
            elapsed = now - _last_send_time
            if elapsed < 0.2:
                time.sleep(0.2 - elapsed)

            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=15
                )
            except requests.RequestException:
                response = None
            finally:
                _last_send_time = time.time()

        if response is not None:
            # Success: 200 or 202
            if response.status_code in (200, 202):
                return response

            # Retry on 500
            if response.status_code == 500:
                if attempt < max_attempts - 1:
                    time.sleep(1 + attempt * 0.5)
                    continue

            # Retry on 429 using Retry-After
            if response.status_code == 429:
                if attempt < max_attempts - 1:
                    retry_after = response.headers.get("Retry-After", "3")
                    try:
                        wait_seconds = float(retry_after)
                    except (ValueError, TypeError):
                        wait_seconds = 3.0
                    time.sleep(wait_seconds + 0.5)
                    continue

            # 400 or other terminal error
            return response
        else:
            # Network failure, retry
            if attempt < max_attempts - 1:
                time.sleep(1)
                continue

    return response


def get_dm_status(dm_id: str):
    api_key = os.getenv("PSEUDOGRAM_API_KEY")
    if api_key:
        api_key = api_key.strip()

    url = f"{PSEUDOGRAM_BASE_URL}/v1/dm/{dm_id}"

    headers = {
        "X-API-Key": api_key
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=15
        )
        return response
    except requests.RequestException:
        # Return a dummy 503 response if network error
        class DummyResponse:
            status_code = 503
            def json(self):
                return {}
        return DummyResponse()