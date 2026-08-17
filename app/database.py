import sqlite3


DATABASE_NAME = "linkplease.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
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


def has_user_been_processed(rule_id: str, user_id: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT 1
        FROM processed_users
        WHERE rule_id = ? AND user_id = ?
        """,
        (rule_id, user_id)
    )

    result = cursor.fetchone()
    connection.close()

    return result is not None


def mark_user_as_processed(rule_id: str, user_id: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO processed_users (rule_id, user_id)
        VALUES (?, ?)
        """,
        (rule_id, user_id)
    )

    connection.commit()
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