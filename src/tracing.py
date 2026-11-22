"""Tracing helpers: log every agent and Claude call to LangFuse and to traces/."""

import contextvars
import dataclasses
import json
import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

TRACES_DIR = Path(__file__).resolve().parent.parent / "traces"

_current_trace = contextvars.ContextVar("current_trace", default=None)
_current_agent = contextvars.ContextVar("current_agent", default=None)

_langfuse = None
_langfuse_failed = False


def _get_langfuse():
    """Create the LangFuse client once, or return None if it is unavailable.

    Returns:
        The LangFuse client, or None if keys are missing or setup failed.
    """
    global _langfuse, _langfuse_failed
    if _langfuse is not None or _langfuse_failed:
        return _langfuse
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        _langfuse_failed = True
        return None
    try:
        from langfuse import get_client

        _langfuse = get_client()
    except Exception:
        _langfuse_failed = True
    return _langfuse


def flush_traces():
    """Send any waiting traces to LangFuse (call this before a script ends)."""
    client = _get_langfuse()
    if client is not None:
        try:
            client.flush()
        except Exception:
            pass


def _jsonable(value, max_items: int = 5, max_text: int = 2000):
    """Convert a value into something that can be saved as JSON.

    Long lists and long text are shortened so trace files stay small.

    Args:
        value: Any Python value.
        max_items: The most list items to keep.
        max_text: The most characters of text to keep.

    Returns:
        A JSON-friendly version of the value.
    """
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        value = dataclasses.asdict(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v, max_items, max_text) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        items = [_jsonable(v, max_items, max_text) for v in value[:max_items]]
        if len(value) > max_items:
            items.append(f"... {len(value) - max_items} more items")
        return items
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    return text if len(text) <= max_text else text[:max_text] + "..."


def _elapsed_ms(start: float) -> float:
    """Return the milliseconds since a perf_counter start time.

    Args:
        start: A value from time.perf_counter().

    Returns:
        float: Elapsed time in milliseconds, to one decimal place.
    """
    return round((time.perf_counter() - start) * 1000, 1)


def _safe_update(observation, **kwargs):
    """Update a LangFuse observation, ignoring any LangFuse problems.

    Args:
        observation: A LangFuse span or generation, or None.
        **kwargs: The fields to update.
    """
    if observation is None:
        return
    try:
        observation.update(**kwargs)
    except Exception:
        pass


@contextmanager
def _langfuse_observation(as_type: str, name: str, **kwargs):
    """Open a LangFuse observation, or do nothing if LangFuse is unavailable.

    Args:
        as_type: "span" for general steps, "generation" for Claude calls.
        name: The label shown in LangFuse.
        **kwargs: Extra fields such as input or model.

    Yields:
        The LangFuse observation, or None.
    """
    client = _get_langfuse()
    manager = None
    observation = None
    if client is not None:
        try:
            manager = client.start_as_current_observation(
                as_type=as_type, name=name, **kwargs
            )
            observation = manager.__enter__()
        except Exception:
            manager, observation = None, None
    try:
        yield observation
    finally:
        if manager is not None:
            try:
                manager.__exit__(None, None, None)
            except Exception:
                pass


class _Handle:
    """Lets the code inside a trace or agent block record its output."""

    def __init__(self, record: dict, observation=None):
        """Store the record and LangFuse observation.

        Args:
            record: The dictionary that will be saved to the trace file.
            observation: The matching LangFuse observation, or None.
        """
        self.record = record
        self.observation = observation

    def set_output(self, output):
        """Record what this step produced.

        Args:
            output: Any value, which is converted to JSON-friendly form.
        """
        self.record["output"] = _jsonable(output)


