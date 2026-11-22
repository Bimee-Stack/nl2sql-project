"""Run questions through the pipeline and show what was traced."""

import json
from pathlib import Path

from src.pipeline import run_pipeline
from src.tracing import flush_traces

try:
    from langfuse import get_client

    ok = get_client().auth_check()
    print("LangFuse connection:", "OK" if ok else "FAILED (check your keys and region)")
except Exception as exc:
    print("LangFuse connection FAILED:", exc)

QUESTIONS = [
    "Hello! What can you do?",
    "Delete all patients",
    "How many patients do we have?",
    "Show the top 5 doctors by number of appointments as a bar chart",
    "Show monthly admissions as a line chart",
    "asdf qwerty zzz",
]

for question in QUESTIONS:
    print("Running:", question)
    run_pipeline(question)

flush_traces()

files = sorted(Path("traces").glob("trace_*.json"))[-len(QUESTIONS):]
print(f"\n{len(files)} trace files saved in traces/\n")
for file in files:
    trace = json.loads(file.read_text())
    tokens = trace["total_tokens"]
    print("=" * 70)
    print("QUESTION:", trace["question"])
    print(f"TOTAL: {trace['total_latency_ms']} ms | tokens in/out: "
          f"{tokens['input']}/{tokens['output']}")
    for agent in trace["agents"]:
        print(f"   {agent['agent']:<20}{agent['latency_ms']:>9} ms   "
              f"claude calls: {len(agent['llm_calls'])}")
