"""Quick check that Python can read the hospital database."""

from src.db import run_query

tables = run_query(
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema = 'public' ORDER BY table_name"
)
print(f"Found {len(tables)} tables:")
for row in tables:
    print(" -", row["table_name"])

patients = run_query("SELECT COUNT(*) AS total FROM patients")
print("Total patients:", patients[0]["total"])