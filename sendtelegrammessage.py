import requests

BOT_TOKEN = "8248911436:AAEcHc5cDmT4iI250Qqisivfh3e8quOiz0E"
CHAT_ID = "8469957334"

def send_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=payload)