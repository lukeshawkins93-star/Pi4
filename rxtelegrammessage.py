import requests

BOT_TOKEN = "8248911436:AAEcHc5cDmT4iI250Qqisivfh3e8quOiz0E"
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def get_updates(last_update_id=None):
    """
    Fetch new messages from Telegram.
    last_update_id: int or None — fetch only messages after this ID.
    Returns: (updates_list, new_last_update_id)
    """
    try:
        params = {"timeout": 10}
        if last_update_id:
            params["offset"] = last_update_id + 1

        r = requests.get(f"{API_URL}/getUpdates", params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        if "result" in data:
            updates = data["result"]
            if updates:
                new_last_id = updates[-1]["update_id"]
                return updates, new_last_id
        return [], last_update_id
    except Exception as e:
        print(f"Error getting updates: {e}")
        return [], last_update_id
