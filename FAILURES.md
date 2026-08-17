# Known Failure Modes

1. If the application process stops while a webhook is being processed in the background, the in-memory background task is lost. There is no persistent job queue, so the event would need to be delivered again.

2. Duplicate protection is stored in SQLite using the `(rule_id, user_id)` combination. Concurrent webhook requests could potentially pass the duplicate check before either request writes the processed record, which could result in duplicate DMs.

3. If the application loses connectivity to the PseudoGram API after the DM request is accepted but before the delivery status is checked, the application may temporarily report the DM as failed even though the external API may eventually deliver it.

4. The statistics are stored locally in SQLite. If the database is deleted, corrupted, or reset, the `/stats` values will no longer represent the historical activity handled by the application.