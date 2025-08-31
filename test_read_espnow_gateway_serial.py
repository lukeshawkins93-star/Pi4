import serial
import struct
import time
import sqlite3
import queue
import threading
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.animation import FuncAnimation
from datetime import datetime, timedelta

# ================= CONFIG =================
SERIAL_PORT = "/dev/serial0"
BAUD_RATE = 115200
BUFFER_SIZE = 5
READ_INTERVAL_SEC = 2  # time between readings within a batch

START_MAGIC = b'\x55\xAA'
END_MAGIC   = b'\xAA\x55'
HEARTBEAT_ID = 0xFF

DB_NAME = "test_espnow_fulltest.db"

# ================= GLOBALS =================
sample_queue = queue.Queue()
buffer = bytearray()
packets_received = 0
packets_missing = 0
last_packet_id = {}
last_packet_time = None

# ================= DATABASE =================
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS temperatures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    packet_id INTEGER,
    sensor_id INTEGER,
    reading_index INTEGER,
    meat_temp REAL,
    fire_temp REAL
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS heartbeat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    message TEXT
)
""")
conn.commit()

# ================= HELPERS =================
def round_half_degree(x):
    return round(x*2)/2

def round_to_second(dt):
    return dt.replace(microsecond=0)

# ================= PARSER =================
def parse_packet(packet_bytes):
    if len(packet_bytes) < 2:
        return None
    packetId, sensorId = struct.unpack_from('<BB', packet_bytes, 0)

    if sensorId == HEARTBEAT_ID:
        msg = packet_bytes[1:].split(b'\x00', 1)[0].decode(errors='ignore')
        return packetId, sensorId, msg

    if len(packet_bytes) != 2 + BUFFER_SIZE*2*2:
        print(f"Invalid packet length: {len(packet_bytes)}")
        return None

    temps = []
    offset = 2
    for i in range(BUFFER_SIZE):
        t1, t2 = struct.unpack_from('<hh', packet_bytes, offset)
        temps.append((round_half_degree(t1/10.0), round_half_degree(t2/10.0)))
        offset += 4
    return packetId, sensorId, temps

# ================= SERIAL READER THREAD =================
def serial_reader():
    global buffer, packets_received, packets_missing, last_packet_id, last_packet_time
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    print(f"Listening on {SERIAL_PORT} at {BAUD_RATE} baud...")
    time.sleep(2)

    try:
        while True:
            chunk = ser.read(ser.in_waiting or 1)
            if chunk:
                buffer.extend(chunk)

            while True:
                start_index = buffer.find(START_MAGIC)
                end_index = buffer.find(END_MAGIC, start_index + 2)
                if start_index == -1 or end_index == -1:
                    break

                packet_bytes = buffer[start_index + 2:end_index]
                buffer = buffer[end_index + len(END_MAGIC):]

                result = parse_packet(packet_bytes)
                if result:
                    packetId, sensorId, data = result
                    now = round_to_second(datetime.now())

                    if sensorId == HEARTBEAT_ID:
                        print(f"[HEARTBEAT] {data}")
                        c.execute(
                            "INSERT INTO heartbeat (timestamp, message) VALUES (?, ?)",
                            (now.isoformat(), data)
                        )
                        conn.commit()
                    else:
                        # Update stats
                        packets_received += 1
                        if sensorId in last_packet_id:
                            gap = packetId - last_packet_id[sensorId] - 1
                            if gap > 0:
                                packets_missing += gap
                        last_packet_id[sensorId] = packetId
                        last_packet_time = now

                        print(f"[ESP32 SENSOR] Packet {packetId}, Sensor {sensorId}")
                        for i, (meat, fire) in enumerate(data):
                            reading_time = now - timedelta(seconds=(BUFFER_SIZE - i - 1)*READ_INTERVAL_SEC)
                            reading_time = round_to_second(reading_time)
                            print(f"  Reading {i}: {meat:.1f}°F, {fire:.1f}°F @ {reading_time}")
                            c.execute(
                                "INSERT INTO temperatures (timestamp, packet_id, sensor_id, reading_index, meat_temp, fire_temp) VALUES (?, ?, ?, ?, ?, ?)",
                                (reading_time.isoformat(), packetId, sensorId, i, meat, fire)
                            )
                            sample_queue.put((reading_time, meat, fire))
                        conn.commit()
    except Exception as e:
        print(f"[ERROR] Serial reader exception: {e}")
    finally:
        ser.close()

# ================= PLOTTING =================
fig, ax1 = plt.subplots()
ax2 = ax1.twinx()
times, meats, fires = [], [], []

def update_plot(frame):
    while not sample_queue.empty():
        timestamp, meat, fire = sample_queue.get()
        times.append(timestamp)
        meats.append(meat)
        fires.append(fire)

    ax1.clear()
    ax2.clear()

    if times:
        ax1.plot(times, meats, color="red", label="Meat Temp (°F)")
        ax2.plot(times, fires, color="orange", label="Fire Temp (°F)")

        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        fig.autofmt_xdate()

    # Axis labels
    ax1.set_xlabel("Time")
    ax1.set_ylabel("Meat Temp (°F)", color="red")
    ax1.tick_params(axis='y', labelcolor="red")

    ax2.set_ylabel("Fire Temp (°F)", color="orange")
    ax2.yaxis.set_label_position('right')
    ax2.yaxis.tick_right()
    ax2.tick_params(axis='y', labelcolor="orange")

    # Legends (one entry per axis)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    plt.tight_layout()

# ================= MAIN =================
if __name__ == "__main__":
    # Show initial statistics
    def show_stats():
        percent_received = (packets_received / (packets_received + packets_missing) * 100) if (packets_received + packets_missing) > 0 else 100
        minutes_since_last = (datetime.now() - last_packet_time).total_seconds()/60 if last_packet_time else 0
        print("===== PACKET STATISTICS =====")
        print(f"Packets received: {packets_received}")
        print(f"Packets missing : {packets_missing}")
        print(f"Percent received: {percent_received:.1f}%")
        print(f"Minutes since last packet: {minutes_since_last:.1f}")
        print("=============================")

    t = threading.Thread(target=serial_reader, daemon=True)
    t.start()

    # Periodically display stats
    def stats_loop():
        while True:
            time.sleep(10)
            show_stats()

    threading.Thread(target=stats_loop, daemon=True).start()
    ani = FuncAnimation(fig, update_plot, interval=1000)
    plt.show()
