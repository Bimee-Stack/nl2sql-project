"""Turns a plain-English question into SQL, validates it, runs it, and retries."""

from anthropic import Anthropic
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from src.db import get_engine
from src.llm import call_llm
from src.schema import build_system_prompt
from src.validator import validate_sql

load_dotenv(override=True)

MODEL = "claude-sonnet-5-5"
MAX_ATTEMPTS = 3

FALLBACK_MESSAGE = (
    "I couldn't work out that question. Could you rephrase it or add more detail? "
    "For example: 'How many patients were admitted last month?'"
)
UNAVAILABLE_MESSAGE = (
    "I'm having trouble reaching the AI service right now. Please try again in a moment."
)

_client = None
_system_prompt = None


def _get_client() -> Anthropic:
    """Create the Anthropic client once and reuse it.

    Returns:
        Anthropic: The API client (the key is read from the .env file).
    """
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def _get_system_prompt() -> str:
    """Build the schema prompt once and reuse it for every question.

    Returns:
        str: The system prompt containing the live database schema.
    """
    global _system_prompt
    if _system_prompt is None:
        _system_prompt = build_system_prompt()
    return _system_prompt


def generate_sql(messages: list) -> str:
    """Ask Claude to write SQL for the conversation so far.

    Args:
        messages: The chat history (the question, and any failed attempts).

    Returns:
        str: The raw text Claude produced.
    """
    return call_llm("sql_generator_llm", _get_system_prompt(), messages, 800)


def execute_query(sql: str):
    """Run a validated SELECT query in a read-only transaction.

    Args:
        sql: A query that has already passed validation.

    Returns:
        tuple: (rows, error). rows is a list of dictionaries, or None if
        the query failed. error is a message, or None if it worked.
    """
    engine = get_engine()
    with engine.connect() as conn:
        try:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            result = conn.execute(text(sql))
            rows = [dict(row._mapping) for row in result]
            return rows, None
        except DBAPIError as exc:
            first_line = str(exc.orig).strip().split("\n")[0]
            return None, f"Execution failed: {first_line}"
        finally:
            conn.rollback()


def friendly_message(question: str, reason_hint: str) -> str:
    """Write a short, non-technical message asking the user to clarify.

    Args:
        question: The user's original question.
        reason_hint: A plain-language note on why the question failed.

    Returns:
        str: A friendly message with no SQL or error details in it.
    """
    system = (
        "You are a friendly assistant for a hospital data dashboard. "
        "The user's question could not be answered. Reply in 1 or 2 short sentences. "
        "Ask them to clarify or rephrase, and give one example of a question you can "
        "answer, such as one about patients, doctors, appointments, admissions, "
        "billing or payments. Never mention SQL, errors, tables or columns."
    )
    try:
        reply = call_llm(
            "clarification_llm",
            system,
            [{"role": "user", "content": f"Question: {question}\nSituation: {reason_hint}"}],
            200,
        )
        return reply.strip()
    except Exception:
        return FALLBACK_MESSAGE


def _reason_hint(errors: list) -> str:
    """Describe the failure in plain language for the friendly message.

    Args:
        errors: The technical errors collected during the attempts.

    Returns:
        str: A non-technical description of what went wrong.
    """
    joined = " ".join(errors).lower()
    if "only select" in joined or "forbidden" in joined:
        return "The request seemed to ask for changing or deleting data. This assistant is read-only."
    if "cannot be answered" in joined:
        return "The question does not match the data this hospital database holds."
    return "The question was unclear or too vague to turn into a reliable answer."


def ask(question: str) -> dict:
    """Answer a plain-English question using the database.

    Tries up to MAX_ATTEMPTS times. Each failed attempt is sent back to
    Claude together with the problem so it can fix the query.

    Args:
        question: The user's question in plain English.

    Returns:
        dict: A result with these keys:
            status (str): "success", "clarification" or "unavailable".
            sql (str | None): The query that worked.
            rows (list | None): The result rows.
            attempts (int): How many tries were used.
            message (str | None): A friendly message when status is not success.
            debug_errors (list[str]): Technical errors, for logs only.
    """
    question = (question or "").strip()
    result = {
        "status": "clarification",
        "sql": None,
        "rows": None,
        "attempts": 0,
        "message": None,
        "debug_errors": [],
    }

    if not question:
        result["message"] = "Please type a question about the hospital data."
        return result

    messages = [{"role": "user", "content": question}]

    while result["attempts"] < MAX_ATTEMPTS:
        result["attempts"] += 1

        try:
            raw_sql = generate_sql(messages)
        except Exception as exc:
            result["status"] = "unavailable"
            result["message"] = UNAVAILABLE_MESSAGE
            result["debug_errors"].append(f"AI service error: {exc}")
            return result

        check = validate_sql(raw_sql)

        if check["sql"].upper() == "CANNOT_ANSWER":
            result["debug_errors"].extend(check["errors"])
            break

        if check["valid"]:
            rows, exec_error = execute_query(check["sql"])
            if exec_error is None:
                result.update(status="success", sql=check["sql"], rows=rows)
                return result
            problems = [exec_error]
        else:
            problems = check["errors"]

        result["debug_errors"].extend(problems)

        feedback = (
            "That query failed with these problems:\n- "
            + "\n- ".join(problems)
            + "\nFix the query. Output ONLY the corrected SQL, "
            "or CANNOT_ANSWER if the question cannot be answered."
        )
        messages.append({"role": "assistant", "content": raw_sql.strip() or "(no output)"})
        messages.append({"role": "user", "content": feedback})

    result["message"] = friendly_message(question, _reason_hint(result["debug_errors"]))
    return result
