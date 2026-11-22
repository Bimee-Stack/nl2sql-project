"""Connects the agents into one traced pipeline that never crashes."""

from dataclasses import asdict

from src.agents import (
    intent_router_agent,
    result_interpreter_agent,
    sql_generator_agent,
)
from src.fallback import fallback_agent
from src.messages import InterpretedResult, RouterMessage, SQLMessage
from src.tracing import trace_agent, trace_request

MAX_QUESTION_CHARS = 1000


def _new_result(intent: str, message=None) -> dict:
    """Create an empty pipeline result.

    Args:
        intent: The Router's decision.
        message: Text to show the user, if any.

    Returns:
        dict: A result with every key present and set to its empty value.
    """
    return {
        "status": "direct_reply",
        "message": message,
        "suggestions": [],
        "sql": None,
        "rows": None,
        "summary": None,
        "chart": None,
        "intent": intent,
        "attempts": 0,
        "agent_messages": {},
    }


def _run_agents(question: str) -> dict:
    """Pass the question through the agents, protecting every step.

    Args:
        question: The user's question in plain English.

    Returns:
        dict: The pipeline result (see run_pipeline for the keys).
    """
    if not question:
        return _new_result("unclear", "Please type a question about the hospital data.")

    # Agent 1: Intent Router. If it crashes, treat the question as a data query.
    try:
        with trace_agent("intent_router", question) as span:
            router_msg = intent_router_agent(question)
            span.set_output(router_msg)
    except Exception:
        router_msg = RouterMessage(question=question, intent="data_query")

    out = _new_result(router_msg.intent, router_msg.reply)
    out["agent_messages"]["router"] = asdict(router_msg)

    if router_msg.intent != "data_query":
        return out

    # Agent 2: SQL Generator. If it crashes, report an error status.
    try:
        with trace_agent("sql_generator", question) as span:
            sql_msg = sql_generator_agent(question)
            span.set_output(
                {
                    "status": sql_msg.status,
                    "sql": sql_msg.sql,
                    "attempts": sql_msg.attempts,
                    "row_count": len(sql_msg.rows) if sql_msg.rows is not None else None,
                    "errors": sql_msg.errors,
                }
            )
    except Exception as exc:
        sql_msg = SQLMessage(
            question=question,
            status="error",
            errors=[f"{type(exc).__name__}: {exc}"],
        )

    out["attempts"] = sql_msg.attempts
    out["agent_messages"]["sql_generator"] = {
        "status": sql_msg.status,
        "sql": sql_msg.sql,
        "attempts": sql_msg.attempts,
        "row_count": len(sql_msg.rows) if sql_msg.rows is not None else None,
        "errors": sql_msg.errors,
    }

    # Persistent failure: hand over to the Fallback Agent.
    if sql_msg.status != "success":
        failure = {
            "question": question,
            "failure_type": sql_msg.status,
            "errors": sql_msg.errors,
        }
        with trace_agent("fallback_agent", failure) as span:
            reply = fallback_agent(question, sql_msg.status, sql_msg.message)
            span.set_output(reply)
        out["status"] = sql_msg.status
        out["message"] = reply["message"]
        out["suggestions"] = reply["suggestions"]
        out["agent_messages"]["fallback"] = reply
        return out

    # Agent 3: Result Interpreter. If it crashes, still return the rows.
    rows = sql_msg.rows or []
    interpreter_input = {
        "question": question,
        "row_count": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
    }
    try:
        with trace_agent("result_interpreter", interpreter_input) as span:
            interpreted = result_interpreter_agent(question, sql_msg, router_msg)
            span.set_output(interpreted)
    except Exception:
        interpreted = InterpretedResult(summary=f"The query returned {len(rows)} row(s).")

    out["agent_messages"]["interpreter"] = asdict(interpreted)
    out.update(
        status="success",
        message=None,
        sql=sql_msg.sql,
        rows=sql_msg.rows,
        summary=interpreted.summary,
        chart=interpreted.chart,
    )
    return out


def run_pipeline(question: str) -> dict:
    """Answer a question by passing it through the agents. Never raises.

    The whole request is traced: each agent's input, output, latency and
    token use is saved to LangFuse and to the traces/ folder.

    Args:
        question: The user's question in plain English.

    Returns:
        dict: A result with these keys:
            status (str): success, direct_reply, clarification, unavailable,
                database_error or error.
            message (str | None): Text to show when there is no data answer.
            suggestions (list[str]): Example questions after a failure.
            sql (str | None): The query that ran.
            rows (list | None): The result rows.
            summary (str | None): The insight from the Result Interpreter.
            chart (dict | None): The chart specification.
            intent (str): The Router's decision.
            attempts (int): SQL attempts used.
            agent_messages (dict): The structured message from each agent.
    """
    question = (question or "").strip()[:MAX_QUESTION_CHARS]

    with trace_request(question) as trace:
        try:
            result = _run_agents(question)
        except Exception:
            reply = fallback_agent(question, "error")
            result = _new_result("data_query", reply["message"])
            result["status"] = "error"
            result["suggestions"] = reply["suggestions"]

        trace.set_output(
            {
                "status": result["status"],
                "intent": result["intent"],
                "attempts": result["attempts"],
                "sql": result["sql"],
                "row_count": len(result["rows"]) if result["rows"] is not None else None,
                "summary": result["summary"],
                "message": result["message"],
            }
        )
    return result
