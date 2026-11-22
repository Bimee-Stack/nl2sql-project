"""Break the system on purpose and check that it fails gracefully."""

import os

from src import llm, pipeline
from src.pipeline import run_pipeline
from src.tracing import flush_traces


def show(title, result):
    """Print the important parts of a pipeline result."""
    print("=" * 70)
    print(title)
    print(f"STATUS : {result['status']} | intent: {result['intent']} | "
          f"attempts: {result['attempts']}")
    if result["message"]:
        print("MESSAGE:", result["message"])
    if result["suggestions"]:
        print("TRY    :", result["suggestions"])
    if result["status"] == "success":
        print("ROWS   :", len(result["rows"]))
        print("SUMMARY:", result["summary"])


show("1. Normal question (should succeed)",
     run_pipeline("How many patients do we have?"))

show("2. Data question the database cannot answer (retries, then fallback)",
     run_pipeline("Show each patient's favourite colour and shoe size"))

# 3. Pretend the AI service is down
original_client = llm.get_client


def broken_client():
    raise RuntimeError("simulated AI outage")


llm.get_client = broken_client
try:
    show("3. SIMULATED AI OUTAGE", run_pipeline("How many doctors do we have?"))
finally:
    llm.get_client = original_client

# 4. Pretend the database is down (wrong port)
saved_port = os.environ.get("DB_PORT")
os.environ["DB_PORT"] = "5999"
try:
    show("4. SIMULATED DATABASE OUTAGE", run_pipeline("How many appointments do we have?"))
finally:
    if saved_port is None:
        os.environ.pop("DB_PORT", None)
    else:
        os.environ["DB_PORT"] = saved_port

# 5. Pretend the Result Interpreter agent has a bug
original_interpreter = pipeline.result_interpreter_agent


def broken_interpreter(*args, **kwargs):
    raise RuntimeError("simulated agent crash")


pipeline.result_interpreter_agent = broken_interpreter
try:
    show("5. SIMULATED AGENT CRASH (rows should still come back)",
         run_pipeline("How many patients do we have?"))
finally:
    pipeline.result_interpreter_agent = original_interpreter

show("6. Empty input", run_pipeline("   "))

flush_traces()
print("\nDone. No unhandled exceptions.")
