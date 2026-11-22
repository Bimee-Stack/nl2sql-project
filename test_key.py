"""Check which API key is loaded and whether Claude responds."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

key = os.getenv("ANTHROPIC_API_KEY") or ""
print("Key starts with:", key[:10], "| length:", len(key))

from anthropic import Anthropic

try:
    reply = Anthropic().messages.create(
        model="claude-haiku-5-5",
        max_tokens=20,
        messages=[{"role": "user", "content": "Say hi"}],
    )
    print("WORKS:", reply.content[0].text)
except Exception as exc:
    print("ERROR:", type(exc).__name__, "-", exc)
