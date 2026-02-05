"""
Heap Product Dashboard – Snowflake auth via access token + interactive telemetry time series.
Run locally: streamlit run app.py
Uses token from ocd-product-dashboard-token-secret.txt and SNOWFLAKE_USER env for username.
"""
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import snowflake.connector

TOKEN_FILE = os.environ.get("SNOWFLAKE_TOKEN_FILE", "ocd-product-dashboard-token-secret.txt")

CONN_PARAMS = {
    "account": "jfb46703.us-east-1",
    "warehouse": "default",
    "database": "ANALYTICS",
    "schema": "INTERMEDIATE",
}

TELEMETRY_QUERY = """
SELECT YEAR(activity_ts) AS activity_year, MONTH(ACTIVITY_TS) AS activity_month, activity_source, product, count(*) as recs
FROM stg_conda_unified_telemetry
GROUP BY 1, 2, 3, 4
ORDER BY 1, 2
"""


def load_token() -> str:
    """Read access token from file (first line, stripped)."""
    path = TOKEN_FILE if os.path.isabs(TOKEN_FILE) else os.path.join(os.path.dirname(__file__), TOKEN_FILE)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Token file not found: {path}")
    with open(path) as f:
        return f.read().strip()


def get_connection():
    """Connect to Snowflake using programmatic access token (token as password)."""
    user = os.environ.get("SNOWFLAKE_USER")
    if not user:
        raise ValueError("SNOWFLAKE_USER environment variable is required for token authentication")
    token = load_token()
    return snowflake.connector.connect(
        user=user,
        password=token,
        **CONN_PARAMS,
    )


def load_telemetry(conn) -> pd.DataFrame:
    """Run the telemetry query and return a DataFrame."""
    return pd.read_sql(TELEMETRY_QUERY, conn)


def prepare_time_series(df: pd.DataFrame) -> pd.DataFrame:
    """Build a date column and ensure types for plotting."""
    if df.empty:
        return df
    df = df.copy()
    df["activity_date"] = pd.to_datetime(
        df["ACTIVITY_YEAR"].astype(str) + "-" + df["ACTIVITY_MONTH"].astype(str).str.zfill(2) + "-01"
    )
    return df


def build_time_series_chart(df: pd.DataFrame) -> go.Figure:
    """Interactive time series: date on x, recs on y, colored by source/product."""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data to display", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    # One series per (activity_source, product) for clarity
    df["series"] = df["ACTIVITY_SOURCE"].fillna("") + " / " + df["PRODUCT"].fillna("")
    fig = px.line(
        df,
        x="activity_date",
        y="RECS",
        color="series",
        title="Telemetry records by month (activity_source / product)",
        labels={"activity_date": "Month", "RECS": "Records", "series": "Source / Product"},
    )
    fig.update_layout(
        xaxis_title="Month",
        yaxis_title="Records",
        legend_title="Source / Product",
        hovermode="x unified",
        template="plotly_white",
        height=500,
    )
    return fig


def main():
    st.set_page_config(page_title="Heap Product Dashboard", page_icon="📊", layout="wide")
    st.title("Heap Product Dashboard")
    st.caption("Snowflake telemetry time series")

    if "telemetry_df" not in st.session_state:
        st.session_state.telemetry_df = None

    # ----- Connect and load data -----
    try:
        conn = get_connection()
    except FileNotFoundError as e:
        st.error(f"Configuration error: {e}. Ensure the token file exists.")
        st.stop()
    except ValueError as e:
        st.error(f"Configuration error: {e}. Set SNOWFLAKE_USER in the environment.")
        st.stop()
    except Exception as e:
        st.error(f"Connection failed: {e}")
        st.stop()

    if st.session_state.telemetry_df is None or st.sidebar.button("Refresh data"):
        with st.spinner("Loading telemetry…"):
            try:
                st.session_state.telemetry_df = load_telemetry(conn)
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.stop()
    try:
        conn.close()
    except Exception:
        pass

    df = st.session_state.telemetry_df
    if df is None or df.empty:
        st.info("No telemetry rows returned.")
        st.stop()

    ts_df = prepare_time_series(df)

    # ----- Chart -----
    st.subheader("Telemetry records by month")
    fig = build_time_series_chart(ts_df)
    st.plotly_chart(fig, use_container_width=True)

    # Optional: summary table and filters
    with st.expander("Data summary & filters"):
        col1, col2 = st.columns(2)
        with col1:
            sources = sorted(ts_df["ACTIVITY_SOURCE"].dropna().unique().tolist())
            selected_sources = st.multiselect("Activity source", sources, default=sources)
        with col2:
            products = sorted(ts_df["PRODUCT"].dropna().unique().tolist())
            selected_products = st.multiselect("Product", products, default=products)
        filtered = ts_df[
            ts_df["ACTIVITY_SOURCE"].isin(selected_sources) & ts_df["PRODUCT"].isin(selected_products)
        ]
        if not filtered.empty:
            st.plotly_chart(build_time_series_chart(filtered), use_container_width=True)
        st.dataframe(ts_df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
