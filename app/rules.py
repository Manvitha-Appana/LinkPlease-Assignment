import uuid

from app.database import get_connection


def create_rule(keyword: str, dm_message: str):
    rule_id = str(uuid.uuid4())

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO rules (rule_id, keyword, dm_message)
        VALUES (?, ?, ?)
        """,
        (rule_id, keyword, dm_message)
    )

    connection.commit()
    connection.close()

    return {
        "rule_id": rule_id,
        "keyword": keyword,
        "dm_message": dm_message
    }
def find_matching_rules(comment_text: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM rules")

    rules = cursor.fetchall()
    connection.close()

    matching_rules = []

    for rule in rules:
        if rule["keyword"].lower() in comment_text.lower():
            matching_rules.append(dict(rule))

    return matching_rules