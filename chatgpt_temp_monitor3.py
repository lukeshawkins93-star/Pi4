#!/usr/bin/env python3
import argparse
import time
import math
import os
import sqlite3
import sys
import requests
import json
from collections import deque
from datetime import date
from sendtelegrammessage import send_message
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# ------------------- Config -------------------
CALIBRATION_OFFSETS = {'meat': 0, 'fire': 0, 'air1': 0, 'air2': 0}
SAMPLING_INTERVAL_SECONDS = 1
ROLLING_AVG_PERIOD_SECONDS = 60
TELEGRAM_UPDATE_MINUTES = 30
DB_DIR = "databases"
TEMP_LIMITS_FILE = "temp_limits.json"
FORCE_CLI = True  # Always show CLI bars

# ------------------- Rolling Buffers -------------------
meat_temps = deque(maxlen=ROLLING_AVG_PERIOD_SECONDS)
fire_temps = deque(maxlen=ROLLING_AVG_PERIOD_SECONDS)
success_count = 0
attempt_count = 0

# ------------------- DB Setup -------------------
parser = argparse.ArgumentParser(description="Smoker Temperature Monitor")
parser.add_argument("db_filename", help="Database filename")
parser.add_argument("--fire_upper", type=float, required=True)
parser.add_argument("--fire_lower", type=float, required=True)
parser.add_argument("--meat_upper", type=float, required=True)
parser.add_argument("--notes", type=str, default="")
args, unknown = parser.parse_known_args()

db_path = os.path.join(DB_DIR, args.db_filename.strip())
os.makedirs(DB_DIR, exist_ok=True)
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
        print(f"Telegram send failed: {e}")

def get_thermometer_data(url="http://192.168.254.25", retries=3, delay=2):
    global attempt_count, success_count
    attempt_count += 1
    for _ in range(retries):
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            values = [float(x) for x in response.text.strip().split(",")]
            if len(values) != 4:
                raise ValueError("Expected 4 values from thermometer")
            success_count += 1
            return values
        except Exception as e:
            time.sleep(delay)
    return None

def render_temp_bar(current, lower, upper, meat=False, length=30):
    if current is None or math.isnan(current):
        return "░" * length
    current = max(min(current, upper), lower)
    fill_ratio = (current - lower) / (upper - lower)
    filled_length = int(round(length * fill_ratio))
    empty_length = length - filled_length
    GREEN = '\033[92m'; YELLOW = '\033[93m'; ORANGE = '\033[33m'; RED = '\033[91m'; RESET = '\033[0m'
    if meat: color = RED if fill_ratio >= 0.9 else GREEN
    else:
        if fill_ratio <= 0.7: color = GREEN
        elif fill_ratio <= 0.85: color = YELLOW
        elif fill_ratio <= 1.0: color = ORANGE
        else: color = RED
    return color + "█" * filled_length + RESET + "░" * empty_length

def print_temp_line(avg_meat, avg_fire, elapsed_minutes, meat_bar, fire_bar, line_length=140):
    success_pct = 100 * success_count / attempt_count if attempt_count else 0
    line = f"MEAT {avg_meat:5.1f}F [{meat_bar}]  FIRE {avg_fire:5.1f}F [{fire_bar}]  Time {elapsed_minutes:6.2f} min  Success {success_pct:5.1f}%"
    sys.stdout.write("\033[2K\r" + line.ljust(line_length))
    sys.stdout.flush()

def update_temp_limits_json(fire_avg, meat_avg):
    try:
        data = json.load(open(TEMP_LIMITS_FILE)) if os.path.exists(TEMP_LIMITS_FILE) else {}
        data['fire_avg'] = fire_avg; data['meat_avg'] = meat_avg
        json.dump(data, open(TEMP_LIMITS_FILE, "w"), indent=2)
    except Exception as e:
        print(f"Failed to update JSON: {e}")

def collect_data(elapsed_minutes):
    data = get_thermometer_data()
    if not data:
        return None
    meat_temp = round((data[0] + CALIBRATION_OFFSETS['meat']) * 2) / 2
    fire_temp = round((data[1] + CALIBRATION_OFFSETS['fire']) * 2) / 2
    air1 = round(data[2] + CALIBRATION_OFFSETS['air1'], 1)
    air2 = round(data[3] + CALIBRATION_OFFSETS['air2'], 1)
    meat_temps.append(meat_temp); fire_temps.append(fire_temp)
    avg_meat = sum(meat_temps)/len(meat_temps)
    avg_fire = sum(fire_temps)/len(fire_temps)
    meat_bar = render_temp_bar(avg_meat, 40, args.meat_upper, meat=True)
    fire_bar = render_temp_bar(avg_fire, args.fire_lower, args.fire_upper)
    print_temp_line(avg_meat, avg_fire, elapsed_minutes, meat_bar, fire_bar)
    try:
        c.execute("INSERT INTO smoker_test (minutes, meat_temp, fire_temp, air1, air2, notes) VALUES (?, ?, ?, ?, ?, ?)",
                  (elapsed_minutes, avg_meat, avg_fire, air1, air2, args.notes))
        conn.commit()
    except:
        conn.rollback()
    update_temp_limits_json(avg_fire, avg_meat)
    global last_telegram_time
    if elapsed_minutes - last_telegram_time >= TELEGRAM_UPDATE_MINUTES:
        last_telegram_time = elapsed_minutes
        send_message_safe(f"MEAT {avg_meat}F FIRE {avg_fire}F Time {elapsed_minutes:.2f} min")
    return avg_meat, avg_fire

# ------------------- Real-time Plot -------------------
plt.ion()
fig, ax = plt.subplots()
meat_line, = ax.plot([], [], label="Meat Temp")
fire_line, = ax.plot([], [], label="Fire Temp")
ax.set_xlabel("Time (s)")
ax.set_ylabel("Temperature (F)")
ax.legend()
ax.grid(True)
xdata, meat_data, fire_data = [], [], []

def update_plot(avg_meat, avg_fire, elapsed_seconds):
    xdata.append(elapsed_seconds)
    meat_data.append(avg_meat)
    fire_data.append(avg_fire)
    meat_line.set_data(xdata, meat_data)
    fire_line.set_data(xdata, fire_data)
    ax.relim(); ax.autoscale_view()
    plt.pause(0.001)

# ------------------- Main Loop -------------------
def thermometer_main():
    filename = date.today().strftime("%Y-%m-%d")
    open(f'{filename}.txt', 'a').close()
    try:
        while True:
            elapsed_sec = time.time() - start_time
            elapsed_min = elapsed_sec / 60
            datapoint = collect_data(elapsed_min)
            if datapoint:
                avg_meat, avg_fire = datapoint
                update_plot(avg_meat, avg_fire, elapsed_sec)
            time.sleep(SAMPLING_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nTerminated by user.")

# ------------------- Run -------------------
if __name__ == "__main__":
    thermometer_main()
