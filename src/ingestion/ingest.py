"""Station 1: daily ingestion of Halifax crime incidents."""

import json
from datetime import datetime, timezone

import requests

from src.config import CRIME_API_URL, RAW_DATA_DIR
from src.ingestion.db import get_connection, init_schema


def fetch_current_window() -> list[dict]:
    params = {"where": "1=1", "outFields": "*", "f": "json"}
    response = requests.get(CRIME_API_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    return [feature["attributes"] for feature in payload.get("features", [])]


def save_raw_snapshot(records: list[dict]) -> None:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    path = RAW_DATA_DIR / f"crime_{today}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    print(f"Saved raw snapshot: {path} ({len(records)} records)")


def ms_to_date(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def store_incidents(records: list[dict]) -> None:
    if not records:
        print("No records to store.")
        return

    distinct_rins = {r["evt_rin"] for r in records}
    if len(distinct_rins) != len(records):
        print(
            f"WARNING: {len(records)} records but only {len(distinct_rins)} "
            f"distinct evt_rin. The dedup key may not be unique. Investigate."
        )

    rows = [
        (
            r["evt_rin"],
            r.get("evt_rt"),
            ms_to_date(r["evt_date"]),
            r.get("location"),
            r.get("rucr"),
            r.get("rucr_ext_d"),
        )
        for r in records
    ]

    insert_sql = """
        INSERT INTO incidents (evt_rin, evt_rt, evt_date, location, rucr, rucr_ext_d)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (evt_rin) DO NOTHING;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM incidents;")
            before = cur.fetchone()[0]
            cur.executemany(insert_sql, rows)
            cur.execute("SELECT count(*) FROM incidents;")
            after = cur.fetchone()[0]
        conn.commit()

    new_count = after - before
    print(
        f"Fetched {len(records)} incidents from the current window. "
        f"Stored {new_count} new, skipped {len(records) - new_count} already seen. "
        f"Archive now holds {after} total incidents."
    )


def run() -> None:
    init_schema()
    records = fetch_current_window()
    save_raw_snapshot(records)
    store_incidents(records)


if __name__ == "__main__":
    run()