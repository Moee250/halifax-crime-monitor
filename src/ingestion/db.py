"""Database connection and schema for the crime incident store."""

import psycopg

from src.config import DATABASE_URL

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS incidents (
    evt_rin     BIGINT PRIMARY KEY,
    evt_rt      TEXT,
    evt_date    DATE NOT NULL,
    location    TEXT,
    rucr        INTEGER,
    rucr_ext_d  TEXT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def get_connection() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def init_schema() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
        conn.commit()