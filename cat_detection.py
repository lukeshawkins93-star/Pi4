#!/usr/bin/env python3

import cv2
from ultralytics import YOLO
import time
import signal
from telegram_utils import load_bot_config, send_photo
import os
from datetime import datetime

# --- CONFIG ---
CONF_THRESHOLD = 0.5
CAM_INDEX = 0
COCO_CAT_CLASS = 15       # YOLOv8 COCO 'cat' class
COCO_DOG_CLASS = 16       # YOLOv8 COCO 'dog' class
MOTION_THRESHOLD = 5000   # pixels; adjust sensitivity
CHECK_INTERVAL = 1        # seconds between frame checks
LATEST_FRAME_FILE = "latest_frame.jpg"  # only keep latest frame
PHOTO_COOLDOWN = 30       # seconds between sending photos
BOT_NAME = "weather_bot"  # replace with your bot name if different
# ----------------------

# Load YOLO model
try:
    model = YOLO("yolov8n.pt")
except Exception as e:
    print(f"[ERROR] Failed to load YOLO model: {e}")
    raise

# Load bot config
try:
    bot_token, chat_id = load_bot_config(BOT_NAME)
except Exception as e:
    print(f"[ERROR] Failed to load bot config: {e}")
    raise

# Open camera
cap = cv2.VideoCapture(CAM_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

prev_gray = None
last_photo_time = 0
running = True

def shutdown_handler(signum, frame):
    global running
    print("[INFO] Shutting down gracefully...")
    running = False

# Catch termination signals
signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

def detect_motion(prev_gray, gray):
    frame_delta = cv2.absdiff(prev_gray, gray)
    thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
    motion_area = cv2.countNonZero(thresh)
    return motion_area > MOTION_THRESHOLD

def detect_animals(frame):
    detected = []
    try:
        results = model(frame)
    except Exception as e:
        print(f"[ERROR] YOLO inference failed: {e}")
        return detected

    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            if conf < CONF_THRESHOLD:
                continue
            if cls == COCO_CAT_CLASS:
                detected.append("cat")
            elif cls == COCO_DOG_CLASS:
                detected.append("dog")
    return detected

def save_and_send(frame, animal):
    global last_photo_time
    now = time.time()
    if now - last_photo_time < PHOTO_COOLDOWN:
        return
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{animal}_{timestamp}.jpg"
    try:
        cv2.imwrite(filename, frame)
        # Overwrite latest frame file to save space
        cv2.imwrite(LATEST_FRAME_FILE, frame)
        print(f"[INFO] {animal.capitalize()} detected! Saved {filename}")
    except Exception as e:
        print(f"[ERROR] Failed to save image: {e}")
        return
    try:
        send_photo(photo_path=filename, bot_token=bot_token, chat_id=chat_id)
        last_photo_time = now
    except Exception as e:
        print(f"[ERROR] Failed to send photo: {e}")

try:
    print("[INFO] Starting motion-based cat and dog detection...")
    while running:
        try:
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] Failed to capture frame. Retrying...")
                time.sleep(1)
                continue
        except Exception as e:
            print(f"[ERROR] Camera read failed: {e}")
            time.sleep(1)
            continue

        # Motion detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        motion_detected = False
        if prev_gray is None:
            prev_gray = gray
        else:
            motion_detected = detect_motion(prev_gray, gray)
            prev_gray = gray

        if motion_detected:
            animals = detect_animals(frame)
            for animal in animals:
                save_and_send(frame, animal)

        # Always update latest frame for listener
        try:
            cv2.imwrite(LATEST_FRAME_FILE, frame)
        except Exception as e:
            print(f"[ERROR] Failed to update latest frame: {e}")

        time.sleep(CHECK_INTERVAL)

finally:
    print("[INFO] Releasing camera...")
    cap.release()
