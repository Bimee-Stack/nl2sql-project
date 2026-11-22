"""Reads the database structure and builds the prompt for the SQL generator."""

from sqlalchemy import inspect, text

from src.db import get_engine

SAMPLE_ROWS = 3
MAX_VALUE_LENGTH = 40


def _short(value):
    """Convert a value to text and shorten it if it is very long.

    Args:
        value: Any value from a database cell.

    Returns:
        str: The value as text, cut to MAX_VALUE_LENGTH characters.
    """
    value_text = str(value)
    if len(value_text) > MAX_VALUE_LENGTH:
        return value_text[:MAX_VALUE_LENGTH] + "..."
    return value_text


def get_schema_info(schema: str = "public") -> dict:
    """Read tables, columns, keys and sample rows from the database.

    Args:
        schema: The database schema to read (PostgreSQL default is "public").

    Returns:
        dict: One entry per table with its columns, primary key,
        foreign keys and a few sample rows.
    """
    engine = get_engine()
    inspector = inspect(engine)
    info = {}

    with engine.connect() as conn:
        for table in sorted(inspector.get_table_names(schema=schema)):
            columns = [
                {"name": col["name"], "type": str(col["type"])}
                for col in inspector.get_columns(table, schema=schema)
            ]

            pk_info = inspector.get_pk_constraint(table, schema=schema)
            primary_key = pk_info.get("constrained_columns", [])

            foreign_keys = []
            for fk in inspector.get_foreign_keys(table, schema=schema):
                for local, remote in zip(fk["constrained_columns"], fk["referred_columns"]):
                    foreign_keys.append(
                        {"column": local, "references": f"{fk['referred_table']}.{remote}"}
                    )

            result = conn.execute(text(f'SELECT * FROM "{table}" LIMIT {SAMPLE_ROWS}'))
            samples = [
                {key: _short(val) for key, val in row._mapping.items()}
                for row in result
            ]

            info[table] = {
                "columns": columns,
                "primary_key": primary_key,
                "foreign_keys": foreign_keys,
                "samples": samples,
            }

    return info


def format_schema(info: dict) -> str:
    """Turn the schema dictionary into readable text for the AI.

    Args:
        info: The dictionary returned by get_schema_info().

    Returns:
        str: A text description of every table.
    """
    lines = []
    for table, details in info.items():
        lines.append(f"TABLE {table}")
        for col in details["columns"]:
            marker = " (primary key)" if col["name"] in details["primary_key"] else ""
            lines.append(f"  - {col['name']}: {col['type']}{marker}")
        for fk in details["foreign_keys"]:
            lines.append(f"  FOREIGN KEY: {table}.{fk['column']} -> {fk['references']}")
        if details["samples"]:
            lines.append("  Sample rows:")
            for row in details["samples"]:
                lines.append(f"    {row}")
        lines.append("")
    return "\n".join(lines)


def build_system_prompt() -> str:
    """Build the full system prompt for the SQL generator agent.

    The schema is read from the live database each time, so nothing is
    hardcoded.

    Returns:
        str: The complete system prompt.
    """
    schema_text = format_schema(get_schema_info())
    return (
        "You are an expert PostgreSQL analyst for a hospital database.\n"
        "Convert the user's question into ONE valid PostgreSQL SELECT query.\n\n"
        "RULES:\n"
        "1. Output ONLY the SQL query, with no explanation and no markdown.\n"
        "2. Use only SELECT. Never use INSERT, UPDATE, DELETE, DROP, ALTER or TRUNCATE.\n"
        "3. Use only the tables and columns listed below.\n"
        "4. Use the foreign keys to write correct JOINs.\n"
        "5. Add LIMIT 100 unless the user asks for a specific number of rows.\n"
        "6. If the question cannot be answered with this database, output exactly: "
        "CANNOT_ANSWER\n\n"
        "DATABASE SCHEMA:\n"
        f"{schema_text}"
    )
