"""Try the NL2SQL engine with good, tricky and bad questions."""

from src.nl2sql import ask

QUESTIONS = [
    "How many patients do we have?",
    "What are the top 5 doctors by number of appointments?",
    "Delete all patients",
    "asdf qwerty zzz",
]

for question in QUESTIONS:
    print("=" * 70)
    print("QUESTION:", question)
    result = ask(question)
    print("STATUS:  ", result["status"], f"(attempts used: {result['attempts']})")
    if result["status"] == "success":
        print("SQL:     ", result["sql"])
        print("ROWS:    ", len(result["rows"]))
        for row in result["rows"][:5]:
            print("   ", row)
    else:
        print("MESSAGE: ", result["message"])
    if result["debug_errors"]:
        print("(debug)  ", result["debug_errors"])
