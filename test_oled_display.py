import time
import requests
import board
import adafruit_ssd1306
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

# I2C display setup
i2c = board.I2C()
disp = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)
disp.fill(0)
disp.show()

# Fonts
font_small     = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)  # top row
font_condensed = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)  # compact bottom
font_medium    = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)  # current temp

# ---------------- NOAA WEATHER ---------------- #
def fetch_weather(lat=45.487, lon=-122.8):  # default Portland, OR
    try:
        # Step 1: Get metadata
        meta = requests.get(f"https://api.weather.gov/points/{lat},{lon}", timeout=5).json()
        forecast_url = meta["properties"]["forecast"]
        stations_url = meta["properties"]["observationStations"]

        # Step 2: Get nearest station
        stations = requests.get(stations_url, timeout=5).json()
        station_id = stations["features"][0]["properties"]["stationIdentifier"]

        # Step 3: Get latest observation (actual current temp)
        obs = requests.get(f"https://api.weather.gov/stations/{station_id}/observations/latest", timeout=5).json()
        temp_c = obs["properties"]["temperature"]["value"]  # in Celsius
        if temp_c is not None:
            current_temp = f"{round(temp_c * 9/5 + 32)}°F"
        else:
            current_temp = "N/A"

        # Step 4: Get forecast highs/lows
        forecast = requests.get(forecast_url, timeout=5).json()
        periods = forecast["properties"]["periods"]

        # Today’s high
        today_high = "N/A"
        for p in periods:
            if p["name"].lower() == "today":
                today_high = f"{p['temperature']}°{p['temperatureUnit']}"
                break
        if today_high == "N/A":
            for p in periods:
                if p.get("isDaytime", False):
                    today_high = f"{p['temperature']}°{p['temperatureUnit']}"
                    break

        # Tonight’s low
        tonight_low = "N/A"
        for p in periods:
            if p["name"].lower() == "tonight":
                tonight_low = f"{p['temperature']}°{p['temperatureUnit']}"
                break

        return current_temp, today_high, tonight_low
    except Exception as e:
        return f"Err", "", ""


# ---------------- RENDER ---------------- #
def render_weather(current_temp, today_high, tonight_low):
    image = Image.new("1", (disp.width, disp.height))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, disp.width, disp.height), fill=0)

    # Top row: Date + Time
    now_time = datetime.now().strftime("%H:%M")
    now_date = datetime.now().strftime("%b %d")  # e.g. "Aug 25"
    draw.text((0, 0), now_date, font=font_small, fill=255)
    draw.text((64, 0), now_time, font=font_small, fill=255)

    # Divider line
    draw.line((0, 18, 128, 18), fill=255)

    # Forecast area
    draw.text((0, 26), f"High: {today_high}  Low: {tonight_low}", font=font_condensed, fill=255)
    draw.text((0, 46), f"Now: {current_temp}", font=font_medium, fill=255)

    disp.image(image)
    disp.show()

# ---------------- MAIN LOOP ---------------- #
try:
    while True:
        current_temp, today_high, tonight_low = fetch_weather()
        render_weather(current_temp, today_high, tonight_low)
        time.sleep(600)  # refresh every 10 min
except KeyboardInterrupt:
    disp.fill(0)
    disp.show()
    print("Exiting...")
