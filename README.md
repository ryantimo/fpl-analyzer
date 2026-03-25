# FPL League Analyzer ⚽

Live gameweek analysis for your FPL mini-league — captain %, ownership, differentials, and transfers.

## Features

| Tab | What it shows |
|-----|---------------|
| 📊 Standings | GW points, total, gap to leader, chip used |
| 🎖️ Captains | Who captained who, % breakdown, pts scored, donut chart |
| 👥 Ownership | Every player owned in the league, % owned vs global % |
| ⚠️ Differentials | Players owned by <50% of league — sorted by GW pts (the ones hurting you) |
| 🔄 Transfers | Every GW transfer, IN vs OUT pts, good/bad verdict |

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app defaults to league `1519916`. Override with an env var:

```bash
LEAGUE_ID=123456 streamlit run app.py
```

## Deploy to Streamlit Cloud (free)

1. Push this repo to GitHub (already done)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub account → select this repo → set main file to `app.py`
4. Add `LEAGUE_ID = 1519916` in **Secrets** (Settings → Secrets)
5. Deploy — you get a public URL, updates live every time you push

## Updating each gameweek

The app fetches live data from the FPL API automatically. Just open it after the gameweek deadline and hit **🔄 Refresh data** in the sidebar. No code changes needed week-to-week.

## Tech

- **Streamlit** — UI framework
- **FPL public API** — `fantasy.premierleague.com/api`
- **Plotly** — charts
- **pandas** — data wrangling
