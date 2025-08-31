import requests
from sendtelegrammessage import send_message  # Make sure this has error handling or use the below example send_message
from datetime import date
import time
import io
import sqlite3
import sys
import logging

# Setup logging to file and console with timestamps
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler("smoker.log"),
        logging.StreamHandler()
    ]
)

# Calibration constants
cal1 = -3
cal2 = 0.1
cal3 = -0.4
cal4 = -3.3

timer = 0

# Validate command line arguments
if len(sys.argv) < 5:
    logging.error("Usage: python script.py <db_filename> <upper_limit1> <upper_limit2> <notes>")
    sys.exit(1)

db_filename = sys.argv[1]
upper_limit1 = sys.argv[2]
upper_limit2 = sys.argv[3]
db_notes = sys.argv[4]

filename_str = db_filename.strip()
notes_str = ' '.join(sys.argv[4:])  # combine all notes after 3rd arg

start_time = time.time()

try:
    conn = sqlite3.connect(filename_str)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS smoker_test (
            Minutes REAL,
            temp1 REAL,
            temp2 REAL,
            temp3 REAL,
            temp4 REAL,
            notes TEXT
        )
    ''')
    c.execute("INSERT INTO smoker_test (minutes, temp1, temp2, temp3, temp4, notes) VALUES (?,?,?,?,?,?)",
              (0, 0, 0, 0, 0, notes_str))
    conn.commit()
except sqlite3.Error as e:
    logging.error(f"Database initialization error: {e}")
    send_message(f"ERROR: Could not initialize database: {e}")
    sys.exit(1)


def get_thermometer_data(url, retries=3, delay=2):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return response.text
        except (requests.RequestException, requests.Timeout) as e:
            logging.warning(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(delay)
    logging.error("Failed to get thermometer data after retries")
    send_message("ERROR: Unable to fetch thermometer data after multiple attempts.")
    return None


def send_message_safe(message):
    try:
        send_message(message)
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")


def collect_data(elapsed_minutes):
    global timer
    thermometer_api = "http://192.168.254.161"
    data_text = get_thermometer_data(thermometer_api)
    if not data_text:
        return None

    string_list = data_text.strip().split(",")
    if len(string_list) != 4:
        logging.warning(f"Unexpected data format: {string_list}")
        send_message_safe("WARNING: Thermometer data format unexpected.")
        return None

    try:
        var1, var2, var3, var4 = [float(x) for x in string_list]
    except ValueError as e:
        logging.warning(f"Sensor data parsing error: {e}")
        send_message_safe("WARNING: Could not parse thermometer readings.")
        return None

    var1 = round(var1 + cal1, 1)
    var2 = round(var2 + cal2, 1)
    var3 = round(var3 + cal3, 1)
    var4 = round(var4 + cal4, 1)

    print(f"MEAT(F):{var1} AIR(F):{var2} Time(Min):{round(elapsed_minutes, 2)}", end="\r", flush=True)

    try:
        c.execute("INSERT INTO smoker_test (minutes, temp1, temp2, temp3, temp4) VALUES (?,?,?,?,?)",
                  (elapsed_minutes, var1, var2, var3, var4))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database insert error: {e}")
        send_message_safe("ERROR: Failed to write data to database.")
        conn.rollback()

    # Send Telegram update every 5 minutes
    if (elapsed_minutes - timer) >= 5:
        timer = elapsed_minutes
        send_message_safe(f"MEAT(F):{var1} AIR(F):{var2} Time(Min):{round(elapsed_minutes, 2)}")

    return data_text


def save_data(datapoint, filename):
    if datapoint is None:
        return
    try:
        with open(f'{filename}.txt', 'a') as data_file:
            print(datapoint, file=data_file)
    except IOError as e:
        logging.error(f"Failed to write to file {filename}.txt: {e}")


def setup_files():
    current_date = date.today()
    filename = f'{current_date.strftime("%Y-%m-%d")}'
    try:
        open(f'{filename}.txt', 'a').close()  # just to ensure file exists
    except IOError as e:
        logging.error(f"Failed to open data file {filename}.txt: {e}")
    return filename


def thermometer_main():
    filename = setup_files()
    global start_time
    try:
        while True:
            elapsed_seconds = time.time() - start_time
            elapsed_minutes = elapsed_seconds / 60
            datapoint = collect_data(elapsed_minutes)
            save_data(datapoint, filename)
            time.sleep(1)  # prevent hammering CPU/network
    except KeyboardInterrupt:
        logging.info("Terminated by user.")
    except Exception as e:
        logging.error(f"Unexpected error in main loop: {e}")
        send_message_safe(f"ERROR: Script crashed: {e}")
        time.sleep(10)  # Prevent crash-loop


if __name__ == '__main__':
    logging.info("Starting smoker temperature logger.")
    thermometer_main()