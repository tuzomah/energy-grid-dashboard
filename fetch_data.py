import os
import sys
import requests
import pandas as pd
import sqlite3
from datetime import datetime, timezone

API_KEY = os.environ.get("EIA_API_KEY")

if not API_KEY:
    print("ERROR: EIA_API_KEY environment variable is not set.")
    sys.exit(1)

REGION = "PJM"
DB_FILE = "grid_data.db"


def fetch_demand():
    """Pulls the last 24 hours of electricity demand for our region."""
    url = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
    params = {
        "api_key": API_KEY,
        "frequency": "hourly",
        "data[]": "value",
        "facets[respondent][]": REGION,
        "facets[type][]": "D",   # D = Demand
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 24
    }
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    return pd.DataFrame(data["response"]["data"])


def fetch_generation_mix():
    """Pulls the last several hours of generation, broken down by fuel type
    (coal, gas, nuclear, solar, wind, etc.) for our region."""
    url = "https://api.eia.gov/v2/electricity/rto/fuel-type-data/data/"
    params = {
        "api_key": API_KEY,
        "frequency": "hourly",
        "data[]": "value",
        "facets[respondent][]": REGION,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 200   # more rows needed here, since each hour has one row PER fuel type
    }
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    return pd.DataFrame(data["response"]["data"])


def save_to_db(df, table_name):
    """Saves any DataFrame into its own table in our database file."""
    conn = sqlite3.connect(DB_FILE)
    df.to_sql(table_name, conn, if_exists="append", index=False)
    conn.close()


demand_df = fetch_demand()
save_to_db(demand_df, "demand_readings")

generation_df = fetch_generation_mix()
save_to_db(generation_df, "generation_readings")

timestamp = datetime.now(timezone.utc).isoformat()
print(f"[{timestamp}] Saved {len(demand_df)} demand rows and {len(generation_df)} generation rows to {DB_FILE}")