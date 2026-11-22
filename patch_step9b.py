"""One-time edit: read only the text blocks from Claude's reply."""

from pathlib import Path

path = Path("src/llm.py")
text = path.read_text()

old = "        text = response.content[0].text\n"
new = '''        text = "".join(
            block.text
            for block in response.content
            if getattr(block, "type", "") == "text"
        ).strip()
        if not text:
            raise RuntimeError(
                f"Claude returned no text (stop reason: {response.stop_reason})"
            )
'''

if old not in text:
    raise SystemExit("Could not find the expected line in src/llm.py. Nothing was changed.")

path.write_text(text.replace(old, new, 1))
print("Patched src/llm.py")
