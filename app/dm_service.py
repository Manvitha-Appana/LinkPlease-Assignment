import os
import time

import requests
from dotenv import load_dotenv


load_dotenv()

PSEUDOGRAM_BASE_URL = "https://pseudogram-api.onrender.com"


def send_dm(recipient_user_id: str, message: str, comment_id: str):
    api_key = os.getenv("PSEUDOGRAM_API_KEY")

    url = f"{PSEUDOGRAM_BASE_URL}/v1/dm/send"

    headers = {
        "X-API-Key": api_key
    }

    payload = {
        "recipient_user_id": recipient_user_id,
        "message": message,
        "comment_id": comment_id
    }

    max_attempts = 3

    for attempt in range(max_attempts):

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=10
        )

        # Success
        if response.status_code in (200, 202):
            return response

        # Retry on 500
        if response.status_code == 500:
            if attempt < max_attempts - 1:
                time.sleep(1)
                continue

        # Retry on 429 using Retry-After
        if response.status_code == 429:
            if attempt < max_attempts - 1:
                retry_after = response.headers.get("Retry-After", "1")

                try:
                    wait_seconds = int(retry_after)
                except ValueError:
                    wait_seconds = 1

                time.sleep(wait_seconds)
                continue

        # 400 and any other non-retryable response
        return response

    return response
def get_dm_status(dm_id: str):
    api_key = os.getenv("PSEUDOGRAM_API_KEY")

    url = f"{PSEUDOGRAM_BASE_URL}/v1/dm/{dm_id}"

    headers = {
        "X-API-Key": api_key
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=10
    )

    return response