"""
Explore the HRM crime data API.

Throwaway exploration script, not part of the pipeline. Its job is to show us
the real shape of the data before we write code that depends on it:
  1. the field names and types,
  2. the total number of records available,
  3. the oldest and newest incident dates (this tells us how often the data
     updates, which decides how meaningful daily ingestion and drift are).
"""

import json
from datetime import datetime, timezone

import requests

# The HRM ArcGIS REST endpoint for crime incidents.
BASE_URL = (
    "https://services2.arcgis.com/11XBiaBYA9Ep0yNJ"
    "/arcgis/rest/services/Crime/FeatureServer/0/query"
)

# evt_date comes back as epoch MILLISECONDS in UTC. This helper turns one of
# those big integers into a readable date so we can reason about it.
def ms_to_date(ms: int) -> str:
    if ms is None:
        return "None"
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def get_sample() -> None:
    """Pull 5 records and print the field structure."""
    params = {
        "where": "1=1",        # match every row (standard ArcGIS idiom)
        "outFields": "*",      # all columns
        "resultRecordCount": 5,
        "f": "json",           # JSON, not the HTML viewer
    }
    print("Requesting a 5-record sample...")
    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    features = response.json().get("features", [])
    print(f"Got {len(features)} records back.\n")

    if not features:
        print("No records returned.")
        return

    first = features[0]["attributes"]
    print("=== FIELD NAMES AND TYPES (from the first record) ===")
    for field_name, value in first.items():
        print(f"  {field_name:<25} {type(value).__name__:<10} example: {value}")


def get_total_count() -> None:
    """Ask the API only for the total row count, not the rows themselves."""
    params = {
        "where": "1=1",
        "returnCountOnly": "true",  # server returns just a count, very cheap
        "f": "json",
    }
    print("\nRequesting total record count...")
    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    count = response.json().get("count")
    print(f"Total records in the dataset: {count:,}")


def get_date_range() -> None:
    """
    Ask the server to compute the min and max of evt_date for us, instead of
    downloading every row and computing it locally. ArcGIS does this via
    'outStatistics', a JSON spec of the aggregations we want.
    """
    statistics = [
        {"statisticType": "min", "onStatisticField": "evt_date",
         "outStatisticFieldName": "min_date"},
        {"statisticType": "max", "onStatisticField": "evt_date",
         "outStatisticFieldName": "max_date"},
    ]
    params = {
        "where": "1=1",
        "outStatistics": json.dumps(statistics),  # must be a JSON string
        "f": "json",
    }
    print("\nRequesting oldest and newest incident dates...")
    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    stats = response.json().get("features", [])[0]["attributes"]

    min_ms, max_ms = stats.get("min_date"), stats.get("max_date")
    print(f"Oldest incident: {ms_to_date(min_ms)}")
    print(f"Newest incident: {ms_to_date(max_ms)}")


if __name__ == "__main__":
    get_sample()
    get_total_count()
    get_date_range()