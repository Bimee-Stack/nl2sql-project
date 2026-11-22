"""Fallback agent: a safe, polite reply when the pipeline cannot answer.

It never calls the AI or the database, so it cannot fail for the same
reason that the rest of the pipeline did.
"""

EXAMPLE_QUESTIONS = [
    "How many patients were admitted this month?",
    "What are the top 5 departments by revenue?",
    "Which doctors have the most appointments?",
    "Show the payment methods used, as a pie chart",
    "What are the most common diagnoses?",
]

MESSAGES = {
    "unavailable": (
        "I'm having trouble reaching the AI service right now. "
        "Please try again in a minute."
    ),
    "database_error": (
        "I can't reach the hospital database at the moment. "
        "Please try again shortly, and tell your administrator if it keeps happening."
    ),
    "error": (
        "Something went wrong on my side while working on that question. "
        "Please try again, or try rephrasing it."
    ),
    "clarification": (
        "I couldn't work out that question. "
        "Could you rephrase it or add more detail?"
    ),
}


def fallback_agent(question: str, failure_type: str, existing_message=None) -> dict:
    """Build a polite reply for a question that could not be answered.

    Args:
        question: The user's original question.
        failure_type: One of clarification, unavailable, database_error or error.
        existing_message: A friendly message already written for a
            clarification failure, which is reused when present.

    Returns:
        dict: A reply with three keys:
            failure_type (str): Why the pipeline could not answer.
            message (str): Friendly text to show the user (no technical details).
            suggestions (list[str]): Three example questions that work.
    """
    message = MESSAGES.get(failure_type, MESSAGES["error"])
    if failure_type == "clarification" and existing_message:
        message = existing_message

    start = sum(ord(ch) for ch in (question or "")) % len(EXAMPLE_QUESTIONS)
    rotated = EXAMPLE_QUESTIONS[start:] + EXAMPLE_QUESTIONS[:start]

    return {
        "failure_type": failure_type,
        "message": message,
        "suggestions": rotated[:3],
    }
