import time

from app.database import (
    try_claim_user_for_rule,
    unclaim_user_for_rule,
    is_event_duplicate_or_record,
    increment_stat,
    decrement_stat
)
from app.rules import find_matching_rules
from app.dm_service import send_dm, get_dm_status


def process_webhook(event):
    # Event-level deduplication
    if is_event_duplicate_or_record(event.event_id):
        increment_stat("duplicates_blocked")
        return

    matching_rules = find_matching_rules(event.data.text)

    for rule in matching_rules:
        user_id = event.data.from_.user_id

        # Atomic user+rule duplicate protection
        claimed = try_claim_user_for_rule(
            rule["rule_id"],
            user_id
        )

        if not claimed:
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
            unclaim_user_for_rule(rule["rule_id"], user_id)
            continue

        # Get the DM ID returned by the mock API
        try:
            dm_id = response.json()["dm_id"]
        except (KeyError, ValueError, TypeError):
            decrement_stat("queued")
            increment_stat("failed")
            unclaim_user_for_rule(rule["rule_id"], user_id)
            continue

        # Check delivery status
        delivered = False
        failed = False

        for _ in range(10):
            try:
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
            except Exception:
                pass

            time.sleep(2)

        # Remove from queued once processing finishes
        decrement_stat("queued")

        if delivered:
            increment_stat("sent")
        else:
            increment_stat("failed")
            unclaim_user_for_rule(rule["rule_id"], user_id)