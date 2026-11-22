"""Builds Plotly charts from the chart specification made by the Result Interpreter."""

import pandas as pd
import plotly.express as px


def rows_to_dataframe(rows: list) -> pd.DataFrame:
    """Convert query rows into a table, turning numeric text into numbers.

    Args:
        rows: A list of dictionaries, one per row.

    Returns:
        pd.DataFrame: The rows as a table (empty if there are no rows).
    """
    df = pd.DataFrame(rows or [])
    for column in df.columns:
        if df[column].dtype == object:
            try:
                df[column] = pd.to_numeric(df[column])
            except (ValueError, TypeError):
                pass
    return df


def build_figure(chart: dict, df: pd.DataFrame):
    """Create a bar, line or pie chart from a chart specification.

    Args:
        chart: A dictionary with type, x, y, title, x_label and y_label.
        df: The data to plot.

    Returns:
        plotly.graph_objects.Figure: The finished chart.

    Raises:
        ValueError: If the chart type is not supported.
    """
    x, y = chart["x"], chart["y"]
    title = chart["title"]
    labels = {x: chart["x_label"], y: chart["y_label"]}
    kind = chart["type"]

    if kind == "line":
        fig = px.line(df.sort_values(x), x=x, y=y, markers=True, title=title, labels=labels)
    elif kind == "bar":
        fig = px.bar(df, x=x, y=y, title=title, labels=labels)
    elif kind == "pie":
        fig = px.pie(df, names=x, values=y, title=title)
    else:
        raise ValueError(f"Unsupported chart type: {kind}")

    fig.update_layout(
        template="plotly_white",
        height=380,
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
    )
    return fig
