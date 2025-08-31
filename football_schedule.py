#!/usr/bin/env python3
import requests
from datetime import datetime, timedelta

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

def fetch_nfl_schedule():
    """Fetch NFL games for the next 8 days using ESPN API."""
    today = datetime.utcnow().date()
    end_date = today + timedelta(days=8)
    date_str = f"{today.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"
    params = {"dates": date_str, "limit": 2000}

    try:
        resp = requests.get(ESPN_SCOREBOARD, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[ERROR] Fetching NFL schedule failed: {e}")
        return []

    games = []
    for event in data.get("events", []):
        date = event.get("date", "")
        competitions = event.get("competitions", [])
        if not competitions:
            continue
        comp = competitions[0]
        away = comp["competitors"][0]["team"]["shortDisplayName"]
        home = comp["competitors"][1]["team"]["shortDisplayName"]
        network = comp.get("broadcasts", [])
        network_name = network[0]["media"]["shortName"] if network else "TBD"
        games.append({
            "datetime": date,
            "away": away,
            "home": home,
            "network": network_name
        })
    return games

def format_games(games):
    """Format the list of games into a human-readable string."""
    if not games:
        return "No games found."
    lines = []
    for g in games:
        dt = datetime.fromisoformat(g["datetime"].replace("Z", "+00:00"))
        lines.append(f"{dt.strftime('%Y-%m-%d %H:%M')} UTC — {g['away']} @ {g['home']} | {g['network']}")
    return "\n".join(lines)

if __name__ == "__main__":
    games = fetch_nfl_schedule()
    print(format_games(games))
