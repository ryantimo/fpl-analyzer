"""
api.py
Thin wrapper around the FPL public API.
"""

import time
import requests

BASE = "https://fantasy.premierleague.com/api"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}


def _get(url: str, **params) -> dict:
    r = requests.get(url, headers=HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def bootstrap() -> dict:
    return _get(f"{BASE}/bootstrap-static/")


def league_standings(league_id: int, page: int = 1) -> dict:
    return _get(f"{BASE}/leagues-classic/{league_id}/standings/", page_standings=page)


def all_league_teams(league_id: int) -> tuple[list, dict]:
    """Return (teams_list, league_meta). Handles pagination."""
    teams, page, league_info = [], 1, {}
    while True:
        data = league_standings(league_id, page)
        league_info = data["league"]
        teams.extend(data["standings"]["results"])
        if not data["standings"]["has_next"]:
            break
        page += 1
        time.sleep(0.3)
    return teams, league_info


def team_picks(team_id: int, gw: int) -> dict | None:
    try:
        return _get(f"{BASE}/entry/{team_id}/event/{gw}/picks/")
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return None
        raise


def team_transfers(team_id: int) -> list:
    return _get(f"{BASE}/entry/{team_id}/transfers/")


def live_gw_points(gw: int) -> dict:
    """Live player points for a given gameweek."""
    return _get(f"{BASE}/event/{gw}/live/")


def fixtures() -> list:
    """All fixtures for the season (finished and upcoming)."""
    return _get(f"{BASE}/fixtures/")
