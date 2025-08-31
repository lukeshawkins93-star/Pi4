#!/usr/bin/env python3
import requests
from datetime import datetime

def fetch_json(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
        return None

def get_scoreboard():
    today = datetime.utcnow().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={today}"
    data = fetch_json(url)
    if not data or "events" not in data:
        return "No games found for today."

    messages = []
    for event in data["events"]:
        comp = event.get("competitions", [])[0]
        competitors = comp.get("competitors", [])
        if len(competitors) != 2:
            continue

        home = next(c for c in competitors if c["homeAway"] == "home")
        away = next(c for c in competitors if c["homeAway"] == "away")

        home_name = home["team"]["shortDisplayName"]
        away_name = away["team"]["shortDisplayName"]
        home_score = home.get("score", "0")
        away_score = away.get("score", "0")
        status = comp.get("status", {}).get("type", {}).get("description", "Unknown")

        messages.append(f"{away_name} @ {home_name}\nScore: {away_score} – {home_score}\nStatus: {status}\n")

    return "\n".join(messages) if messages else "No NFL games today."

if __name__ == "__main__":
    print(get_scoreboard())
