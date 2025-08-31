import requests
from datetime import datetime, date
import math

LAT = 45.4800
LON = -122.8074

def get_closest_stations(lat, lon, max_stations=3):
    url = f"https://api.weather.gov/points/{lat},{lon}/stations"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    stations = data.get('features', [])
    return stations[:max_stations]

def get_latest_station_gust(station_id):
    url = f"https://api.weather.gov/stations/{station_id}/observations/latest"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        gust_mps = data['properties'].get('windGust', {}).get('value')
        if gust_mps is not None:
            # Convert m/s to mph
            gust_mph = gust_mps * 2.23694
            return round(gust_mph, 1)
    except Exception as e:
        print(f"Error fetching data for station {station_id}: {e}")
    return None

def get_forecast_gridpoint(lat, lon):
    url = f"https://api.weather.gov/points/{lat},{lon}"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    props = data.get('properties', {})
    office = props.get('gridId')
    gridX = props.get('gridX')
    gridY = props.get('gridY')
    if office and gridX is not None and gridY is not None:
        return office, gridX, gridY
    return None, None, None

def get_forecast_gusts(office, gridX, gridY):
    url = f"https://api.weather.gov/gridpoints/{office}/{gridX},{gridY}/forecast"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    periods = data.get('properties', {}).get('periods', [])
    
    # Collect gusts for next 10 days (assuming each period is ~12 hrs)
    forecast_gusts = {}
    for p in periods:
        date_str = p.get('startTime', '')[:10]
        gust_info = p.get('windGust')
        gust_value = None
        if gust_info:
            # windGust example: "20 mph"
            gust_text = gust_info
            # Parse mph number
            try:
                gust_value = int(gust_text.split()[0])
            except Exception:
                gust_value = None
        # Store max gust per day
        if date_str:
            if date_str not in forecast_gusts or (gust_value and gust_value > forecast_gusts[date_str]):
                forecast_gusts[date_str] = gust_value
    
    # Fill missing days with None, limit to next 10 days
    today = date.today()
    next_10_days = [(today.replace(day=today.day+i)).isoformat() for i in range(1, 11)]
    result = {d: forecast_gusts.get(d, None) for d in next_10_days}
    return result

def main():
    print(f"Fetching stations near {LAT}, {LON} ...")
    stations = get_closest_stations(LAT, LON)
    print(f"Using {len(stations)} closest stations:")
    for s in stations:
        print(f"- {s['properties']['name']} ({s['properties']['stationIdentifier']})")
    
    gusts = []
    for s in stations:
        station_id = s['properties']['stationIdentifier']
        gust = get_latest_station_gust(station_id)
        if gust is not None:
            gusts.append(gust)
    if gusts:
        peak_gust_today = max(gusts)
        print(f"Peak wind gust today from nearby stations: {peak_gust_today} mph")
    else:
        print("No wind gust data available from nearby stations today.")
    
    office, gridX, gridY = get_forecast_gridpoint(LAT, LON)
    if not office:
        print("Could not determine forecast gridpoint.")
        return
    
    print(f"Fetching forecast gusts from gridpoint {office} {gridX},{gridY} ...")
    forecast_gusts = get_forecast_gusts(office, gridX, gridY)
    
    print("\nNext 10 days peak wind gust forecast:")
    for day, gust in forecast_gusts.items():
        if gust is not None:
            print(f"{day}: {gust} mph")
        else:
            print(f"{day}: No data")

if __name__ == "__main__":
    main()
