import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
from datetime import datetime, timezone

st.set_page_config(page_title="PJM Grid Dashboard", layout="wide")

DB_FILE = "grid_data.db"

# Fixed color assigned to each fuel type — using the same color for the same
# fuel every time (rather than letting the chart library auto-pick colors)
# is what keeps the chart readable as it updates.
FUEL_COLORS = {
    "NG":  {"label": "Natural Gas", "color": "#2a78d6"},
    "COL": {"label": "Coal",        "color": "#eb6834"},
    "NUC": {"label": "Nuclear",     "color": "#1baf7a"},
    "SUN": {"label": "Solar",       "color": "#eda100"},
    "WND": {"label": "Wind",        "color": "#e87ba4"},
    "WAT": {"label": "Hydro",       "color": "#008300"},
    "OIL": {"label": "Petroleum",   "color": "#4a3aa7"},
    "OTH": {"label": "Other",       "color": "#e34948"},
}
DEMAND_COLOR = "#2a78d6"
RENEWABLE_CODES = {"SUN", "WND"}   # what counts as "renewable" for our % calculation


@st.cache_data(ttl=300)   # re-read the database at most once every 5 minutes
def load_data():
    conn = sqlite3.connect(DB_FILE)
    demand = pd.read_sql("SELECT * FROM demand_readings", conn)
    generation = pd.read_sql("SELECT * FROM generation_readings", conn)
    conn.close()

    # Remember the duplicate-rows issue from earlier? This is where we clean
    # that up — keep only one row per timestamp before plotting anything.
    demand = demand.drop_duplicates(subset=["period"]).sort_values("period")
    generation = generation.drop_duplicates(subset=["period", "fueltype"]).sort_values("period")

    demand["period"] = pd.to_datetime(demand["period"])
    generation["period"] = pd.to_datetime(generation["period"])
    demand["value"] = pd.to_numeric(demand["value"])
    generation["value"] = pd.to_numeric(generation["value"])

    return demand, generation


demand_df, generation_df = load_data()

st.title("PJM Grid Health Dashboard")
st.caption("Live electricity demand and generation mix for the PJM grid region (covers NJ, PA, and neighboring states)")

# ---- Top row: quick-glance stats ----
latest_demand = demand_df.iloc[-1]
latest_period = generation_df["period"].max()
latest_gen = generation_df[generation_df["period"] == latest_period]
total_gen = latest_gen["value"].sum()
renewable_gen = latest_gen[latest_gen["fueltype"].isin(RENEWABLE_CODES)]["value"].sum()
renewable_pct = (renewable_gen / total_gen * 100) if total_gen else 0

col1, col2, col3 = st.columns(3)
col1.metric("Current Demand", f"{latest_demand['value']:,.0f} MWh")
col2.metric("Renewable Share (latest hour)", f"{renewable_pct:.1f}%")
col3.metric("Unique Hours Collected", f"{len(demand_df):,}")

# ---- Chart 1: demand over time ----
st.subheader("Electricity Demand Over Time")
fig_demand = go.Figure()
fig_demand.add_trace(go.Scatter(
    x=demand_df["period"], y=demand_df["value"],
    mode="lines", line=dict(color=DEMAND_COLOR, width=2),
    name="Demand", hovertemplate="%{x}<br>%{y:,.0f} MWh<extra></extra>"
))
fig_demand.update_layout(
    height=350, margin=dict(l=10, r=10, t=10, b=10),
    yaxis_title="Demand (MWh)", hovermode="x unified"
)
st.plotly_chart(fig_demand, use_container_width=True)

# ---- Chart 2: generation mix over time (stacked area) ----
st.subheader("Generation Mix Over Time")
fig_mix = go.Figure()
for code, meta in FUEL_COLORS.items():
    series = generation_df[generation_df["fueltype"] == code]
    if series.empty:
        continue
    fig_mix.add_trace(go.Scatter(
        x=series["period"], y=series["value"],
        mode="lines", stackgroup="one",
        name=meta["label"], line=dict(width=0.5, color=meta["color"]),
        fillcolor=meta["color"],
        hovertemplate="%{x}<br>%{y:,.0f} MWh<extra>" + meta["label"] + "</extra>"
    ))
fig_mix.update_layout(
    height=400, margin=dict(l=10, r=10, t=10, b=10),
    yaxis_title="Generation (MWh)", hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02)
)
st.plotly_chart(fig_mix, use_container_width=True)

st.caption(f"Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} — data refreshes automatically every hour via GitHub Actions.")
# ---- Chart 3: net load (the "duck curve") ----
st.subheader("Net Load: Demand Minus Solar & Wind")
st.caption(
    "This is the number grid operators actually have to manage — how much load "
    "still needs to come from other sources once variable solar and wind are subtracted."
)

renewable_by_period = (
    generation_df[generation_df["fueltype"].isin(RENEWABLE_CODES)]
    .groupby("period")["value"].sum()
    .rename("renewable_mw")
)

net_load_df = demand_df.merge(renewable_by_period, on="period", how="inner")
net_load_df["net_load"] = net_load_df["value"] - net_load_df["renewable_mw"]

fig_net = go.Figure()
fig_net.add_trace(go.Scatter(
    x=net_load_df["period"], y=net_load_df["value"],
    mode="lines", line=dict(color="#2a78d6", width=2),
    name="Total Demand", hovertemplate="%{x}<br>%{y:,.0f} MWh<extra>Total Demand</extra>"
))
fig_net.add_trace(go.Scatter(
    x=net_load_df["period"], y=net_load_df["net_load"],
    mode="lines", line=dict(color="#eb6834", width=2),
    name="Net Load (Demand minus Solar/Wind)",
    hovertemplate="%{x}<br>%{y:,.0f} MWh<extra>Net Load</extra>"
))
fig_net.update_layout(
    height=350, margin=dict(l=10, r=10, t=10, b=10),
    yaxis_title="MWh", hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02)
)
st.plotly_chart(fig_net, use_container_width=True)