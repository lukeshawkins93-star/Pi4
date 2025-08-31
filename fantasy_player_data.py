import requests

season = 2024  # change when next season's data exists
adp_url = f"https://api.sleeper.app/v1/adp/nfl/{season}?season_type=regular&scoring=PPR"
r = requests.get(adp_url)

if r.status_code != 200:
    print("Error fetching ADP:", r.status_code, r.text)
else:
    adp_data = r.json()
    print(adp_data)