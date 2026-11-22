"""One-time edits: route Claude calls in nl2sql.py and agents.py through call_llm."""

from pathlib import Path


def patch(path, pairs):
    """Apply text replacements to a file, all or nothing."""
    text = Path(path).read_text()
    for old, new in pairs:
        if old not in text:
            raise SystemExit(f"Could not find this text in {path}:\n{old}\n\nNothing was changed in {path}.")
        text = text.replace(old, new, 1)
    Path(path).write_text(text)
    print(f"Patched {path}")


patch("src/nl2sql.py", [
    (
        "from src.db import get_engine\n",
        "from src.db import get_engine\nfrom src.llm import call_llm\n",
    ),
    (
        r'''    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=800,
        system=_get_system_prompt(),
        messages=messages,
    )
    return response.content[0].text
''',
        r'''    return call_llm("sql_generator_llm", _get_system_prompt(), messages, 800)
''',
    ),
    (
        r'''        response = _get_client().messages.create(
            model=MODEL,
            max_tokens=200,
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": f"Question: {question}\nSituation: {reason_hint}",
                }
            ],
        )
        return response.content[0].text.strip()
''',
        r'''        reply = call_llm(
            "clarification_llm",
            system,
            [{"role": "user", "content": f"Question: {question}\nSituation: {reason_hint}"}],
            200,
        )
        return reply.strip()
''',
    ),
])

patch("src/agents.py", [
    (
        "from src.nl2sql import MODEL, _get_client, ask\n",
        "from src.llm import call_llm\nfrom src.nl2sql import ask\n",
    ),
    (
        "def _call_claude(system: str, user: str, max_tokens: int = 500) -> str:",
        "def _call_claude(name: str, system: str, user: str, max_tokens: int = 500) -> str:",
    ),
    (
        "        system: The system prompt describing the agent's job.\n",
        "        name: A label for this call, shown in traces.\n"
        "        system: The system prompt describing the agent's job.\n",
    ),
    (
        r'''    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text
''',
        r'''    return call_llm(name, system, [{"role": "user", "content": user}], max_tokens)
''',
    ),
    (
        "_call_claude(ROUTER_PROMPT, question, 300)",
        '_call_claude("router_llm", ROUTER_PROMPT, question, 300)',
    ),
    (
        "_call_claude(INTERPRETER_PROMPT, json.dumps(payload, default=str), 600)",
        '_call_claude("interpreter_llm", INTERPRETER_PROMPT, json.dumps(payload, default=str), 600)',
    ),
])

print("Done.")
