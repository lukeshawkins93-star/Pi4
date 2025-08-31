#!/usr/bin/env python3

import requests
from datetime import datetime
import sys
from sendtelegrammessage import send_message

def fetch_json(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None

def get_station_info():
    # Beaverton, OR coordinates approx 45.48, -122.81
    point_url = "https://api.weather.gov/points/45.48,-122.81"
    data = fetch_json(point_url)
    if not data:
        return None, None, None
    properties = data.get("properties", {})
    forecast_url = properties.get("forecast")
    forecast_hourly_url = properties.get("forecastHourly")
    alerts_url = properties.get("alerts")
    return forecast_url, forecast_hourly_url, alerts_url

def get_alerts(alerts_url):
    if not alerts_url:
        return "No alerts URL available."
    data = fetch_json(alerts_url)
    if not data or "features" not in data:
        return "No alerts data found."
    alerts = data["features"]
    if not alerts:
        return "No active alerts for your area."
    alert_msgs = []
    for alert in alerts:
        props = alert.get("properties", {})
        event = props.get("event", "Unknown Event")
        headline = props.get("headline", "")
        desc = props.get("description", "")
        alert_msgs.append(f"{event}:\n{headline}\n{desc}")
    return "\n\n".join(alert_msgs)

def get_hourly_forecast(forecast_hourly_url):
    if not forecast_hourly_url:
        return "No hourly forecast URL available."
    data = fetch_json(forecast_hourly_url)
    if not data or "properties" not in data:
        return "No hourly forecast data found."
    periods = data["properties"].get("periods", [])
    # Get next 12 hours
    next_12_hours = periods[:12]
    lines = []
    for p in next_12_hours:
        time = p.get("startTime", "unknown time")
        temp = p.get("temperature", "N/A")
        temp_unit = p.get("temperatureUnit", "")
        wind_gust = p.get("windSpeed", "N/A")  # windSpeed includes gusts usually, but NOAA API varies
        short_forecast = p.get("shortForecast", "")
        lines.append(f"{time[:16]}: {temp} {temp_unit}, Wind: {wind_gust}, {short_forecast}")
    return "\n".join(lines)

def get_text_forecast(forecast_url):
    if not forecast_url:
        return "No text forecast URL available."
    data = fetch_json(forecast_url)
    if not data or "properties" not in data:
        return "No text forecast data found."
    periods = data["properties"].get("periods", [])
    # Get next 5 periods
    next_periods = periods[:14]
    lines = []
    for p in next_periods:
        name = p.get("name", "")
        detailed_forecast = p.get("detailedForecast", "")
        lines.append(f"{name}:\n{detailed_forecast}")
    return "\n\n".join(lines)

def main():
    forecast_url, forecast_hourly_url, alerts_url = get_station_info()
    if not any([forecast_url, forecast_hourly_url, alerts_url]):
        send_message("Error: Could not get weather data URLs from NOAA for Beaverton, OR.")
        return

    alerts_text = get_alerts(alerts_url)
    hourly_text = get_hourly_forecast(forecast_hourly_url)
    text_forecast = get_text_forecast(forecast_url)

    message = f"NOAA Weather Report for Beaverton, OR\n\n"
    message += f"=== Alerts ===\n{alerts_text}\n\n"
    message += f"=== Hourly Forecast (Next 12 Hours) ===\n{hourly_text}\n\n"
    message += f"=== Text Forecast (Next 5 Periods) ===\n{text_forecast}\n\n"
    message += f"Report generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    send_message(message)
    print(message)

if __name__ == "__main__":
    main()
