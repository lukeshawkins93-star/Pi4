import json
import os
import requests

CONFIG_PATH = os.getenv("TELEGRAM_CONFIG_PATH", "telegram_config.json")

# Load default token and chat_id at import time
DEFAULT_BOT_TOKEN = None
DEFAULT_CHAT_ID = None

def load_bot_config(bot_name):
    """Load credentials for the given bot from config file."""
    global DEFAULT_BOT_TOKEN, DEFAULT_CHAT_ID
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")
    
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
    
    if bot_name not in config:
        raise ValueError(f"Bot '{bot_name}' not found in config.")
    
    DEFAULT_BOT_TOKEN = config[bot_name]["bot_token"]
    DEFAULT_CHAT_ID = config[bot_name].get("default_chat_id")
    return DEFAULT_BOT_TOKEN, DEFAULT_CHAT_ID

def send_message(message, bot_token=None, chat_id=None, parse_mode=None):
    """
    Send a Telegram message to the given chat.
    
    If bot_token or chat_id are not provided, uses defaults loaded from config.
    Maintains backwards compatibility with scripts that only pass `message`.
    """
    token = bot_token or DEFAULT_BOT_TOKEN
    chat = chat_id or DEFAULT_CHAT_ID

    if not token or not chat:
        print("[send_message] Missing bot_token or chat_id. Message:", message)
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": message}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"[send_message] Failed to send message: {e}")

def get_updates(bot_token=None, offset=None):
    """Fetch new messages from Telegram."""
    token = bot_token or DEFAULT_BOT_TOKEN
    if not token:
        raise ValueError("No bot_token available for get_updates()")

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"timeout": 10, "offset": offset}
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()

def send_photo(bot_token=None, chat_id=None, photo_path=None, frame=None):
    """Send a photo via Telegram."""
    token = bot_token or DEFAULT_BOT_TOKEN
    chat = chat_id or DEFAULT_CHAT_ID

    if not token or not chat:
        print("[send_photo] Missing bot_token or chat_id. Photo not sent.")
        return

    url = f"https://api.telegram.org/bot{token}/sendPhoto"

    if photo_path:
        with open(photo_path, "rb") as f:
            files = {"photo": f}
            data = {"chat_id": chat}
            requests.post(url, files=files, data=data)
    elif frame is not None:
        import cv2, io
        _, img_encoded = cv2.imencode(".jpg", frame)
        files = {"photo": ("frame.jpg", io.BytesIO(img_encoded.tobytes()))}
        data = {"chat_id": chat}
        requests.post(url, files=files, data=data)
    else:
        raise ValueError("Must provide photo_path or frame")
