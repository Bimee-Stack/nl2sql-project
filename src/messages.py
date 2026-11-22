"""Structured messages passed between the agents."""

import json
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RouterMessage:
    """What the Intent Router decided.

    Attributes:
        question: The user's original question.
        intent: One of data_query, greeting, unsafe_request, unclear.
        wants_chart: True if the user asked for a chart or graph.
        chart_hint: Suggested chart type (bar, line, pie) or None.
        reply: A ready-made reply for intents that need no database.
    """

    question: str
    intent: str
    wants_chart: bool = False
    chart_hint: Optional[str] = None
    reply: Optional[str] = None


@dataclass
class SQLMessage:
    """What the SQL Generator produced.

    Attributes:
        question: The user's original question.
        status: success, clarification or unavailable.
        sql: The query that worked (or None).
        rows: The result rows (or None).
        attempts: How many tries were used.
        message: A friendly message when status is not success.
        errors: Technical errors, for logs only.
    """

    question: str
    status: str
    sql: Optional[str] = None
    rows: Optional[list] = None
    attempts: int = 0
    message: Optional[str] = None
    errors: list = field(default_factory=list)


@dataclass
class InterpretedResult:
    """What the Result Interpreter produced.

    Attributes:
        summary: Plain-English insight that cites real numbers.
        chart: A chart specification dictionary, or None.
    """

    summary: str
    chart: Optional[dict] = None


def parse_json_object(text: str) -> Optional[dict]:
    """Safely pull a JSON object out of the AI's reply.

    Args:
        text: The raw reply, which may include markdown fences or extra words.

    Returns:
        dict | None: The parsed object, or None if no valid JSON was found.
    """
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
