import serial
import struct
import time
import sqlite3
import queue
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import threading
from datetime import datetime

# ===== CONFIG =====
SERIAL_PORT = "/dev/serial0"
BAUD_RATE = 115200
BUFFER_SIZE = 5
READ_INTERVAL_SEC = 2  # for plotting x-axis timing

START_MAGIC = b'\x55\xAA'
END_MAGIC   = b'\xAA\x55'
PACKET_BODY_LEN = 2 + BUFFER_SIZE*2*2  # packetId + sensorId + temps

# Queue to pass data to plotting thread
sample_queue = queue.Queue()
start_time = datetime.now()

# ===== PARSE PACKET =====
def parse_packet(packet_bytes):
    if len(packet_bytes) < 2:
        return None

    packetId, sensorId = struct.unpack_from('<BB', packet_bytes, 0)

    if sensorId == 0xFF:  # heartbeat
        msg = packet_bytes[1:].split(b'\x00', 1)[0].decode(errors='ignore')
        return packetId, sensorId, msg

    # normal temperature packet
    temps = []
    offset = 2
    for i in range(BUFFER_SIZE):
        if offset + 4 <= len(packet_bytes):
            t1, t2 = struct.unpack_from('<hh', packet_bytes, offset)
            temps.append((t1/10.0, t2/10.0))
            offset += 4
    return packetId, sensorId, temps

# ===== SERIAL READER THREAD =====
def serial_reader(db_conn):
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    print(f"Listening on {SERIAL_PORT} at {BAUD_RATE} baud...")
    time.sleep(2)
    buffer = bytearray()

    while True:
        try:
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
                    elapsed_sec = (datetime.now() - start_time).total_seconds()
                    elapsed_min = elapsed_sec / 60.0

                    if sensorId == 0xFF:
                        print(f"[HEARTBEAT] {data}")
                        db_conn.execute(
                            "INSERT INTO heartbeats(elapsed_min, message) VALUES (?, ?)",
                            (f"{elapsed_min:.2f}", data)
                        )
                        db_conn.commit()
                    else:
                        print(f"[ESP32 SENSOR] Packet {packetId}, Sensor {sensorId}")
                        for i, (meat, fire) in enumerate(data):
                            print(f"  Reading {i}: {meat:.1f}°F, {fire:.1f}°F")
                            sample_queue.put((elapsed_min + i*READ_INTERVAL_SEC/60.0, meat, fire))
                            db_conn.execute(
                                "INSERT INTO temperatures(elapsed_min, meat_temp, fire_temp) VALUES (?, ?, ?)",
                                (f"{elapsed_min:.2f}", meat, fire)
                            )
                        db_conn.commit()
        except KeyboardInterrupt:
            ser.close()
            return
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(0.1)

# ===== MAIN =====
if __name__ == "__main__":
    db_name = "test_espnow_fulltest.db"
    conn = sqlite3.connect(db_name, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS temperatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elapsed_min TEXT,
            meat_temp REAL,
            fire_temp REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS heartbeats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            elapsed_min TEXT,
            message TEXT
        )
    """)
    conn.commit()

    # Start serial reader thread
    reader_thread = threading.Thread(target=serial_reader, args=(conn,), daemon=True)
    reader_thread.start()

    # ===== PLOTTING =====
    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx()
    times, meats, fires = [], [], []

    def update(frame):
        while not sample_queue.empty():
            elapsed_min, meat, fire = sample_queue.get()
            times.append(elapsed_min)
            meats.append(meat)
            fires.append(fire)

        ax1.clear()
        ax2.clear()
        ax1.plot(times, meats, color="red", label="Meat Temp (°F)")
        ax2.plot(times, fires, color="orange", label="Fire Temp (°F)")

        ax1.set_xlabel("Elapsed Time (minutes)")
        ax1.set_ylabel("Meat Temp (°F)", color="red")
        ax2.set_ylabel("Fire Temp (°F)", color="orange")
        ax2.yaxis.set_label_position('right')
        ax2.yaxis.tick_right()
        ax1.tick_params(axis='y', labelcolor="red")
        ax2.tick_params(axis='y', labelcolor="orange")
        ax1.legend(loc="upper left")
        ax2.legend(loc="upper right")

        if times:
            ax1.set_xlim(left=max(0, times[0]-0.1), right=(times[-1]+0.1))
        plt.tight_layout()

    ani = FuncAnimation(fig, update, interval=1000)
    plt.show()
