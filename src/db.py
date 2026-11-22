"""Database connection helpers for the MediCore hospital database."""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

load_dotenv(override=True)


def get_engine():
    """Create a SQLAlchemy engine using settings from the environment.

    Returns:
        sqlalchemy.engine.Engine: A connection engine for the database.

    Raises:
        RuntimeError: If any required database setting is missing.
    """
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(f"Missing settings: {', '.join(missing)}")

    query = {}
    sslmode = os.getenv("DB_SSLMODE")
    if sslmode:
        query["sslmode"] = sslmode

    url = URL.create(
        "postgresql+psycopg2",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        query=query,
    )
    return create_engine(url)


def run_query(sql: str):
    """Run a SQL query and return the rows.

    Args:
        sql: The SQL text to execute.

    Returns:
        list[dict]: One dictionary per row, keyed by column name.
    """
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        return [dict(row._mapping) for row in result]
