#!/usr/bin/env python3
import os
import sys
import time
import json
import subprocess
import random  # for dice roll
from telegram_utils import get_updates, send_message, send_photo, load_bot_config
from nfl_schedule import fetch_nfl_schedule
from steelers_report import get_scoreboard
from fun_fetcher import get_fun_content  # <-- import joke/quote/fact fetcher


BOT_NAME = os.getenv("TELEGRAM_BOT_NAME", "weather_bot")
TEMP_LIMITS_FILE = "temp_limits.json"
CHECK_INTERVAL = 1

# --- Load bot token ---
bot_token, _ = load_bot_config(BOT_NAME)

# --- Load Jeopardy questions ---
JEOPARDY_FILE = "JEOPARDY_QUESTIONS1.json"
try:
    with open(JEOPARDY_FILE, "r", encoding="utf-8") as f:
        jeopardy_questions = json.load(f)
except Exception as e:
    print(f"[ERROR] Failed to load Jeopardy questions: {e}", file=sys.stderr)
    jeopardy_questions = []
    
# Tracks active Jeopardy questions per chat
active_questions = {}  # chat_id -> {"question": ..., "answer": ...}


def get_random_jeopardy_question():
    if not jeopardy_questions:
        return "⚠️ No Jeopardy questions available."
    q = random.choice(jeopardy_questions)
    category = q.get("category", "Unknown")
    value = q.get("value", "N/A")
    question = q.get("question", "No question text")
    answer = q.get("answer", "No answer provided")
    return f"🎯 Category: {category}\n💰 Value: {value}\n❓ Question: {question}\n✅ Answer: {answer}"


