"""Storage for Station 2 feature tables: schema, reads, and writes.

All database I/O for feature engineering lives here, so build_features.py
stays pure transformation logic. Reuses the connection helper from Station 1."""

import pandas as pd

from src.ingestion.db import get_connection

CREATE_DAILY_FEATURES_SQL = """
CREATE TABLE IF NOT EXISTS daily_features (
    feature_date    DATE PRIMARY KEY,
    total_incidents INTEGER NOT NULL,
    day_of_week     SMALLINT NOT NULL,
    is_weekend      BOOLEAN NOT NULL,
    rolling_7d_avg  DOUBLE PRECISION,
    rolling_7d_std  DOUBLE PRECISION
);
"""

CREATE_DAILY_CRIME_COUNTS_SQL = """
CREATE TABLE IF NOT EXISTS daily_crime_counts (
    feature_date   DATE NOT NULL,
    crime_type     TEXT NOT NULL,
    incident_count INTEGER NOT NULL,
    PRIMARY KEY (feature_date, crime_type)
);
"""


def init_feature_schema() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_DAILY_FEATURES_SQL)
            cur.execute(CREATE_DAILY_CRIME_COUNTS_SQL)
        conn.commit()


def read_incidents() -> pd.DataFrame:
    """Load the columns we need from the incidents table (the source of truth
    that Station 1 populates)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT evt_date, rucr_ext_d FROM incidents;")
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
    return pd.DataFrame(rows, columns=columns)


def store_features(daily: pd.DataFrame, crime_counts: pd.DataFrame) -> None:
    """Replace the feature tables with freshly computed features.

    Features are derived entirely from the incidents table, so the correct
    pattern is recompute-and-replace: wipe the feature tables and rewrite them
    from scratch every run. This keeps features perfectly in sync with
    incidents and makes the build idempotent. The wipe and rewrite share one
    transaction, so a reader never catches the tables empty.

    We cast each value to a native Python type (int, float, bool, date)
    because psycopg will not adapt numpy's int64/float64/bool_ types directly."""
    daily_rows = [
        (
            r.feature_date.date(),
            int(r.total_incidents),
            int(r.day_of_week),
            bool(r.is_weekend),
            float(r.rolling_7d_avg),
            float(r.rolling_7d_std),
        )
        for r in daily.itertuples(index=False)
    ]
    crime_rows = [
        (r.feature_date.date(), str(r.crime_type), int(r.incident_count))
        for r in crime_counts.itertuples(index=False)
    ]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM daily_features;")
            cur.execute("DELETE FROM daily_crime_counts;")
            cur.executemany(
                """
                INSERT INTO daily_features
                    (feature_date, total_incidents, day_of_week, is_weekend,
                     rolling_7d_avg, rolling_7d_std)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                daily_rows,
            )
            cur.executemany(
                """
                INSERT INTO daily_crime_counts
                    (feature_date, crime_type, incident_count)
                VALUES (%s, %s, %s);
                """,
                crime_rows,
            )
        conn.commit()