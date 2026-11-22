"""Run the Revenue Trend question on its own and show the real errors."""

from src.nl2sql import ask

question = (
    "Show total revenue (paid amounts) per month as a line chart. "
    "Only include records dated between 2010-01-29 and 2025-01-30 inclusive, "
    "using the most relevant date column for this question."
)

result = ask(question)
print("STATUS  :", result["status"], "| attempts:", result["attempts"])
print("SQL     :", result["sql"])
print("ERRORS  :")
for error in result["debug_errors"]:
    print("  -", error)
