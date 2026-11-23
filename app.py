"""MediCore Hospital dashboard: five pre-built panels and a free-question box."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import streamlit as st

from src.charts import build_figure, rows_to_dataframe
from src.data_range import get_data_date_range
from src.fallback import EXAMPLE_QUESTIONS
from src.pipeline import run_pipeline
from src.tracing import flush_traces

PANELS = [
    {
        "title": "Revenue Trend",
        "question": "Show total revenue (paid amounts) per month as a line chart.",
    },
    {
        "title": "Top Diagnoses",
        "question": "Show the 10 most common diagnoses as a bar chart.",
    },
    {
        "title": "Doctor Load",
        "question": "Show the top 10 doctors by number of appointments as a bar chart.",
    },
    {
        "title": "Payment Methods",
        "question": "Show the total payment amount by payment method as a pie chart.",
    },
    {
        "title": "Monthly Admissions",
        "question": "Show the number of admissions per month as a line chart.",
    },
]


@st.cache_data(ttl=3600, show_spinner=False)
def cached_data_range():
    """Look up the date range of the data once per hour.

    Returns:
        tuple | None: (earliest, latest) dates, or None if unknown.
    """
    return get_data_date_range()


@st.cache_data(ttl=900, show_spinner=False)
def load_panels(questions: tuple) -> dict:
    """Answer all panel questions in parallel and remember the results.

    Args:
        questions: The panel questions, including any date filter text.

    Returns:
        dict: Maps each question to its pipeline result.
    """
    with ThreadPoolExecutor(max_workers=len(questions)) as pool:
        results = list(pool.map(run_pipeline, questions))
    flush_traces()
    return dict(zip(questions, results))


def render_result(result: dict, key: str):
    """Show one pipeline result: a chart (or table), the insight, and the SQL.

    Args:
        result: The dictionary returned by run_pipeline().
        key: A unique name so Streamlit can tell the charts apart.
    """
    if result["status"] != "success":
        st.warning(result["message"] or "No answer is available for this panel.")
        for suggestion in result.get("suggestions") or []:
            st.caption(f"Try: {suggestion}")
        import os

        if os.getenv("SHOW_DEBUG") == "1":
            details = (
                result.get("agent_messages", {}).get("sql_generator", {}).get("errors")
            )
            with st.expander("Debug details"):
                st.write(f"Status: {result['status']}")
                st.write(details or "No errors were recorded.")
        return

    df = rows_to_dataframe(result["rows"])
    chart_shown = False
    if result["chart"] is not None:
        try:
            st.plotly_chart(build_figure(result["chart"], df), key=f"chart_{key}")
            chart_shown = True
        except Exception:
            chart_shown = False
    if not chart_shown:
        st.dataframe(df)

    if result["summary"]:
        st.markdown(f"**Insight:** {result['summary']}")

    with st.expander("Show SQL and data"):
        st.code(result["sql"], language="sql")
        if chart_shown:
            st.dataframe(df)


st.set_page_config(page_title="MediCore Hospital Dashboard", layout="wide")

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
st.title("MediCore Hospital Dashboard")
st.caption("Charts are generated from plain-English questions by a team of AI agents.")

data_range = cached_data_range()
today = date.today()
default_start, default_end = data_range or (today - timedelta(days=365), today)

with st.sidebar:
    st.header("Filters")
    use_filter = st.checkbox("Filter by date range", value=data_range is not None)
    picked = st.date_input(
        "Date range",
        value=(default_start, default_end),
        min_value=date(1990, 1, 1),
        max_value=date(2100, 12, 31),
        disabled=not use_filter,
    )
    if data_range:
        st.caption(f"Your data covers about {data_range[0]} to {data_range[1]}.")
    if st.button("Refresh data"):
        st.cache_data.clear()
        st.rerun()

suffix = ""
if use_filter:
    if not (isinstance(picked, (tuple, list)) and len(picked) == 2):
        st.info("Pick both a start date and an end date in the sidebar.")
        st.stop()
    start, end = picked
    suffix = (
        f" Only include records dated between {start} and {end} inclusive, "
        "using the most relevant date column for this question."
    )
    st.caption(f"Showing records from {start} to {end}.")
else:
    st.caption("Showing all dates.")

questions = tuple(panel["question"] + suffix for panel in PANELS)
with st.spinner("The agents are working. The first load takes 10 to 20 seconds..."):
    results = load_panels(questions)

for i in range(0, len(PANELS), 2):
    chunk = PANELS[i : i + 2]
    for column, panel in zip(st.columns(len(chunk)), chunk):
        with column:
            st.subheader(panel["title"])
            render_result(results[panel["question"] + suffix], key=panel["title"])

st.divider()
st.header("Ask your own question")
st.caption("Your own questions search all dates and do not use the date filter.")
with st.form("ask_form"):
    user_question = st.text_input(
        "Type a question in plain English", placeholder=EXAMPLE_QUESTIONS[0]
    )
    submitted = st.form_submit_button("Ask")

if submitted:
    with st.spinner("Thinking..."):
        answer = run_pipeline(user_question)
        flush_traces()
    if answer["status"] == "direct_reply":
        st.info(answer["message"])
    else:
        render_result(answer, key="custom")
