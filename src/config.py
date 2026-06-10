"""Central configuration. Reads from .env so secrets and environment-specific
values never get hardcoded into the pipeline code."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

CRIME_API_URL = (
    "https://services2.arcgis.com/11XBiaBYA9Ep0yNJ"
    "/arcgis/rest/services/Crime/FeatureServer/0/query"
)

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Add it to your .env file. "
        "Example: postgresql://mohamedwael@localhost:5432/halifax_crime"
    )