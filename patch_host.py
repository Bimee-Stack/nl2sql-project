"""One-time edit: add an optional password screen to app.py."""

from pathlib import Path

path = Path("app.py")
text = path.read_text()
marker = 'st.set_page_config(page_title="MediCore Hospital Dashboard", layout="wide")\n'

if marker not in text:
    raise SystemExit("Could not find the set_page_config line. Nothing was changed.")
if "APP_PASSWORD" in text:
    raise SystemExit("Already patched. Nothing was changed.")

gate = '''
import hmac
import os

APP_PASSWORD = os.getenv("APP_PASSWORD")
if APP_PASSWORD and not st.session_state.get("authed"):
    entered = st.text_input("Password", type="password")
    if entered:
        if hmac.compare_digest(entered.encode(), APP_PASSWORD.encode()):
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()
'''

path.write_text(text.replace(marker, marker + gate, 1))
print("Patched app.py")
