import json
import os

DB_FILE = "crm_db.json"


def _load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_user(user_id: str):
    data = _load_db()
    return data.get(user_id, {})


def update_user(user_id: str, key: str, value: str):
    data = _load_db()

    if user_id not in data:
        data[user_id] = {}

    data[user_id][key] = value
    _save_db(data)

    return {"status": "success", "user": data[user_id]}