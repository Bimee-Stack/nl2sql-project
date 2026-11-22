"""The single place where Claude is called, so every call is traced."""

from anthropic import Anthropic
from dotenv import load_dotenv

from src.tracing import trace_llm_call

load_dotenv(override=True)

MODEL = "claude-sonnet-5-5"

_client = None


def get_client() -> Anthropic:
    """Create the Anthropic client once and reuse it.

    Returns:
        Anthropic: The API client (the key is read from the .env file).
    """
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def call_llm(name: str, system: str, messages: list, max_tokens: int) -> str:
    """Send a request to Claude and record it in the trace.

    Args:
        name: A label for this call, shown in traces.
        system: The system prompt.
        messages: The chat messages to send.
        max_tokens: The maximum length of the reply.

    Returns:
        str: The text of Claude's reply.
    """
    payload = {"system": system, "messages": messages}
    with trace_llm_call(name, MODEL, payload) as call:
        response = get_client().messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        text = "".join(
            block.text
            for block in response.content
            if getattr(block, "type", "") == "text"
        ).strip()
        if not text:
            raise RuntimeError(
                f"Claude returned no text (stop reason: {response.stop_reason})"
            )
        call.finish(text, response.usage.input_tokens, response.usage.output_tokens)
        return text
