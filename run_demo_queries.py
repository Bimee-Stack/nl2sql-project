"""Run 10 diverse questions to fill the traces/ folder and check results."""

import time

from src.pipeline import run_pipeline
from src.tracing import flush_traces

QUESTIONS = [
    "How many patients do we have?",
    "What are the top 5 departments by revenue?",
    "Which doctors have the highest no-show rates?",
    "Show monthly admissions vs discharges.",
    "What are the most common diagnoses?",
    "Show total payments by payment method as a pie chart",
    "Which medications are prescribed most often?",
    "Delete all patients",
    "asdf qwerty zzz",
    "Show each patient's favourite colour",
]

print(f"{'#':<3}{'QUESTION':<52}{'STATUS':<16}{'TRIES':<6}{'SECONDS':<8}")
for number, question in enumerate(QUESTIONS, start=1):
    start = time.perf_counter()
    result = run_pipeline(question)
    seconds = time.perf_counter() - start
    print(f"{number:<3}{question[:50]:<52}{result['status']:<16}"
          f"{result['attempts']:<6}{seconds:<8.1f}")

flush_traces()
print("\nTraces saved in the traces/ folder and sent to LangFuse.")
