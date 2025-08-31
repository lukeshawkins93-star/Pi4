#!/bin/bash
ESP_MAC="10:B4:1D:13:4A:7A"

echo "=== Cleaning up previous BLE state ==="

# Restart adapter to clear any stale state
echo "Restarting Bluetooth adapter..."
sudo systemctl restart bluetooth
sleep 3

# Wait for ESP32 to appear in scan
echo "Scanning for ESP32..."
FOUND=0
for i in {1..10}; do
    SCAN_OUTPUT=$(timeout 3 bluetoothctl scan on | grep $ESP_MAC)
    if [[ ! -z "$SCAN_OUTPUT" ]]; then
        FOUND=1
        break
    fi
    echo "Attempt $i: ESP32 not found yet, retrying..."
    sleep 1
done

if [[ $FOUND -eq 0 ]]; then
    echo "ESP32 not found after 10 seconds, aborting."
    exit 1
fi

echo "ESP32 found, starting Python BLE receiver..."
python3 test_bluetooth_grilltemp_receiver.py
