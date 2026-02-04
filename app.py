"""
Heap Product Dashboard – Snowflake auth + interactive telemetry time series.
Run locally: streamlit run app.py
"""
import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import snowflake.connector

# Fixed connection parameters (user provided at runtime)
CONN_PARAMS = {
    "account": "jfb46703.us-east-1",
    "warehouse": "default",
    "database": "ANALYTICS",
    "schema": "INTERMEDIATE",
    "authenticator": "externalbrowser",
}

TELEMETRY_QUERY = """
SELECT YEAR(activity_ts) AS activity_year, MONTH(ACTIVITY_TS) AS activity_month, activity_source, product, count(*) as recs
FROM stg_conda_unified_telemetry
GROUP BY 1, 2, 3, 4
ORDER BY 1, 2
"""


def get_connection(username: str):
    """Connect to Snowflake with external browser auth; token is cached by the connector."""
    return snowflake.connector.connect(
        user=username,
        **CONN_PARAMS,
        client_request_mfa_token=True,  # cache token for reuse (e.g. ~4h)
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

    # Session state for connection and cached username
    if "conn" not in st.session_state:
        st.session_state.conn = None
    if "snowflake_user" not in st.session_state:
        st.session_state.snowflake_user = None
    if "telemetry_df" not in st.session_state:
        st.session_state.telemetry_df = None

    # ----- Auth -----
    if st.session_state.conn is None:
        with st.form("login"):
            username = st.text_input("Snowflake username", placeholder="your.email@company.com")
            submit = st.form_submit_button("Connect (opens browser for SSO)")
            if submit and username:
                with st.spinner("Opening browser for Snowflake SSO…"):
                    try:
                        conn = get_connection(username.strip())
                        st.session_state.conn = conn
                        st.session_state.snowflake_user = username.strip()
                        st.success("Connected. Token is cached for later use.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Connection failed: {e}")
        st.stop()

    # Connected: show user and option to disconnect
    st.sidebar.success(f"Connected as **{st.session_state.snowflake_user}**")
    if st.sidebar.button("Disconnect"):
        try:
            if st.session_state.conn:
                st.session_state.conn.close()
        except Exception:
            pass
        st.session_state.conn = None
        st.session_state.snowflake_user = None
        st.session_state.telemetry_df = None
        st.rerun()

    # ----- Data -----
    conn = st.session_state.conn
    if st.session_state.telemetry_df is None or st.sidebar.button("Refresh data"):
        with st.spinner("Loading telemetry…"):
            try:
                st.session_state.telemetry_df = load_telemetry(conn)
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.stop()

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