class _LLMHandle:
    """Lets the code inside a Claude-call block record the reply and tokens."""

    def __init__(self, call: dict, observation=None):
        """Store the call record and LangFuse observation.

        Args:
            call: The dictionary describing this Claude call.
            observation: The matching LangFuse generation, or None.
        """
        self.call = call
        self.observation = observation

    def finish(self, output, input_tokens: int, output_tokens: int):
        """Record Claude's reply and the tokens used.

        Args:
            output: The text Claude replied with.
            input_tokens: Tokens sent to Claude.
            output_tokens: Tokens Claude wrote back.
        """
        self.call["output"] = _jsonable(output)
        self.call["input_tokens"] = int(input_tokens or 0)
        self.call["output_tokens"] = int(output_tokens or 0)
        _safe_update(
            self.observation,
            output=self.call["output"],
            usage_details={
                "input_tokens": self.call["input_tokens"],
                "output_tokens": self.call["output_tokens"],
            },
        )


def _save_trace(trace: dict):
    """Write a finished trace to the traces/ folder as a JSON file.

    Args:
        trace: The completed trace dictionary.
    """
    try:
        TRACES_DIR.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = TRACES_DIR / f"trace_{stamp}_{trace['trace_id'][:6]}.json"
        path.write_text(json.dumps(trace, indent=2, ensure_ascii=False))
    except OSError:
        pass


@contextmanager
def trace_request(question: str):
    """Trace one whole user request from start to finish.

    Args:
        question: The user's question.

    Yields:
        A handle with set_output() for recording the final result.
    """
    trace = {
        "trace_id": uuid.uuid4().hex,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "question": question,
        "output": None,
        "total_latency_ms": None,
        "total_tokens": {"input": 0, "output": 0},
        "agents": [],
    }
    token = _current_trace.set(trace)
    start = time.perf_counter()
    with _langfuse_observation("span", "nl2sql-request", input=question) as observation:
        try:
            yield _Handle(trace, observation)
        finally:
            trace["total_latency_ms"] = _elapsed_ms(start)
            _safe_update(
                observation,
                output=trace["output"],
                metadata={
                    "trace_id": trace["trace_id"],
                    "total_tokens": trace["total_tokens"],
                },
            )
            _save_trace(trace)
            _current_trace.reset(token)


@contextmanager
def trace_agent(name: str, input_data):
    """Trace one agent: its input, output and latency.

    Args:
        name: The agent's name, such as "intent_router".
        input_data: What the agent received.

    Yields:
        A handle with set_output() for recording what the agent produced.
    """
    trace = _current_trace.get()
    record = {
        "agent": name,
        "input": _jsonable(input_data),
        "output": None,
        "latency_ms": None,
        "llm_calls": [],
        "error": None,
    }
    token = _current_agent.set(record)
    start = time.perf_counter()
    with _langfuse_observation("span", name, input=record["input"]) as observation:
        try:
            yield _Handle(record, observation)
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            _safe_update(observation, level="ERROR", status_message=record["error"])
            raise
        finally:
            record["latency_ms"] = _elapsed_ms(start)
            _safe_update(observation, output=record["output"])
            _current_agent.reset(token)
            if trace is not None:
                trace["agents"].append(record)


@contextmanager
def trace_llm_call(name: str, model: str, input_data):
    """Trace one Claude call: its input, output, latency and tokens.

    Args:
        name: A label for the call, such as "router_llm".
        model: The Claude model name.
        input_data: What was sent to Claude.

    Yields:
        A handle with finish() for recording the reply and token counts.
    """
    agent = _current_agent.get()
    trace = _current_trace.get()
    call = {
        "name": name,
        "model": model,
        "input": _jsonable(input_data),
        "output": None,
        "latency_ms": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "error": None,
    }
    start = time.perf_counter()
    with _langfuse_observation(
        "generation", name, model=model, input=call["input"]
    ) as observation:
        try:
            yield _LLMHandle(call, observation)
        except Exception as exc:
            call["error"] = f"{type(exc).__name__}: {exc}"
            _safe_update(observation, level="ERROR", status_message=call["error"])
            raise
        finally:
            call["latency_ms"] = _elapsed_ms(start)
            if agent is not None:
                agent["llm_calls"].append(call)
            if trace is not None:
                trace["total_tokens"]["input"] += call["input_tokens"]
                trace["total_tokens"]["output"] += call["output_tokens"]
