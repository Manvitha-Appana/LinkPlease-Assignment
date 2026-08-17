import time

from app.database import (
    has_user_been_processed,
    mark_user_as_processed,
    increment_stat,
    decrement_stat
)
from app.rules import find_matching_rules
from app.dm_service import send_dm, get_dm_status


def process_webhook(event):
    matching_rules = find_matching_rules(event.data.text)

    for rule in matching_rules:

        user_id = event.data.from_.user_id

        already_processed = has_user_been_processed(
            rule["rule_id"],
            user_id
        )

        if already_processed:
            increment_stat("duplicates_blocked")
            continue

        # DM is waiting to be processed
        increment_stat("queued")

        response = send_dm(
            recipient_user_id=user_id,
            message=rule["dm_message"],
            comment_id=event.data.comment_id
        )

        # Initial request failed
        if response.status_code not in (200, 202):
            decrement_stat("queued")
            increment_stat("failed")
            continue

        # Get the DM ID returned by the mock API
        try:
            dm_id = response.json()["dm_id"]
        except (KeyError, ValueError):
            decrement_stat("queued")
            increment_stat("failed")
            continue

        # Check delivery status
        delivered = False
        failed = False

        for _ in range(5):

            status_response = get_dm_status(dm_id)

            if status_response.status_code == 200:

                status_data = status_response.json()
                dm_status = status_data.get("status")

                if dm_status == "delivered":
                    delivered = True
                    break

                if dm_status == "failed":
                    failed = True
                    break

            time.sleep(2)

        # Remove from queued once processing finishes
        decrement_stat("queued")

        if delivered:

            mark_user_as_processed(
                rule["rule_id"],
                user_id
            )

            increment_stat("sent")

        elif failed:

            increment_stat("failed")

        else:

            # Still unknown after polling
            increment_stat("failed")