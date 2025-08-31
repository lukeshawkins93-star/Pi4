#!/usr/bin/env python3
import requests
from datetime import datetime, timedelta
from sendtelegrammessage import send_message  # your existing method

LAT = 45.48
LON = -122.81
RAIN_THRESHOLD = 75  # percent
WIND_THRESHOLD = 25  # mph

def fetch_alerts(lat, lon):
    url = f"https://api.weather.gov/alerts/active?point={lat},{lon}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("features", [])
    except Exception as e:
        print(f"Error fetching alerts: {e}")
        return []

def fetch_hourly_forecast(lat, lon):
    try:
        r = requests.get(f"https://api.weather.gov/points/{lat},{lon}", timeout=10)
        r.raise_for_status()
        point_data = r.json()
        forecast_hourly_url = point_data['properties'].get('forecastHourly')
        if not forecast_hourly_url:
            return []
        r2 = requests.get(forecast_hourly_url, timeout=10)
        r2.raise_for_status()
        return r2.json().get("properties", {}).get("periods", [])
    except Exception as e:
        print(f"Error fetching hourly forecast: {e}")
        return []

def format_alerts(alerts):
    lines = []
    for alert in alerts:
        props = alert.get("properties", {})
        event = props.get("event", "Unknown Event")
        headline = props.get("headline", "")
        description = props.get("description", "")
        lines.append(f"{event}:\n{headline}\n{description}\n")
    return "\n".join(lines)

def check_rain_next_hour(hourly_forecast):
    now = datetime.utcnow()
    one_hour_later = now + timedelta(hours=1)
    for period in hourly_forecast:
        start_time = period.get("startTime")
        if not start_time:
            continue
        period_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if now <= period_time <= one_hour_later:
            pop = period.get("probabilityOfPrecipitation", {}).get("value", 0)
            if pop and pop >= RAIN_THRESHOLD:
                return pop, period.get("shortForecast", "")
    return None, None

def check_wind_next_hours(hourly_forecast, hours=8):
    now = datetime.utcnow()
    end_time = now + timedelta(hours=hours)
    gusts_over_threshold = []
    for period in hourly_forecast:
        start_time = period.get("startTime")
        if not start_time:
            continue
        period_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if now <= period_time <= end_time:
            wind_gust_str = period.get("windSpeed", "")
            # Extract numeric mph value if present
            try:
                gust_value = max([int(s) for s in wind_gust_str.split() if s.isdigit()])
            except Exception:
                gust_value = 0
            if gust_value >= WIND_THRESHOLD:
                gusts_over_threshold.append((gust_value, period.get("shortForecast", ""), period_time))
    return gusts_over_threshold

def main():
    now = datetime.now()
    alerts = fetch_alerts(LAT, LON)
    hourly_forecast = fetch_hourly_forecast(LAT, LON)

    rain_pop, rain_forecast = check_rain_next_hour(hourly_forecast)
    strong_winds = check_wind_next_hours(hourly_forecast, 8)

    send_anyway = now.hour == 7 and now.minute == 0  # 7:00 AM message
    if not alerts and rain_pop is None and not strong_winds and not send_anyway:
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] No alerts, rain, or strong winds; skipping message.")
        return

    message = f"Weather Report for your area ({now.strftime('%Y-%m-%d %H:%M:%S')}):\n\n"

    if alerts:
        message += format_alerts(alerts)
    else:
        message += "No active alerts.\n"

    if rain_pop is not None:
        message += f"\n🌧 High chance of rain in the next hour: {rain_pop}% ({rain_forecast})\n"

    if strong_winds:
        message += "\n💨 Strong winds expected in the next 8 hours:\n"
        for gust_value, short_forecast, period_time in strong_winds:
            local_time = period_time.strftime("%Y-%m-%d %H:%M UTC")
            message += f"- {local_time}: gusts {gust_value} mph, {short_forecast}\n"

    send_message(message)
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Message sent.")

if __name__ == "__main__":
    main()
