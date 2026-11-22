"""Validates generated SQL before it is allowed to run."""

import re

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from src.db import get_engine

FORBIDDEN_KEYWORDS = [
    "insert", "update", "delete", "drop", "alter", "truncate", "create",
    "grant", "revoke", "copy", "call", "execute", "merge", "vacuum",
    "into", "set",
]

FORBIDDEN_FUNCTIONS = [
    "pg_sleep", "pg_read_file", "pg_ls_dir", "lo_import", "lo_export",
    "dblink", "pg_terminate_backend",
]


def clean_sql(sql: str) -> str:
    """Remove markdown fences, extra spaces and trailing semicolons.

    Args:
        sql: The raw text produced by the SQL generator.

    Returns:
        str: The cleaned SQL text.
    """
    cleaned = (sql or "").strip()
    cleaned = re.sub(r"^```(?:sql)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    cleaned = cleaned.rstrip(";").strip()
    return cleaned


def _strip_literals(sql: str) -> str:
    """Replace quoted text values with empty quotes for safe keyword checks.

    This stops a harmless value such as 'drop' from being mistaken
    for a dangerous command.

    Args:
        sql: The cleaned SQL text.

    Returns:
        str: The SQL with the contents of string literals removed.
    """
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def _check_with_database(sql: str):
    """Ask PostgreSQL to plan the query without running it.

    EXPLAIN catches unknown tables, unknown columns and syntax errors.
    The check runs in a read-only transaction that is always rolled back.

    Args:
        sql: A cleaned SELECT query.

    Returns:
        str | None: An error message, or None if the query is valid.
    """
    engine = get_engine()
    with engine.connect() as conn:
        try:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(text(f"EXPLAIN {sql}"))
        except DBAPIError as exc:
            first_line = str(exc.orig).strip().split("\n")[0]
            return f"Database check failed: {first_line}"
        finally:
            conn.rollback()
    return None


def validate_sql(sql: str) -> dict:
    """Check whether a SQL query is safe and correct.

    Args:
        sql: The SQL text produced by the SQL generator.

    Returns:
        dict: A result with three keys:
            valid (bool): True if the query may run.
            sql (str): The cleaned query.
            errors (list[str]): Reasons the query was rejected.
    """
    cleaned = clean_sql(sql)

    if not cleaned:
        return {"valid": False, "sql": cleaned, "errors": ["The query is empty."]}

    if cleaned.upper() == "CANNOT_ANSWER":
        return {
            "valid": False,
            "sql": cleaned,
            "errors": ["The question cannot be answered with this database."],
        }

    errors = []
    analysis = _strip_literals(cleaned)
    lowered = analysis.lower()

    if not re.match(r"\s*(select|with)\b", lowered):
        errors.append("Only SELECT queries are allowed.")

    if ";" in analysis:
        errors.append("Only one SQL statement is allowed.")

    if "--" in analysis or "/*" in analysis:
        errors.append("SQL comments are not allowed.")

    for word in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{word}\b", lowered):
            errors.append(f"Forbidden keyword found: {word.upper()}")

    for func in FORBIDDEN_FUNCTIONS:
        if re.search(rf"\b{func}\b", lowered):
            errors.append(f"Forbidden function found: {func}")

    if errors:
        return {"valid": False, "sql": cleaned, "errors": errors}

    db_error = _check_with_database(cleaned)
    if db_error:
        return {"valid": False, "sql": cleaned, "errors": [db_error]}

    return {"valid": True, "sql": cleaned, "errors": []}
