from app.dm_service import get_dm_status


dm_id = "dm_7e4a9b3fc85f"

response = get_dm_status(dm_id)

print("Status code:", response.status_code)
print("Response:", response.text)