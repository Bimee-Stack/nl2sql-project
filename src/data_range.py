"""Finds the date range covered by the data, so the dashboard filter starts sensibly."""

from datetime import date, datetime

from sqlalchemy import inspect, text
from sqlalchemy.types import Date, DateTime

from src.db import get_engine

SKIP_WORDS = ("birth", "dob", "expiry", "expire", "due", "next_")


def _to_date(value):
    """Convert a database date or timestamp into a plain date.

    Args:
        value: A date, datetime or None.

    Returns:
        date | None: The date, or None if the value is not a date.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def get_data_date_range():
    """Find the earliest and latest dates across the database's date columns.

    Birth dates and expiry dates are skipped because they would stretch
    the range far beyond the period the data really covers.

    Returns:
        tuple | None: (earliest_date, latest_date), or None if no dates were found.
    """
    try:
        engine = get_engine()
        inspector = inspect(engine)
        earliest, latest = [], []
        with engine.connect() as conn:
            for table in inspector.get_table_names(schema="public"):
                for col in inspector.get_columns(table, schema="public"):
                    name = col["name"]
                    if not isinstance(col["type"], (Date, DateTime)):
                        continue
                    if any(word in name.lower() for word in SKIP_WORDS):
                        continue
                    row = conn.execute(
                        text(f'SELECT MIN("{name}"), MAX("{name}") FROM "{table}"')
                    ).one()
                    low, high = _to_date(row[0]), _to_date(row[1])
                    if low and high:
                        earliest.append(low)
                        latest.append(high)
        if not earliest:
            return None
        return min(earliest), max(latest)
    except Exception:
        return None
