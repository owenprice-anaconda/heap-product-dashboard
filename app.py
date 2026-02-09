"""
SnowSnake – Snowflake key-pair auth + interactive telemetry time series.
Run locally: streamlit run app.py
Uses RSA key-pair auth; set SNOWFLAKE_USER (default LABS) and either SNOWFLAKE_PRIVATE_KEY
or SNOWFLAKE_PRIVATE_KEY_PATH. Optional: SNOWFLAKE_PRIVATE_KEY_PASSPHRASE if key is encrypted.
"""
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import snowflake.connector
from cryptography.hazmat.primitives import serialization

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


def _load_private_key():
    """Load PEM private key from SNOWFLAKE_PRIVATE_KEY (PEM string) or SNOWFLAKE_PRIVATE_KEY_PATH (file)."""
    path = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH")
    pem_content = os.environ.get("SNOWFLAKE_PRIVATE_KEY")
    if path:
        with open(path, "rb") as f:
            pem_bytes = f.read()
    elif pem_content:
        # Support newlines as literal \n (e.g. from single-line env var)
        pem_bytes = pem_content.strip().replace("\\n", "\n").encode("utf-8")
    else:
        raise ValueError(
            "Set SNOWFLAKE_PRIVATE_KEY (PEM string, use \\n for newlines) or "
            "SNOWFLAKE_PRIVATE_KEY_PATH (path to PEM file)"
        )
    passphrase = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
    password = passphrase.encode("utf-8") if passphrase else None
    return serialization.load_pem_private_key(pem_bytes, password=password)


def get_connection():
    """Connect to Snowflake using key-pair authentication (LABS service account)."""
    user = os.environ.get("SNOWFLAKE_USER", "LABS")
    private_key = _load_private_key()
    return snowflake.connector.connect(
        user=user,
        private_key=private_key,
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
    st.set_page_config(page_title="SnowSnake", page_icon="📊", layout="wide")
    st.title("SnowSnake")
    st.caption("Snowflake telemetry time series")

    if "telemetry_df" not in st.session_state:
        st.session_state.telemetry_df = None

    # ----- Connect and load data -----
    try:
        conn = get_connection()
    except ValueError as e:
        st.error(f"Configuration error: {e}. Set SNOWFLAKE_USER (optional, default LABS) and SNOWFLAKE_PRIVATE_KEY or SNOWFLAKE_PRIVATE_KEY_PATH.")
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
