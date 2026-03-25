"""
analysis.py
Pure data-processing functions — no Streamlit imports.
"""

from collections import defaultdict
import pandas as pd


def current_gw(bootstrap: dict) -> int:
    for e in bootstrap["events"]:
        if e["is_current"]:
            return e["id"]
    for e in reversed(bootstrap["events"]):
        if e["finished"]:
            return e["id"]
    return 1


def player_map(bootstrap: dict, live: dict | None = None) -> dict:
    """
    Returns {player_id: {...}} with name, team, position, price, form,
    global ownership %, and live GW points (if available).
    """
    teams = {t["id"]: t["short_name"] for t in bootstrap["teams"]}
    pos = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}

    live_pts = {}
    if live:
        live_pts = {
            el["id"]: el["stats"]["total_points"]
            for el in live["elements"]
        }

    return {
        p["id"]: {
            "name": p["web_name"],
            "full_name": f"{p['first_name']} {p['second_name']}",
            "team": teams[p["team"]],
            "position": pos[p["element_type"]],
            "price": p["now_cost"] / 10,
            "form": float(p["form"] or 0),
            "global_own_pct": float(p["selected_by_percent"] or 0),
            "gw_pts": live_pts.get(p["id"], p["event_points"] or 0),
        }
        for p in bootstrap["elements"]
    }


# ── Standings ──────────────────────────────────────────────────────────────────

def build_standings(teams: list, picks_map: dict) -> pd.DataFrame:
    """
    teams: raw league standings list
    picks_map: {team_id: picks_data}
    """
    rows = []
    for t in teams:
        tid = t["entry"]
        picks = picks_map.get(tid)
        gw_pts = picks["entry_history"]["points"] if picks else None
        tc = picks["entry_history"]["event_transfers_cost"] if picks else 0
        chip = picks.get("active_chip") if picks else None

        rows.append({
            "Rank": t["rank"],
            "Manager": t["player_name"],
            "Team": t["entry_name"],
            "GW pts": gw_pts,
            "Transfer cost": f"-{tc}" if tc else "0",
            "Chip": chip or "–",
            "Total": t["total"],
            "entry": tid,
        })

    df = pd.DataFrame(rows).sort_values("Rank").reset_index(drop=True)
    leader = df["Total"].max()
    df["Gap"] = df["Total"].apply(lambda x: f"-{leader - x}" if x < leader else "–")
    return df


# ── Captains ──────────────────────────────────────────────────────────────────

def build_captain_table(teams: list, picks_map: dict, pmap: dict) -> pd.DataFrame:
    captain_counts: dict[int, int] = defaultdict(int)
    vc_counts: dict[int, int] = defaultdict(int)
    n = 0

    for t in teams:
        picks = picks_map.get(t["entry"])
        if not picks:
            continue
        n += 1
        for p in picks["picks"]:
            if p["is_captain"]:
                captain_counts[p["element"]] += 1
            if p["is_vice_captain"]:
                vc_counts[p["element"]] += 1

    if n == 0:
        return pd.DataFrame()

    rows = []
    for pid, cnt in sorted(captain_counts.items(), key=lambda x: -x[1]):
        info = pmap.get(pid, {})
        gw_pts = info.get("gw_pts", 0)
        rows.append({
            "Player": info.get("name", "?"),
            "Team": info.get("team", "?"),
            "Position": info.get("position", "?"),
            "Captained by": cnt,
            "% of league": round(cnt / n * 100, 1),
            "GW pts": gw_pts,
            "Captain pts": gw_pts * 2,
            "VC count": vc_counts.get(pid, 0),
        })

    return pd.DataFrame(rows)


# ── Ownership ─────────────────────────────────────────────────────────────────

def build_ownership_table(teams: list, picks_map: dict, pmap: dict) -> pd.DataFrame:
    own_counts: dict[int, int] = defaultdict(int)
    n = sum(1 for t in teams if picks_map.get(t["entry"]))

    for t in teams:
        picks = picks_map.get(t["entry"])
        if not picks:
            continue
        for p in picks["picks"]:
            own_counts[p["element"]] += 1

    rows = []
    for pid, cnt in sorted(own_counts.items(), key=lambda x: -x[1]):
        info = pmap.get(pid, {})
        rows.append({
            "Player": info.get("name", "?"),
            "Team": info.get("team", "?"),
            "Position": info.get("position", "?"),
            "Price": f"£{info.get('price', 0):.1f}m",
            "Owned by (league)": cnt,
            "% league": round(cnt / n * 100, 1),
            "% global": info.get("global_own_pct", 0),
            "Form": info.get("form", 0),
            "GW pts": info.get("gw_pts", 0),
        })

    return pd.DataFrame(rows)


# ── Differentials ─────────────────────────────────────────────────────────────

def build_differentials(
    ownership_df: pd.DataFrame,
    max_league_own_pct: float = 50.0,
) -> pd.DataFrame:
    """
    Players owned by SOME (but < max_league_own_pct %) of your league.
    Sorted by GW pts desc — these are the ones that hurt you most this week.
    """
    df = ownership_df[
        (ownership_df["% league"] > 0) &
        (ownership_df["% league"] < max_league_own_pct)
    ].copy()
    df = df.sort_values("GW pts", ascending=False).reset_index(drop=True)
    df["Danger"] = df["GW pts"].apply(
        lambda pts: "🔴 High" if pts >= 10 else ("🟡 Medium" if pts >= 6 else "🟢 Low")
    )
    return df


# ── Transfers ─────────────────────────────────────────────────────────────────

def build_transfers_table(
    teams: list,
    transfers_map: dict,
    pmap: dict,
    gw: int,
) -> pd.DataFrame:
    rows = []
    for t in teams:
        gw_transfers = [
            tr for tr in transfers_map.get(t["entry"], [])
            if tr["event"] == gw
        ]
        for tr in gw_transfers:
            p_in = pmap.get(tr["element_in"], {})
            p_out = pmap.get(tr["element_out"], {})
            rows.append({
                "Manager": t["player_name"],
                "Team": t["entry_name"],
                "OUT": p_out.get("name", "?"),
                "OUT pts": p_out.get("gw_pts", 0),
                "IN": p_in.get("name", "?"),
                "IN pts": p_in.get("gw_pts", 0),
                "Net pts": p_in.get("gw_pts", 0) - p_out.get("gw_pts", 0),
            })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).sort_values("Net pts", ascending=False).reset_index(drop=True)
    df["Result"] = df["Net pts"].apply(
        lambda x: "✅ Good" if x > 0 else ("➖ Break even" if x == 0 else "❌ Bad")
    )
    return df
