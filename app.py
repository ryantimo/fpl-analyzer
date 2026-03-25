"""
FPL League Analyzer
Run: streamlit run app.py
"""

import os
import time
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import fpl.api as api
from fpl.analysis import (
    current_gw,
    player_map,
    build_standings,
    build_captain_table,
    build_ownership_table,
    build_differentials,
    build_transfers_table,
    build_fixture_ticker,
    build_squad_forecast,
    build_transfer_targets,
    build_rankings_chart_data,
    FDR_COLORS,
    FDR_TEXT,
)

LEAGUE_ID = int(os.getenv("LEAGUE_ID", "1519916"))
DIFF_THRESHOLD = 50.0  # players owned by < this % of league = differential

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="FPL League Analyzer",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .metric-card { background:#1e2130; border-radius:8px; padding:12px 16px; margin:4px 0; }
    .danger-high  { color:#ff4b4b; font-weight:600; }
    .danger-mid   { color:#ffa500; font-weight:600; }
    .danger-low   { color:#21c55d; font-weight:600; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚽ FPL Analyzer")
    league_id = st.number_input("League ID", value=LEAGUE_ID, step=1, format="%d")
    diff_pct = st.slider("Differential threshold (%)", 10, 80, 50, 5,
                         help="Players owned by fewer than this % of your league")
    refresh = st.button("🔄 Refresh data", use_container_width=True)
    if refresh:
        st.cache_data.clear()
    st.caption("Data cached for 5 minutes. Hit Refresh after gameweek deadline.")


# ── Data fetching (cached) ────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def load_data(league_id: int, gw: int):
    boot = api.bootstrap()
    teams, league_info = api.all_league_teams(league_id)
    live = api.live_gw_points(gw)
    all_fixtures = api.fixtures()
    pmap = player_map(boot, live)

    picks_map, transfers_map, histories_map = {}, {}, {}
    for t in teams:
        tid = t["entry"]
        picks_map[tid]    = api.team_picks(tid, gw)
        transfers_map[tid] = api.team_transfers(tid)
        histories_map[tid] = api.team_history(tid)
        time.sleep(0.08)  # be polite to the FPL API

    return boot, teams, league_info, pmap, picks_map, transfers_map, all_fixtures, histories_map


# ── GW picker (needs bootstrap first) ────────────────────────────────────────

try:
    with st.spinner("Loading FPL data…"):
        boot_quick = api.bootstrap()
    gw_options = [e["id"] for e in boot_quick["events"] if e["finished"] or e["is_current"]]
    default_gw = current_gw(boot_quick)
except Exception as e:
    st.error(f"Could not reach FPL API: {e}")
    st.stop()

with st.sidebar:
    selected_gw = st.selectbox(
        "Gameweek", options=gw_options[::-1], index=0,
        format_func=lambda x: f"GW {x}"
    )

# ── Main load ─────────────────────────────────────────────────────────────────

try:
    with st.spinner(f"Fetching GW{selected_gw} data for all managers…"):
        boot, teams, league_info, pmap, picks_map, transfers_map, all_fixtures, histories_map = load_data(
            int(league_id), selected_gw
        )
except Exception as e:
    st.error(f"Failed to load data: {e}")
    st.stop()

n_teams = len(teams)

# ── Header ────────────────────────────────────────────────────────────────────

col_title, col_meta = st.columns([3, 1])
with col_title:
    st.title(f"⚽ {league_info['name']}")
    st.caption(f"Gameweek {selected_gw}  •  {n_teams} managers")
with col_meta:
    avg_pts = (
        sum(p["entry_history"]["points"] for p in picks_map.values() if p) / n_teams
        if n_teams else 0
    )
    st.metric("Avg GW score", f"{avg_pts:.0f} pts")

st.divider()

# ── Build tables ──────────────────────────────────────────────────────────────

standings_df = build_standings(teams, picks_map)
captain_df   = build_captain_table(teams, picks_map, pmap)
ownership_df = build_ownership_table(teams, picks_map, pmap)
diff_df      = build_differentials(ownership_df, max_league_own_pct=diff_pct)
transfers_df = build_transfers_table(teams, transfers_map, pmap, selected_gw)

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_stand, tab_rank, tab_cap, tab_own, tab_diff, tab_trans, tab_fore = st.tabs([
    "📊 Standings",
    "📈 Rankings",
    "🎖️ Captains",
    "👥 Ownership",
    "⚠️ Differentials",
    "🔄 Transfers",
    "🔮 Forecast",
])

# ─── Standings ────────────────────────────────────────────────────────────────
with tab_stand:
    st.subheader(f"GW{selected_gw} Standings")

    # Top 3 cards
    top3 = standings_df.head(3)
    cols = st.columns(3)
    medals = ["🥇", "🥈", "🥉"]
    for col, (_, row), medal in zip(cols, top3.iterrows(), medals):
        with col:
            st.metric(
                label=f"{medal} {row['Manager']}",
                value=f"{row['Total']} pts",
                delta=f"GW: {row['GW pts']} pts",
            )

    st.dataframe(
        standings_df.drop(columns=["entry"]),
        use_container_width=True,
        hide_index=True,
    )

    # GW points bar chart
    if not standings_df.empty and standings_df["GW pts"].notna().any():
        fig = px.bar(
            standings_df.sort_values("GW pts", ascending=True),
            x="GW pts", y="Manager",
            orientation="h",
            color="GW pts",
            color_continuous_scale="Blues",
            title=f"GW{selected_gw} Points by Manager",
            text="GW pts",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False, coloraxis_showscale=False,
                          yaxis_title="", height=max(300, n_teams * 28))
        st.plotly_chart(fig, use_container_width=True)


# ─── Rankings ─────────────────────────────────────────────────────────────────
with tab_rank:
    st.subheader("📈 Points trajectory — last 5 GWs + 5 GW projection")
    st.caption(
        "Solid lines = actual points. Dotted lines = projected. "
        "⭐ Top 9 are highlighted with thicker lines. "
        "Gold dashed line = top 9 cut-off at current GW."
    )

    chart_df = build_rankings_chart_data(
        teams, histories_map, picks_map, pmap, all_fixtures,
        current_gw_num=selected_gw, gws_back=5, gws_ahead=5, top_n=20,
    )

    if chart_df.empty:
        st.info("No historical data available yet.")
    else:
        colors = px.colors.qualitative.Dark24
        managers_by_rank = (
            chart_df[["Manager", "rank"]]
            .drop_duplicates()
            .sort_values("rank")["Manager"]
            .tolist()
        )
        color_map = {m: colors[i % len(colors)] for i, m in enumerate(managers_by_rank)}

        fig = go.Figure()

        # Shaded projected zone
        proj_gws = chart_df[chart_df["is_projected"]]["GW"]
        if not proj_gws.empty:
            fig.add_vrect(
                x0=proj_gws.min() - 0.5,
                x1=proj_gws.max() + 0.5,
                fillcolor="rgba(255,255,255,0.03)",
                line_width=0,
            )
            fig.add_annotation(
                x=proj_gws.min(), y=1, yref="paper",
                text="◀ Actual  |  Projected ▶",
                showarrow=False, font=dict(size=11, color="rgba(255,255,255,0.4)"),
                xanchor="center",
            )

        for manager in managers_by_rank:
            mdf = chart_df[chart_df["Manager"] == manager].sort_values("GW")
            rank = int(mdf["rank"].iloc[0])
            color = color_map[manager]
            lw = 3.0 if rank <= 9 else 1.4
            opacity = 1.0 if rank <= 9 else 0.6
            label = f"{'⭐ ' if rank <= 9 else ''}#{rank} {manager}"

            hist_df = mdf[~mdf["is_projected"]]
            proj_df = mdf[mdf["is_projected"]]

            # Historical — solid
            if not hist_df.empty:
                fig.add_trace(go.Scatter(
                    x=hist_df["GW"], y=hist_df["Total"],
                    name=label,
                    line=dict(color=color, width=lw),
                    opacity=opacity,
                    mode="lines",
                    legendgroup=manager,
                    hovertemplate=f"<b>{manager}</b> GW%{{x}}<br>%{{y:.0f}} pts<extra></extra>",
                ))

            # Projected — dotted, connected from last real point
            if not proj_df.empty:
                connect = pd.concat([hist_df.tail(1), proj_df])
                fig.add_trace(go.Scatter(
                    x=connect["GW"], y=connect["Total"],
                    name=label,
                    line=dict(color=color, width=lw, dash="dot"),
                    opacity=opacity * 0.75,
                    mode="lines+markers",
                    marker=dict(size=5, symbol="circle-open"),
                    legendgroup=manager,
                    showlegend=False,
                    hovertemplate=f"<b>{manager}</b> GW%{{x}} (proj)<br>%{{y:.0f}} pts<extra></extra>",
                ))

            # End-of-projection label
            if not proj_df.empty:
                last = proj_df.iloc[-1]
                fig.add_annotation(
                    x=last["GW"] + 0.15, y=last["Total"],
                    text=f"<b>{manager}</b>" if rank <= 9 else manager,
                    showarrow=False, xanchor="left",
                    font=dict(size=9 if rank > 9 else 10, color=color),
                )

        # Vertical "now" line
        fig.add_vline(
            x=selected_gw + 0.5,
            line_dash="dash",
            line_color="rgba(255,255,255,0.25)",
        )

        # Top-9 cut-off: gold horizontal line at rank-9 current total
        rank9_rows = chart_df[(chart_df["rank"] == 9) & (~chart_df["is_projected"])]
        if not rank9_rows.empty:
            y9 = rank9_rows.sort_values("GW").iloc[-1]["Total"]
            fig.add_hline(
                y=y9,
                line_dash="dot", line_color="gold", line_width=1.5,
                annotation_text=f"Top 9 cut ({y9:.0f})",
                annotation_position="right",
                annotation_font=dict(color="gold", size=11),
            )

        fig.update_layout(
            xaxis=dict(
                title="Gameweek",
                tickmode="linear", dtick=1,
                showgrid=True, gridcolor="rgba(255,255,255,0.08)",
            ),
            yaxis=dict(
                title="Total Points",
                showgrid=True, gridcolor="rgba(255,255,255,0.08)",
            ),
            legend=dict(
                orientation="v", yanchor="top", y=1, xanchor="left", x=1.01,
                font=dict(size=11),
            ),
            hovermode="x unified",
            height=620,
            margin=dict(r=160),
            plot_bgcolor="rgba(14,17,23,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )

        st.plotly_chart(fig, use_container_width=True)

        # Projected final standings table
        st.subheader("Projected standings after 5 GWs")
        proj_final = (
            chart_df[chart_df["is_projected"]]
            .sort_values("GW")
            .groupby("Manager")
            .last()
            .reset_index()[["Manager", "Total", "rank"]]
            .sort_values("Total", ascending=False)
            .reset_index(drop=True)
        )
        proj_final.index += 1
        proj_final.columns = ["Manager", "Projected Total", "Current Rank"]
        proj_final.insert(0, "Proj Rank", proj_final.index)
        proj_final["Movement"] = proj_final.apply(
            lambda r: (
                f"▲ {int(r['Current Rank'] - r['Proj Rank'])}"
                if r["Current Rank"] > r["Proj Rank"]
                else (
                    f"▼ {int(r['Proj Rank'] - r['Current Rank'])}"
                    if r["Current Rank"] < r["Proj Rank"]
                    else "–"
                )
            ),
            axis=1,
        )
        st.dataframe(proj_final, use_container_width=True, hide_index=True)


# ─── Captains ─────────────────────────────────────────────────────────────────
with tab_cap:
    st.subheader(f"GW{selected_gw} Captain Choices")

    if captain_df.empty:
        st.info("No captain data available yet for this gameweek.")
    else:
        # Big stat: most popular captain
        top_cap = captain_df.iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Most captained", top_cap["Player"],
                  f"{top_cap['% of league']}% of league")
        c2.metric("Their GW pts", f"{top_cap['GW pts']} pts",
                  f"×2 = {top_cap['Captain pts']} for captains")
        unique = captain_df[captain_df["Captained by"] == 1].shape[0]
        c3.metric("Unique choices", unique, f"across {n_teams} managers")

        st.dataframe(captain_df, use_container_width=True, hide_index=True)

        # Donut chart
        fig = px.pie(
            captain_df[captain_df["Captained by"] > 0],
            values="Captained by",
            names="Player",
            title="Captain pick distribution",
            hole=0.45,
        )
        fig.update_traces(textinfo="label+percent")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        # Who picked which captain (detail)
        st.subheader("Captain picks per manager")
        cap_detail = []
        for t in teams:
            picks = picks_map.get(t["entry"])
            if not picks:
                continue
            for p in picks["picks"]:
                if p["is_captain"]:
                    info = pmap.get(p["element"], {})
                    cap_detail.append({
                        "Manager": t["player_name"],
                        "Team": t["entry_name"],
                        "Captain": info.get("name", "?"),
                        "GW pts": info.get("gw_pts", 0),
                        "Captain pts": info.get("gw_pts", 0) * 2,
                    })
        if cap_detail:
            detail_df = pd.DataFrame(cap_detail).sort_values(
                "Captain pts", ascending=False
            ).reset_index(drop=True)
            st.dataframe(detail_df, use_container_width=True, hide_index=True)


# ─── Ownership ────────────────────────────────────────────────────────────────
with tab_own:
    st.subheader(f"GW{selected_gw} Player Ownership in League")

    pos_filter = st.multiselect(
        "Filter by position",
        ["GKP", "DEF", "MID", "FWD"],
        default=["GKP", "DEF", "MID", "FWD"],
    )

    filtered_own = ownership_df[ownership_df["Position"].isin(pos_filter)]

    st.dataframe(filtered_own, use_container_width=True, hide_index=True)

    # Top 15 owned bar chart
    top15 = filtered_own.head(15)
    if not top15.empty:
        fig = px.bar(
            top15.sort_values("% league", ascending=True),
            x="% league", y="Player",
            orientation="h",
            color="Position",
            title="Top 15 most-owned players (% of league)",
            text="% league",
        )
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        fig.update_layout(yaxis_title="", xaxis_title="% owned in league",
                          height=450)
        st.plotly_chart(fig, use_container_width=True)


# ─── Differentials ────────────────────────────────────────────────────────────
with tab_diff:
    st.subheader(f"⚠️ Differentials — players owned by <{diff_pct:.0f}% of your league")
    st.caption(
        "These players are owned by **some** managers but not all. "
        "High GW points here means the gap between managers is widening."
    )

    if diff_df.empty:
        st.info("No differentials found for this gameweek.")
    else:
        # Summary stats
        high_danger = diff_df[diff_df["Danger"] == "🔴 High"].shape[0]
        mid_danger  = diff_df[diff_df["Danger"] == "🟡 Medium"].shape[0]

        d1, d2, d3 = st.columns(3)
        d1.metric("🔴 High danger (≥10 pts)", high_danger, "differential hauled")
        d2.metric("🟡 Medium danger (6–9 pts)", mid_danger)
        d3.metric("Total differentials", len(diff_df),
                  f"owned by <{diff_pct:.0f}% of league")

        # Colour the danger column
        st.dataframe(
            diff_df[["Danger", "Player", "Team", "Position", "% league",
                      "% global", "GW pts", "Form", "Price"]],
            use_container_width=True,
            hide_index=True,
        )

        # Scatter: league own% vs GW pts
        if len(diff_df) > 1:
            fig = px.scatter(
                diff_df,
                x="% league",
                y="GW pts",
                color="Position",
                size=diff_df["GW pts"].clip(lower=1),
                hover_name="Player",
                hover_data=["Team", "% global", "Form"],
                title="Differentials — league ownership vs GW points",
                labels={"% league": "% owned in league", "GW pts": "GW points"},
            )
            fig.add_vline(x=diff_pct / 2, line_dash="dash", line_color="gray",
                          annotation_text="50% of threshold")
            st.plotly_chart(fig, use_container_width=True)

        # Who owns each dangerous differential
        st.subheader("Who owns the top differentials?")
        top_diffs = diff_df[diff_df["GW pts"] >= 6].head(10)
        for _, row in top_diffs.iterrows():
            player_id = None
            for pid, info in pmap.items():
                if info["name"] == row["Player"]:
                    player_id = pid
                    break
            if player_id is None:
                continue
            owners = [
                t["player_name"]
                for t in teams
                if picks_map.get(t["entry"])
                and any(p["element"] == player_id for p in picks_map[t["entry"]]["picks"])
            ]
            non_owners_count = n_teams - len(owners)
            with st.expander(
                f"{row['Player']} — {row['GW pts']} pts | {len(owners)} own / {non_owners_count} don't"
            ):
                if owners:
                    st.write("**Managers who own:**  " + ", ".join(owners))
                else:
                    st.write("Nobody in your league owns this player.")


# ─── Transfers ────────────────────────────────────────────────────────────────
with tab_trans:
    st.subheader(f"GW{selected_gw} Transfer Activity")

    if transfers_df.empty:
        st.info("No transfers made this gameweek (or data not yet available).")
    else:
        good = (transfers_df["Net pts"] > 0).sum()
        bad  = (transfers_df["Net pts"] < 0).sum()
        even = (transfers_df["Net pts"] == 0).sum()

        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Total transfers", len(transfers_df))
        t2.metric("✅ Good transfers", good)
        t3.metric("❌ Bad transfers", bad)
        t4.metric("➖ Neutral", even)

        st.dataframe(transfers_df, use_container_width=True, hide_index=True)

        # Net pts chart
        fig = px.bar(
            transfers_df,
            x="Manager",
            y="Net pts",
            color="Result",
            title="Transfer net points (IN pts − OUT pts)",
            color_discrete_map={
                "✅ Good": "#21c55d",
                "➖ Break even": "#888888",
                "❌ Bad": "#ff4b4b",
            },
            hover_data=["IN", "OUT"],
        )
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.4)
        st.plotly_chart(fig, use_container_width=True)

# ─── Forecast ────────────────────────────────────────────────────────────────
with tab_fore:
    next_gw = selected_gw + 1
    st.subheader(f"🔮 Forecast — GW{next_gw} onwards")
    st.caption(
        f"GW{next_gw} projections use FPL's own **ep_next** per player. "
        f"GW{next_gw + 1} and GW{next_gw + 2} use form × fixture difficulty. "
        f"Captain multiplier applied. * = ep_next column."
    )

    # ── Section 1: Fixture ticker ─────────────────────────────────────────────
    st.markdown("### 📅 Fixture Ticker — all 20 PL teams")
    gws_ahead = st.slider("GWs to show", 3, 8, 5, 1, key="ticker_gws")

    labels_df, fdr_df = build_fixture_ticker(boot, all_fixtures, next_gw, gws_ahead)

    def _color_cell(val, fdr_val):
        if fdr_val is None:
            return "background-color: #2a2a2a; color: #888;"
        bg = FDR_COLORS.get(int(fdr_val), "#ebebe4")
        fg = FDR_TEXT.get(int(fdr_val), "black")
        return f"background-color: {bg}; color: {fg}; font-weight: 600; text-align: center;"

    # Build styled dataframe by applying cell-level CSS
    styled = labels_df.style
    for col in labels_df.columns:
        for team in labels_df.index:
            fdr_val = fdr_df.at[team, col]
            css = _color_cell(labels_df.at[team, col], fdr_val)
            styled = styled.set_properties(
                subset=pd.IndexSlice[[team], [col]], **{
                    k.strip(): v.strip()
                    for part in css.split(";") if ":" in part
                    for k, v in [part.split(":", 1)]
                }
            )

    st.dataframe(styled, use_container_width=True)

    st.caption("🟢 Easy (FDR 1–2)  ·  ⬜ Medium (FDR 3)  ·  🔴 Hard (FDR 4–5)  ·  DGW = double gameweek")

    st.divider()

    # ── Section 2: Squad projections ─────────────────────────────────────────
    st.markdown("### 👥 Squad Projections — your league managers")
    forecast_df = build_squad_forecast(teams, picks_map, pmap, all_fixtures, next_gw, gws_ahead=3)

    if forecast_df.empty:
        st.info("No squad data available yet — check back after the deadline.")
    else:
        # Top/bottom managers
        f1, f2 = st.columns(2)
        with f1:
            best = forecast_df.iloc[0]
            st.metric("📈 Best 3GW outlook", best["Manager"],
                      f"{best['3GW proj']:.0f} projected pts")
        with f2:
            worst = forecast_df.iloc[-1]
            st.metric("📉 Toughest run", worst["Manager"],
                      f"{worst['3GW proj']:.0f} projected pts")

        st.dataframe(forecast_df, use_container_width=True, hide_index=True)

        # Bar chart: 3GW total projection
        fig = px.bar(
            forecast_df.sort_values("3GW proj", ascending=True),
            x="3GW proj", y="Manager",
            orientation="h",
            color="3GW proj",
            color_continuous_scale="RdYlGn",
            title="3-GW projected points by manager (starting XI)",
            text="3GW proj",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            showlegend=False,
            coloraxis_showscale=False,
            yaxis_title="",
            height=max(300, n_teams * 28),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Section 3: Transfer targets ───────────────────────────────────────────
    st.markdown("### 🎯 Transfer Targets — high ep_next, low league ownership")
    st.caption(
        "Players with strong expected points next GW that few in your league own. "
        "FDR shown for next 3 GWs (1=easiest, 5=hardest)."
    )

    target_threshold = st.slider(
        "Max league ownership %", 10, 60, 30, 5, key="target_thresh",
        help="Only show players owned by fewer than this % of your league"
    )

    targets_df = build_transfer_targets(
        teams, picks_map, pmap, all_fixtures, next_gw,
        max_league_own_pct=float(target_threshold),
    )

    if targets_df.empty:
        st.info("No targets found — try raising the ownership threshold.")
    else:
        st.dataframe(targets_df, use_container_width=True, hide_index=True)

        fig = px.scatter(
            targets_df,
            x="% league",
            y="ep_next",
            color="Pos",
            size=targets_df["ep_next"].clip(lower=1),
            hover_name="Player",
            hover_data=["Team", "Price", "Form", "Next 3 FDRs"],
            title="Transfer targets — league ownership vs expected next GW points",
            labels={"% league": "% owned in league", "ep_next": "Expected pts (next GW)"},
        )
        st.plotly_chart(fig, use_container_width=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("Data sourced from the official FPL API · Refreshes every 5 min · Built with Streamlit")