# --- Load or initialize limits ---
def load_limits():
    if os.path.exists(TEMP_LIMITS_FILE):
        try:
            with open(TEMP_LIMITS_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("[WARNING] Could not parse JSON, using defaults.", file=sys.stderr)
    return {"fire_upper": 300, "fire_lower": 200, "meat_upper": 125}

def save_limits(limits):
    with open(TEMP_LIMITS_FILE, "w") as f:
        json.dump(limits, f, indent=2)
    print(f"[DEBUG] Saved limits: {limits}", file=sys.stderr)

limits = load_limits()
offset = None
print("[DEBUG] Listener starting...", file=sys.stderr)

# --- Weather helper ---
def run_weather_script():
    script_path = os.path.join(os.path.dirname(__file__), "noaa_weather_report.py")
    try:
        result = subprocess.run([sys.executable, script_path], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return f"Weather script error:\n{result.stderr}"
        return result.stdout
    except Exception as e:
        return f"Failed to run weather script: {e}"

# --- Dice roller ---
def roll_die(sides: int) -> str:
    if sides < 2:
        return "⚠️ Number of sides must be at least 2."
    result = random.randint(1, sides)
    return f"🎲 Rolled a {sides}-sided die: {result}"

while True:
    try:
        updates = get_updates(bot_token, offset)
        if "result" in updates:
            for update in updates["result"]:
                offset = update["update_id"] + 1
                if "message" in update and "text" in update["message"]:
                    text = update["message"]["text"].strip()
                    chat_id = update["message"]["chat"]["id"]
                    parts = text.split()
                    if not parts:
                        continue
                    cmd = parts[0].lower()

                    if cmd == "setlimit" and len(parts) == 3:
                        key, value_str = parts[1], parts[2]
                        if key in limits:
                            try:
                                value = float(value_str)
                                limits[key] = value
                                save_limits(limits)
                                send_message(f"✅ Updated {key} to {value}", bot_token, chat_id)
                            except ValueError:
                                send_message("❌ Value must be a number", bot_token, chat_id)
                        else:
                            send_message(f"❌ Unknown limit name '{key}'", bot_token, chat_id)

                    elif cmd == "getlimits":
                        msg = "\n".join([f"{k}: {v}" for k, v in limits.items()])
                        send_message(f"Current limits:\n{msg}", bot_token, chat_id)
                    
                    elif cmd == "temps":
                        try:
                            with open(TEMP_LIMITS_FILE, "r") as f:
                                data = json.load(f)
                            meat_avg = data.get("meat_avg")
                            fire_avg = data.get("fire_avg")
                            if meat_avg is None or fire_avg is None:
                                send_message("⚠️ Rolling-average temps not yet available.", bot_token, chat_id)
                            else:
                                send_message(f"🥩 Meat avg: {meat_avg:.1f}°F\n🔥 Fire avg: {fire_avg:.1f}°F", bot_token, chat_id)
                        except Exception as e:
                            send_message(f"⚠️ Failed to read rolling-average temps: {e}", bot_token, chat_id)

                    elif cmd == "weather":
                        send_message("Fetching NOAA weather forecast...", bot_token, chat_id)
                        weather_output = run_weather_script()
                        send_message(weather_output, bot_token, chat_id)

                    elif cmd in ("football", "nfl"):
                        try:
                            games = fetch_nfl_schedule()
                            if not games:
                                send_message("No NFL games found in the next 8 days.", bot_token, chat_id)
                            else:
                                message = "Upcoming NFL Games:\n\n" + "\n".join(games)
                                send_message(message, bot_token, chat_id)
                        except Exception as e:
                            send_message(f"⚠ Error fetching NFL schedule: {e}", bot_token, chat_id)
                            print(f"[ERROR] NFL command exception: {e}", file=sys.stderr)

                    elif cmd == "steelers":
                        from steelers_report import get_steelers_report
                        try:
                            message = get_steelers_report()
                            send_message(message, bot_token, chat_id)
                        except Exception as e:
                            send_message(f"⚠ Steelers command exception: {e}", bot_token, chat_id)

                    elif cmd in ("joke", "quote"):
                        try:
                            message = get_fun_content(cmd)
                            send_message(message, bot_token, chat_id)
                        except Exception as e:
                            send_message(f"⚠ Error fetching {cmd}: {e}", bot_token, chat_id)
                    elif cmd == "fact":
                        if not jeopardy_questions:
                            send_message("⚠️ No Jeopardy questions available.", bot_token, chat_id)
                            continue

                        q = random.choice(jeopardy_questions)

                        # Ensure q is a dict
                        if isinstance(q, dict):
                            category = q.get("category", "Unknown")
                            value = q.get("value", "N/A")
                            question_text = q.get("question", "No question text")
                            answer_text = q.get("answer", "No answer provided")
                        else:
                            category = "Unknown"
                            value = "N/A"
                            question_text = str(q)
                            answer_text = "Answer not available"

                        # Store active question for this chat
                        active_questions[chat_id] = {"question": question_text, "answer": answer_text}

                        # Send the question
                        send_message(f"🎯 Category: {category}\n💰 Value: {value}\n❓ Question: {question_text}\n\nType 'answer' to see the answer.", bot_token, chat_id)

                    elif cmd == "answer":
                        if chat_id in active_questions:
                            answer_text = active_questions[chat_id]["answer"]
                            send_message(f"✅ Answer: {answer_text}", bot_token, chat_id)
                            # Remove the question so "answer" can’t be reused
                            del active_questions[chat_id]
                        else:
                            send_message("⚠️ No active question. Type 'fact' to get a new question.", bot_token, chat_id)


                    # --- FUN FETCHER ---
                    elif cmd in ("joke", "quote", "fact"):
                        try:
                            message = get_fun_content(cmd)
                            send_message(message, bot_token, chat_id)
                        except Exception as e:
                            send_message(f"⚠ Error fetching {cmd}: {e}", bot_token, chat_id)

                    # --- DICE ROLL ---
                    elif cmd == "roll" and len(parts) == 2:
                        try:
                            sides = int(parts[1])
                            send_message(roll_die(sides), bot_token, chat_id)
                        except ValueError:
                            send_message("⚠️ Usage: roll <number_of_sides>", bot_token, chat_id)

                    elif cmd == "help":
                        send_message(
                            "Available commands:\n"
                            "setlimit <name> <value> - update a temperature limit\n"
                            "getlimits - view current limits\n"
                            "temps - view rolling average temps\n"
                            "weather - get NOAA weather forecast\n"
                            "nfl / football - get upcoming NFL schedule\n"
                            "steelers - Steelers game report (if available)\n"
                            "scores - NFL scoreboard\n"
                            "joke - get a random joke\n"
                            "quote - get a random quote\n"
                            "fact - get a trivia fact\n"
                            "roll <n> - roll a die with n sides\n"
                            "help - show this message",
                            bot_token,
                            chat_id
                        )

    except Exception as e:
        print(f"[ERROR] Listener loop exception: {e}", file=sys.stderr)
        time.sleep(5)

    time.sleep(CHECK_INTERVAL)
