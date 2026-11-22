"""Try the 3-agent pipeline with different kinds of questions."""

from src.pipeline import run_pipeline

QUESTIONS = [
    "Hello! What can you do?",
    "Delete all patients",
    "How many patients do we have?",
    "Show the top 5 doctors by number of appointments as a bar chart",
    "Show monthly admissions as a line chart",
    "asdf qwerty zzz",
]

for question in QUESTIONS:
    print("=" * 70)
    print("QUESTION:", question)
    result = run_pipeline(question)
    print("INTENT:  ", result["intent"])
    print("STATUS:  ", result["status"], f"(sql attempts: {result['attempts']})")
    if result["status"] == "success":
        print("SQL:     ", result["sql"])
        print("ROWS:    ", len(result["rows"]))
        print("SUMMARY: ", result["summary"])
        print("CHART:   ", result["chart"])
    else:
        print("MESSAGE: ", result["message"])
