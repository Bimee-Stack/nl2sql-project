"""Quick check that the environment and API key work."""

import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()  # reads the .env file

api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise SystemExit("ANTHROPIC_API_KEY not found. Check your .env file.")

client = Anthropic(api_key=api_key)

response = client.messages.create(
    model="claude-haiku-5-5",
    max_tokens=50,
    messages=[{"role": "user", "content": "Say hello in one short sentence."}],
)

print("Claude says:", response.content[0].text)
print("Setup works!")