import requests
import random

# --- JOKE FETCHER ---
def get_joke():
    try:
        url = "https://official-joke-api.appspot.com/random_joke"
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        return f"{data['setup']} {data['punchline']}"
    except Exception as e:
        return f"Could not fetch joke right now ({e})"

# --- QUOTE FETCHER (updated) ---
FALLBACK_QUOTES = [
    "The only limit to our realization of tomorrow is our doubts of today. — Franklin D. Roosevelt",
    "In the middle of difficulty lies opportunity. — Albert Einstein",
    "Stay hungry, stay foolish. — Steve Jobs",
    "Do or do not. There is no try. — Yoda",
    "The secret of getting ahead is getting started. — Mark Twain",
    "It always seems impossible until it’s done. — Nelson Mandela",
]

def get_quote():
    # Try programming quotes API
    try:
        url = "https://programming-quotes-api.herokuapp.com/quotes/random"
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        return f"“{data.get('en')}” — {data.get('author')}"
    except Exception as e:
        print(f"[DEBUG] quote API failed: {e}")
        return f"{random.choice(FALLBACK_QUOTES)}"

# --- FACT FETCHER ---
def get_fact():
    try:
        url = "https://uselessfacts.jsph.pl/random.json?language=en"
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        return data["text"]
    except Exception as e:
        return f"Could not fetch fact right now ({e})"

# --- ROLL HANDLER ---
def roll_die(sides: int):
    try:
        sides = int(sides)
        if sides < 2:
            return "Die must have at least 2 sides."
        return f"🎲 Rolled a {sides}-sided die: {random.randint(1, sides)}"
    except Exception as e:
        return f"Invalid input: {e}"

# --- COMMAND DISPATCH ---
def get_fun_content(command: str):
    parts = command.strip().split()
    cmd = parts[0].lower()

    if cmd == "joke":
        return get_joke()
    elif cmd == "quote":
        return get_quote()
    elif cmd == "fact":
        return get_fact()
    elif cmd == "roll" and len(parts) == 2:
        return roll_die(parts[1])
    else:
        return "Unknown fun command. Try: joke, quote, fact, roll N"

# --- Self-test runner ---
if __name__ == "__main__":
    for cmd in ['joke', 'quote', 'fact', 'roll 6', 'roll two', 'unknown']:
        print(f"{cmd} → {get_fun_content(cmd)}")
