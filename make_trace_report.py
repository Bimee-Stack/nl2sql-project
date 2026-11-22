"""Pick three representative traces and write report_trace_data.md for the report."""

import json
from pathlib import Path

FENCE = "`" * 3


def load_traces() -> list:
    """Read every trace file in the traces/ folder.

    Returns:
        list[dict]: The traces, oldest first.
    """
    traces = []
    for path in sorted(Path("traces").glob("trace_*.json")):
        try:
            trace = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        trace["_file"] = path.name
        traces.append(trace)
    return traces


def sql_info(trace: dict):
    """Return the SQL Generator's output for a trace.

    Args:
        trace: One loaded trace.

    Returns:
        dict | None: The agent's output, or None if the trace has no SQL step.
    """
    for agent in trace.get("agents", []):
        if agent["agent"] == "sql_generator":
            return agent.get("output") or {}
    return None


def complexity(info: dict) -> float:
    """Score how complex a query was (more joins and retries score higher).

    Args:
        info: The SQL Generator's output.

    Returns:
        float: A complexity score.
    """
    sql = " ".join((info.get("sql") or "").upper().split())
    return (
        sql.count(" JOIN ") * 3
        + sql.count("GROUP BY")
        + sql.count("ORDER BY")
        + sql.count("WITH ") * 2
        + (info.get("attempts") or 1) * 2
        + len(sql) / 300
    )


def pick(traces: list):
    """Choose a simple, a complex and a failed trace.

    Args:
        traces: All loaded traces.

    Returns:
        tuple: (simple, complex, failed), each a (trace, info) pair or None.
    """
    successes, failures = [], []
    for trace in traces:
        info = sql_info(trace)
        if info is None:
            continue
        if info.get("status") == "success":
            successes.append((trace, info))
        else:
            failures.append((trace, info))
    simple = min(successes, key=lambda p: complexity(p[1]), default=None)
    complex_ = max(successes, key=lambda p: complexity(p[1]), default=None)
    failed = max(failures, key=lambda p: p[1].get("attempts") or 0, default=None)
    return simple, complex_, failed


def describe(title: str, pair) -> str:
    """Write one trace as a block of markdown.

    Args:
        title: The heading for this trace.
        pair: A (trace, info) pair, or None.

    Returns:
        str: The markdown text.
    """
    if pair is None:
        return f"## {title}\n\nNo matching trace found. Run more queries and try again.\n"

    trace, info = pair
    errors = info.get("errors") or []
    lines = [
        f"## {title}",
        "",
        f"- **Trace file:** {trace['_file']}",
        f"- **Natural-language question:** {trace['question']}",
        f"- **Final status:** {info.get('status')} after {info.get('attempts')} attempt(s)",
        f"- **Rows returned:** {info.get('row_count')}",
        "",
        "**SQL generated:**",
        "",
        FENCE + "sql",
        info.get("sql") or "(none: no valid SQL was produced)",
        FENCE,
        "",
    ]
    if errors:
        lines += ["**Validation or execution problems (sent back to Claude on each retry):**", ""]
        lines += [f"- {error}" for error in errors]
        lines.append("")
    else:
        lines += ["**Validation:** passed on the first attempt (no errors).", ""]

    lines += [
        "**Timing and tokens:**",
        "",
        "| Agent | Time (ms) | Claude calls | Tokens in | Tokens out |",
        "|---|---|---|---|---|",
    ]
    for agent in trace["agents"]:
        calls = agent.get("llm_calls", [])
        tokens_in = sum(call["input_tokens"] for call in calls)
        tokens_out = sum(call["output_tokens"] for call in calls)
        lines.append(
            f"| {agent['agent']} | {agent['latency_ms']} | {len(calls)} | {tokens_in} | {tokens_out} |"
        )
    total = trace["total_tokens"]
    lines.append(
        f"| **Total** | **{trace['total_latency_ms']}** | | {total['input']} | {total['output']} |"
    )

    output = trace.get("output") or {}
    final = output.get("summary") or output.get("message") or "(none)"
    lines += ["", f"**Output shown to the user:** {final}", ""]
    return "\n".join(lines)


traces = load_traces()
print(f"Found {len(traces)} trace files")
if not traces:
    raise SystemExit("No traces found. Run python run_demo_queries.py first.")

simple, complex_, failed = pick(traces)
report = "# Query trace data\n\n" + "\n".join(
    [
        describe("Trace A: Simple query", simple),
        describe("Trace B: Complex query", complex_),
        describe("Trace C: Failed query", failed),
    ]
)
Path("report_trace_data.md").write_text(report)

for label, pair in (("Simple", simple), ("Complex", complex_), ("Failed", failed)):
    print(f"{label:<8}", pair[0]["question"][:70] if pair else "NOT FOUND")
print("\nSaved report_trace_data.md")
