#!/usr/bin/env python3
import requests
from datetime import datetime, timedelta
import pytz

# --- CONFIG ---
TIMEZONE = "America/Los_Angeles"
NUM_DAYS = 8
PRIORITY_TEAMS = ["Steelers", "Broncos"]
# ----------------

def fetch_nfl_schedule():
    """Fetch upcoming NFL games over the next NUM_DAYS, return list of strings."""
    today = datetime.utcnow()
    end_date = today + timedelta(days=NUM_DAYS)
    start_str = today.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={start_str}-{end_str}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch NFL schedule: {e}")
        return []

    games = []
    for event in data.get("events", []):
        game_dt_str = event.get("date")
        if not game_dt_str:
            continue

        game_dt = datetime.fromisoformat(game_dt_str.replace("Z", "+00:00"))
        local_dt = game_dt.astimezone(pytz.timezone(TIMEZONE))

        comp = event.get("competitions", [])[0] if event.get("competitions") else None
        if not comp:
            continue
        competitors = comp.get("competitors", [])
        if len(competitors) != 2:
            continue

        home = next((c for c in competitors if c["homeAway"] == "home"), None)
        away = next((c for c in competitors if c["homeAway"] == "away"), None)
        if not home or not away:
            continue

        # Broadcast info
        broadcasts = comp.get("broadcasts", [])
        network_names = [b.get("names", ["TBD"])[0] for b in broadcasts if b.get("names")]
        network_str = ", ".join(network_names) if network_names else "TBD"

        # Priority teams bolded
        home_name = f"*{home['team']['shortDisplayName']}*" if home['team']['shortDisplayName'] in PRIORITY_TEAMS else home['team']['shortDisplayName']
        away_name = f"*{away['team']['shortDisplayName']}*" if away['team']['shortDisplayName'] in PRIORITY_TEAMS else away['team']['shortDisplayName']

        day_time = local_dt.strftime("%a %m/%d %I:%M %p")
        line = f"{day_time}: {away_name} at {home_name} ({network_str})"

        # Mark if priority team involved
        is_priority = any(team in [home['team']['shortDisplayName'], away['team']['shortDisplayName']] for team in PRIORITY_TEAMS)
        games.append((is_priority, line))

    # Sort priority games first and return only strings
    games.sort(key=lambda x: not x[0])
    return [line for _, line in games]


if __name__ == "__main__":
    for g in fetch_nfl_schedule():
        print(g)
