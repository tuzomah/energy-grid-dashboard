import os
import sys
import requests
import pandas as pd
import sqlite3
from datetime import datetime, timezone

# Reads the API key from an environment variable instead of hardcoding it.
# We'll set this variable up in two places later: your own terminal (for
# testing) and GitHub Secrets (for the automated cloud runs).
API_KEY = os.environ.get("EIA_API_KEY")

if not API_KEY:
    print("ERROR: EIA_API_KEY environment variable is not set.")
    sys.exit(1)   # stop the script early with an error, instead of failing later

url = "https://api.eia.gov/v2/electricity/rto/region-data/data/"

params = {
    "api_key": API_KEY,
    "frequency": "hourly",
    "data[]": "value",
    "facets[respondent][]": "PJM",
    "facets[type][]": "D",
    "sort[0][column]": "period",
    "sort[0][direction]": "desc",
    "length": 24
}

response = requests.get(url, params=params, timeout=15)
response.raise_for_status()   # raises an error if the request failed, instead of silently continuing

data = response.json()
df = pd.DataFrame(data["response"]["data"])

DB_FILE = "grid_data.db"
conn = sqlite3.connect(DB_FILE)
df.to_sql("demand_readings", conn, if_exists="append", index=False)
conn.close()

timestamp = datetime.now(timezone.utc).isoformat()
print(f"[{timestamp}] Saved {len(df)} rows to {DB_FILE}")