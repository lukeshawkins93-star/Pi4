#!/usr/bin/env python3
import requests
from datetime import datetime

STEELERS_ID = 25  # ESPN team ID for Steelers

def fetch_json(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
        return None

def get_steelers_live_game():
    """Return the live or in-progress Steelers game, if any."""
    today = datetime.utcnow().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{STEELERS_ID}/schedule?dates={today}-{today}"
    data = fetch_json(url)
    if not data or "events" not in data:
        return None
    for event in data["events"]:
        status = event.get("status", {}).get("type", {}).get("name", "")
        if status in ("STATUS_IN_PROGRESS", "STATUS_FINAL"):
            return event
    return None

def display_player_stats(game):
    if not game:
        return "No Steelers game in progress right now."

    comp = game.get("competitions", [])[0]
    competitors = comp.get("competitors", [])
    stats_text = ""

    for competitor in competitors:
        team_name = competitor["team"]["shortDisplayName"]
        stats_text += f"\n=== {team_name} Stats ===\n"
        leaders = competitor.get("leaders", [])
        if not leaders:
            stats_text += "No player stats available.\n"
            continue
        for stat in leaders:
            athlete = stat.get("athlete", {}).get("displayName", "Unknown Player")
            label = stat.get("displayName", "")
            value = stat.get("value", "")
            stats_text += f"{athlete} – {label}: {value}\n"

    return stats_text

if __name__ == "__main__":
    game = get_steelers_live_game()
    stats_report = display_player_stats(game)
    print(stats_report)
