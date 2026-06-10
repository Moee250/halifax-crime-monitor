"""Station 2: turn raw incidents into model-ready daily features.

Reads incidents from Postgres, aggregates them into one row per day, adds
time features and rolling baselines, and stores the result in daily_features
(plus a long daily_crime_counts table for per-type detail). The output is
what Station 3's anomaly model trains on."""

import pandas as pd

from src.features.store import init_feature_schema, read_incidents, store_features

ROLLING_WINDOW_DAYS = 7


def build_daily_features(incidents: pd.DataFrame) -> pd.DataFrame:
    """Aggregate incidents into one row per calendar day with count, time,
    and rolling features."""
    incidents = incidents.copy()
    incidents["evt_date"] = pd.to_datetime(incidents["evt_date"])

    # Count feature: total incidents per day.
    daily = (
        incidents.groupby("evt_date")
        .size()
        .rename("total_incidents")
        .reset_index()
        .sort_values("evt_date")
    )

    # Fill in calendar days that had zero incidents. A quiet day has no rows in
    # the source, but the model must see it as 0, not as missing, or both the
    # rolling average and the very idea of "a quiet day" break.
    full_range = pd.date_range(
        start=daily["evt_date"].min(),
        end=daily["evt_date"].max(),
        freq="D",
    )
    daily = (
        daily.set_index("evt_date")
        .reindex(full_range, fill_value=0)
        .rename_axis("feature_date")
        .reset_index()
    )

    # Time features: which day of week (Monday=0), and weekend vs weekday.
    # These let the model judge a count relative to the kind of day it is.
    daily["day_of_week"] = daily["feature_date"].dt.dayofweek
    daily["is_weekend"] = daily["day_of_week"].isin([5, 6])

    # Rolling baseline: the recent norm the anomaly detector compares against.
    # min_periods=1 means early days still get a value, computed on a partial
    # window. Those early values are noisy and shouldn't be over-trusted until
    # the archive holds a full window of history.
    rolling = daily["total_incidents"].rolling(
        window=ROLLING_WINDOW_DAYS, min_periods=1
    )
    daily["rolling_7d_avg"] = rolling.mean()
    daily["rolling_7d_std"] = rolling.std().fillna(0.0)  # std of one point is NaN

    return daily


def build_crime_type_counts(incidents: pd.DataFrame) -> pd.DataFrame:
    """Count incidents per day per crime type, in long format (one row per
    day-and-type). Long format avoids a fragile wide schema that would need a
    brand-new column every time an unseen crime type appears in the data."""
    incidents = incidents.copy()
    incidents["evt_date"] = pd.to_datetime(incidents["evt_date"])
    return (
        incidents.groupby(["evt_date", "rucr_ext_d"])
        .size()
        .rename("incident_count")
        .reset_index()
        .rename(columns={"evt_date": "feature_date", "rucr_ext_d": "crime_type"})
    )


def run() -> None:
    init_feature_schema()
    incidents = read_incidents()
    if incidents.empty:
        print("No incidents found. Run Station 1 ingestion first.")
        return

    daily = build_daily_features(incidents)
    crime_counts = build_crime_type_counts(incidents)
    store_features(daily, crime_counts)

    print(
        f"Built features for {len(daily)} days "
        f"({daily['feature_date'].min().date()} to "
        f"{daily['feature_date'].max().date()}).\n"
        f"Daily totals range from {int(daily['total_incidents'].min())} to "
        f"{int(daily['total_incidents'].max())} incidents.\n"
        f"Latest 7-day rolling average: "
        f"{daily['rolling_7d_avg'].iloc[-1]:.1f} incidents/day.\n"
        f"Tracked {crime_counts['crime_type'].nunique()} distinct crime types."
    )


if __name__ == "__main__":
    run()