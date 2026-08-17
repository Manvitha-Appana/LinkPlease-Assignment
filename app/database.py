import sqlite3


DATABASE_NAME = "linkplease.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_NAME, timeout=30.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


def initialize_database():
    connection = get_connection()
    cursor = connection.cursor()

    # Rules table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rules (
            rule_id TEXT PRIMARY KEY,
            keyword TEXT NOT NULL,
            dm_message TEXT NOT NULL
        )
    """)

    # Processed users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            UNIQUE(rule_id, user_id)
        )
    """)

    # Processed events table to prevent duplicate webhook processing
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_events (
            event_id TEXT PRIMARY KEY
        )
    """)

    # Statistics table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            sent INTEGER NOT NULL DEFAULT 0,
            failed INTEGER NOT NULL DEFAULT 0,
            queued INTEGER NOT NULL DEFAULT 0,
            duplicates_blocked INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Create the single statistics row
    cursor.execute("""
        INSERT OR IGNORE INTO stats (
            id,
            sent,
            failed,
            queued,
            duplicates_blocked
        )
        VALUES (1, 0, 0, 0, 0)
    """)

    connection.commit()
    connection.close()


def try_claim_user_for_rule(rule_id: str, user_id: str) -> bool:
    """
    Atomically records (rule_id, user_id) in processed_users.
    Returns True if successfully claimed, False if already processed.
    """
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO processed_users (rule_id, user_id)
            VALUES (?, ?)
            """,
            (rule_id, user_id)
        )
        connection.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        connection.close()


def unclaim_user_for_rule(rule_id: str, user_id: str):
    """
    Removes the claim if sending ultimately failed permanently.
    """
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        DELETE FROM processed_users
        WHERE rule_id = ? AND user_id = ?
        """,
        (rule_id, user_id)
    )
    connection.commit()
    connection.close()


def is_event_duplicate_or_record(event_id: str) -> bool:
    """
    Records event_id atomically. Returns True if event was already processed.
    """
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO processed_events (event_id) VALUES (?)",
            (event_id,)
        )
        connection.commit()
        return False
    except sqlite3.IntegrityError:
        return True
    finally:
        connection.close()


def increment_stat(stat_name: str):
    allowed_stats = {
        "sent",
        "failed",
        "queued",
        "duplicates_blocked"
    }

    if stat_name not in allowed_stats:
        raise ValueError("Invalid statistic name")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        f"""
        UPDATE stats
        SET {stat_name} = {stat_name} + 1
        WHERE id = 1
        """
    )

    connection.commit()
    connection.close()


def decrement_stat(stat_name: str):
    allowed_stats = {
        "sent",
        "failed",
        "queued",
        "duplicates_blocked"
    }

    if stat_name not in allowed_stats:
        raise ValueError("Invalid statistic name")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        f"""
        UPDATE stats
        SET {stat_name} = MAX({stat_name} - 1, 0)
        WHERE id = 1
        """
    )

    connection.commit()
    connection.close()


def get_stats():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            sent,
            failed,
            queued,
            duplicates_blocked
        FROM stats
        WHERE id = 1
    """)

    row = cursor.fetchone()
    connection.close()

    return dict(row)