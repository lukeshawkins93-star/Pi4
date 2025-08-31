#!/usr/bin/env python3
import argparse
import time
import math
import os
import sqlite3
import sys
#import logging
import requests
import json
from collections import deque
from datetime import date
from sendtelegrammessage import send_message

# ------------------- Config -------------------
#CALIBRATION_OFFSETS = {'meat': -3, 'fire': -3.3, 'air1': 0.1, 'air2': -0.4}
CALIBRATION_OFFSETS = {'meat': 0, 'fire': 0, 'air1': 0, 'air2': 0}

SAMPLING_INTERVAL_SECONDS = 1
ROLLING_AVG_PERIOD_SECONDS = 60
TELEGRAM_UPDATE_MINUTES = 30
DB_DIR = "databases"
LOG_DIR = "logs"
TEMP_LIMITS_FILE = "temp_limits.json"
FORCE_CLI = True  # Always show CLI bars

# ------------------- Rolling Buffers -------------------
meat_temps = deque(maxlen=ROLLING_AVG_PERIOD_SECONDS)
fire_temps = deque(maxlen=ROLLING_AVG_PERIOD_SECONDS)

# ------------------- Logging -------------------
os.makedirs(DB_DIR, exist_ok=True)
#os.makedirs(LOG_DIR, exist_ok=True)
#logging.basicConfig(
#    level=logging.INFO,
#    format='%(asctime)s %(levelname)s: %(message)s',
    #handlers=[logging.FileHandler(os.path.join(LOG_DIR, "smoker.log")), logging.StreamHandler()]
    #handlers=[logging.FileHandler(os.path.join(LOG_DIR, "smoker.log"))]

#)

# ------------------- Arguments -------------------
parser = argparse.ArgumentParser(description="Smoker Temperature Monitor")
parser.add_argument("db_filename", help="Database filename")
parser.add_argument("--fire_upper", type=float, required=True)
parser.add_argument("--fire_lower", type=float, required=True)
parser.add_argument("--meat_upper", type=float, required=True)
parser.add_argument("--notes", type=str, default="")

# Ignore unknown args so extra flags (e.g., --force-tty) don't break script
args, unknown = parser.parse_known_args()

