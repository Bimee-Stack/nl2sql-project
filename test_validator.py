"""Check that the validator allows safe SQL and blocks unsafe SQL."""

from src.validator import validate_sql

CASES = [
    ("Normal count", "SELECT COUNT(*) FROM patients", True),
    ("Markdown fence", "```sql\nSELECT * FROM patients LIMIT 5;\n```", True),
    ("Harmless 'drop' text", "SELECT COUNT(*) FROM patients WHERE 'drop' = 'drop'", True),
    ("DELETE", "DELETE FROM patients", False),
    ("DROP TABLE", "DROP TABLE patients", False),
    ("UPDATE", "UPDATE patients SET first_name = 'x'", False),
    ("Two statements", "SELECT * FROM patients; DROP TABLE patients", False),
    ("Comment trick", "SELECT * FROM patients -- hide something", False),
    ("Unknown table", "SELECT * FROM unicorns", False),
    ("Unknown column", "SELECT fake_column FROM patients", False),
    ("Syntax error", "SELECT * FORM patients", False),
    ("Cannot answer", "CANNOT_ANSWER", False),
]

passed = 0
for name, sql, expected in CASES:
    result = validate_sql(sql)
    ok = result["valid"] == expected
    passed += ok
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}: valid={result['valid']} (expected {expected})")
    for error in result["errors"]:
        print(f"        reason: {error}")

print(f"\n{passed} of {len(CASES)} tests passed")
