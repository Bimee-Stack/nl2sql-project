"""Check that the schema prompt is built from the live database."""

from src.schema import build_system_prompt, get_schema_info

info = get_schema_info()
print(f"Tables found: {len(info)}")
for table, details in info.items():
    print(f" - {table}: {len(details['columns'])} columns, "
          f"{len(details['foreign_keys'])} foreign keys")

prompt = build_system_prompt()
print(f"\nPrompt length: {len(prompt)} characters")
print("\n----- FIRST 1500 CHARACTERS -----")
print(prompt[:1500])