# ------------------- DB Setup -------------------
db_path = os.path.join(DB_DIR, args.db_filename.strip())
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS smoker_test (
    minutes REAL,
    meat_temp REAL,
    fire_temp REAL,
    air1 REAL,
    air2 REAL,
    notes TEXT
)
""")
conn.commit()

# ------------------- Global State -------------------
last_telegram_time = 0
start_time = time.time()

# ------------------- Helper Functions -------------------
def send_message_safe(message):
    try:
        send_message(message)
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")

def get_thermometer_data(url="http://192.168.254.25", retries=3, delay=2):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data_text = response.text.strip()
            values = [float(x) for x in data_text.split(",")]
            if len(values) != 4:
                raise ValueError("Expected 4 values from thermometer")
            return values
        except Exception as e:
            logging.warning(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(delay)
    logging.error("Failed to get thermometer data after retries")
    send_message_safe("ERROR: Unable to fetch thermometer data after multiple attempts.")
    return None

def render_temp_bar(current, lower, upper, meat=False, length=30):
    if current is None or math.isnan(current):
        return "░" * length

    current = max(min(current, upper), lower)
    fill_ratio = (current - lower) / (upper - lower)
    filled_length = int(round(length * fill_ratio))
    empty_length = length - filled_length

    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    ORANGE = '\033[33m'
    RED = '\033[91m'
    RESET = '\033[0m'

    if meat:
        color = RED if fill_ratio >= 0.9 else GREEN
    else:
        if fill_ratio <= 0.7:
            color = GREEN
        elif fill_ratio <= 0.85:
            color = YELLOW
        elif fill_ratio <= 1.0:
            color = ORANGE
        else:
            color = RED

    return color + "█" * filled_length + RESET + "░" * empty_length

def update_temp_limits_json(fire_avg, meat_avg):
    try:
        if os.path.exists(TEMP_LIMITS_FILE):
            with open(TEMP_LIMITS_FILE, "r") as f:
                data = json.load(f)
        else:
            data = {}
        data['fire_avg'] = fire_avg
        data['meat_avg'] = meat_avg
        with open(TEMP_LIMITS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to update temp_limits.json: {e}")

def print_temp_line(avg_meat, avg_fire, elapsed_minutes, meat_bar, fire_bar):
    line = f"MEAT {avg_meat:6.1f}F [{meat_bar}]  FIRE {avg_fire:6.1f}F [{fire_bar}]  Time {elapsed_minutes:6.2f} min"
    # Clear the line first
    sys.stdout.write("\033[2K\r")  # ANSI escape: clear line + carriage return
    sys.stdout.write(line)
    sys.stdout.flush()

def print_temp_line(avg_meat, avg_fire, elapsed_minutes, meat_bar, fire_bar, line_length=120):
    line = f"MEAT {avg_meat:6.1f}F [{meat_bar}]  FIRE {avg_fire:6.1f}F [{fire_bar}]  Time {elapsed_minutes:6.2f} min"
    # Pad the line to overwrite previous longer content
    padded_line = line.ljust(line_length)
    # Clear the line first
    sys.stdout.write("\033[2K\r")  # ANSI: clear line + carriage return
    sys.stdout.write(padded_line)
    sys.stdout.flush()

def collect_data(elapsed_minutes):
    global meat_temps, fire_temps, last_telegram_time

    data = get_thermometer_data()
    if not data:
        return None

    meat_raw, fire_raw, air1_raw, air2_raw = data
    meat_temp = round(meat_raw + CALIBRATION_OFFSETS['meat'], 1)
    fire_temp = round(fire_raw + CALIBRATION_OFFSETS['fire'], 1)
    air1 = round(air1_raw + CALIBRATION_OFFSETS['air1'], 1)
    air2 = round(air2_raw + CALIBRATION_OFFSETS['air2'], 1)

    meat_temps.append(meat_temp)
    fire_temps.append(fire_temp)

    avg_meat = sum(meat_temps)/len(meat_temps)
    avg_fire = sum(fire_temps)/len(fire_temps)

    meat_bar = render_temp_bar(avg_meat, 40, args.meat_upper, meat=True)
    fire_bar = render_temp_bar(avg_fire, args.fire_lower, args.fire_upper, meat=False)

    # Print live CLI output (force display)
    #print(f"MEAT {avg_meat:6.1f}F [{meat_bar}]  FIRE {avg_fire:6.1f}F [{fire_bar}]  Time {elapsed_minutes:6.2f} min", end="\r", flush=True)
    #print(f"MEAT {avg_meat:6.1f}F [{meat_bar}]  FIRE {avg_fire:6.1f}F [{fire_bar}]  Time {elapsed_minutes:6.2f} min", end="\r", flush=True)
    print_temp_line(avg_meat, avg_fire, elapsed_minutes, meat_bar, fire_bar)


    # Insert into DB
    try:
        c.execute("INSERT INTO smoker_test (minutes, meat_temp, fire_temp, air1, air2, notes) VALUES (?, ?, ?, ?, ?, ?)",
                  (elapsed_minutes, avg_meat, avg_fire, air1, air2, args.notes))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database insert error: {e}")
        conn.rollback()

    # Update rolling-average in JSON
    update_temp_limits_json(avg_fire, avg_meat)

    # Send Telegram every TELEGRAM_UPDATE_MINUTES
    if elapsed_minutes - last_telegram_time >= TELEGRAM_UPDATE_MINUTES:
        last_telegram_time = elapsed_minutes
        send_message_safe(f"MEAT {avg_meat:6.1f}F  FIRE {avg_fire:6.1f}F  Time {elapsed_minutes:6.2f} min")

    return (avg_meat, avg_fire, air1, air2)

def save_data(datapoint, filename):
    if datapoint is None:
        return
    try:
        with open(f'{filename}.txt', 'a') as f:
            print(datapoint, file=f)
    except IOError as e:
        logging.error(f"Failed to write to file {filename}.txt: {e}")

def setup_files():
    filename = date.today().strftime("%Y-%m-%d")
    try:
        open(f'{filename}.txt', 'a').close()
    except IOError as e:
        logging.error(f"Failed to open data file {filename}.txt: {e}")
    return filename

def thermometer_main():
    filename = setup_files()
    global start_time
    try:
        while True:
            elapsed_min = (time.time() - start_time)/60
            datapoint = collect_data(elapsed_min)
            save_data(datapoint, filename)
            time.sleep(SAMPLING_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logging.info("Terminated by user.")
    except Exception as e:
        logging.error(f"Unexpected error in main loop: {e}")
        send_message_safe(f"ERROR: Script crashed: {e}")
        time.sleep(10)

# ------------------- Run -------------------
if __name__ == "__main__":
    #logging.info("Starting Smoker Temperature Logger")
    #logging.info(f"DB: {db_path}")
    #logging.info(f"Fire Limits: {args.fire_lower}-{args.fire_upper} F")
    #logging.info(f"Meat Upper Limit: {args.meat_upper} F")
    #logging.info(f"Notes: {args.notes}")
    thermometer_main()
