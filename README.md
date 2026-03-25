# FPL League Analyzer ⚽

Live gameweek analysis for your FPL mini-league — standings, rankings chart, captain %, ownership, differentials, transfers, and fixture-based forecasting.

## Tabs

| Tab | What it shows |
|-----|---------------|
| 📊 Standings | GW points, total, gap to leader, chip used, points bar chart |
| 📈 Rankings | Points trajectory — last 5 GWs solid + next 5 GWs projected (dotted). Top 9 highlighted with thicker lines, gold cut-off line, projected final standings table |
| 🎖️ Captains | Who captained who, % breakdown, pts scored ×2, donut chart, per-manager breakdown |
| 👥 Ownership | Every player owned in the league, % owned vs global %, filter by position |
| ⚠️ Differentials | Players owned by <50% of league, sorted by GW pts — the ones hurting you this week |
| 🔄 Transfers | Every GW transfer, IN vs OUT pts, ✅/❌ verdict, net pts chart |
| 🔮 Forecast | Fixture ticker (FPL colours, DGW aware), squad projections for next 3 GWs, transfer targets by ep_next |

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Override the league ID with an env var:

```bash
LEAGUE_ID=123456 streamlit run app.py
```

## Deploy to Streamlit Cloud (free)

1. Go to [share.streamlit.io](https://share.streamlit.io) and connect your GitHub account
2. Select this repo, set main file to `app.py`
3. Add `LEAGUE_ID = 1519916` in **Settings → Secrets**
4. Deploy — you get a public URL that auto-updates every push

## Updating each gameweek

No code changes needed. The app pulls live data from the FPL API on every load. Hit **🔄 Refresh data** in the sidebar after each gameweek deadline to clear the 5-minute cache.

## How the forecast works

- **GW+1 projection** — uses FPL's own `ep_next` (expected points) per player, captain ×2 applied
- **GW+2–5 projection** — player form × fixture difficulty multiplier `(6 − FDR) / 5`
- **Fixture ticker** — FDR colours match the official FPL site (dark green → dark red), double gameweeks flagged automatically

## Tech

- **Streamlit** — UI
- **FPL public API** — `fantasy.premierleague.com/api`
- **Plotly** — interactive charts (px + graph_objects)
- **pandas** — data wrangling
