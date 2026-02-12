"""
SnowSnake – Snowflake auth (key-pair or SSO) + package usage telemetry.
Run locally: streamlit run app.py

Deployment (key-pair): SNOWFLAKE_PRIVATE_KEY or SNOWFLAKE_PRIVATE_KEY_PATH; user LABS, warehouse LABS.
Local (SSO): set SNOWFLAKE_USE_SSO=1, then enter your username in the app; warehouse default.
"""
import json
import os
import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import snowflake.connector
from cryptography.hazmat.primitives import serialization

PACKAGE_LIST_CSV = os.path.join(os.path.dirname(__file__), "package_list.csv")
SAVED_GROUPS_PATH = os.path.join(os.path.dirname(__file__), "saved_groups.json")
GROUP_PREFIX = "📁 "  # Icon prefix for group names in the selector


def _load_saved_groups() -> dict[str, list[str]]:
    """Load saved package groups from JSON file (persists across launches)."""
    if not os.path.isfile(SAVED_GROUPS_PATH):
        return {}
    try:
        with open(SAVED_GROUPS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {k: list(v) for k, v in data.items() if isinstance(v, list)}
    except Exception:
        return {}


def _save_saved_groups(groups: dict[str, list[str]]) -> None:
    """Write saved package groups to JSON file."""
    with open(SAVED_GROUPS_PATH, "w", encoding="utf-8") as f:
        json.dump(groups, f, indent=2)


def _resolve_selection_to_packages(selected: list[str], groups: dict[str, list[str]]) -> list[str]:
    """Expand group choices to package lists; return flat, order-preserving, deduped package list."""
    packages = []
    for s in selected:
        if s.startswith(GROUP_PREFIX):
            group_name = s[len(GROUP_PREFIX) :].strip()
            packages.extend(groups.get(group_name, []))
        else:
            packages.append(s)
    return list(dict.fromkeys(packages))  # preserve order, remove duplicates


@st.cache_data
def _load_package_list() -> list[str]:
    """Load and return sorted package names from package_list.csv (cached)."""
    df = pd.read_csv(PACKAGE_LIST_CSV)
    # Support column named 'package_name' or first column
    col = "package_name" if "package_name" in df.columns else df.columns[0]
    return sorted(df[col].dropna().astype(str).str.strip().unique().tolist())


def _conn_params(warehouse_default: str = "LABS"):
    """Connection params; warehouse default is LABS for key-pair, default for token auth."""
    return {
        "account": os.environ.get("SNOWFLAKE_ACCOUNT", "jfb46703.us-east-1"),
        "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE", warehouse_default),
        "database": os.environ.get("SNOWFLAKE_DATABASE", "ANALYTICS"),
        "schema": os.environ.get("SNOWFLAKE_SCHEMA", "INTERMEDIATE"),
    }

# Package pattern is bound as %(package_pattern)s; from-date fixed when detailed telemetry started.
PACKAGE_USERS_QUERY = """
SELECT
  DATE_TRUNC('MONTH', ACTIVITY_TS) AS ACTIVITY_MONTH,
  COUNT(DISTINCT USER_ID) AS DISTINCT_USERS
FROM ANALYTICS.INTERMEDIATE.STG_CONDA_UNIFIED_TELEMETRY
WHERE ACTIVITY_SOURCE != 'dotcloud_request_logs'
  AND ACTIVITY_TS >= '2025-05-01'
  AND (
    REGEXP_LIKE(LOWER(metadata:ClientRequestURI::STRING), %(package_pattern)s)
    OR REGEXP_LIKE(LOWER(metadata:RequestHeaders:"anaconda-telemetry-install"::STRING), %(package_pattern)s)
    OR REGEXP_LIKE(LOWER(metadata:RequestHeaders:"anaconda-telemetry-packages"::STRING), %(package_pattern)s)
  )
GROUP BY ACTIVITY_MONTH
ORDER BY ACTIVITY_MONTH
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


def _use_sso() -> bool:
    """True when local SSO (external browser) auth is requested."""
    v = os.environ.get("SNOWFLAKE_USE_SSO", "").strip().lower()
    auth = os.environ.get("SNOWFLAKE_AUTH", "").strip().lower()
    return v in ("1", "true", "yes") or auth == "externalbrowser"


def get_connection_sso(username: str):
    """Connect to Snowflake via SSO (external browser). Warehouse defaults to default."""
    return snowflake.connector.connect(
        user=username,
        authenticator="externalbrowser",
        client_request_mfa_token=True,
        **_conn_params(warehouse_default="default"),
    )


def get_connection():
    """Connect to Snowflake using key-pair authentication (deployment)."""
    user = os.environ.get("SNOWFLAKE_USER", "LABS")
    private_key = _load_private_key()
    return snowflake.connector.connect(
        user=user,
        private_key=private_key,
        **_conn_params(warehouse_default="LABS"),
    )


def build_package_pattern(packages: list[str]) -> str:
    """Build a regex pattern for whole-token match of package names (word boundaries)."""
    if not packages:
        return ""
    escaped = "|".join(re.escape(p) for p in packages)
    return r"\b(" + escaped + r")\b"


def load_package_users(conn, package_pattern: str) -> pd.DataFrame:
    """Run the package-users query with bound pattern; return DataFrame with ACTIVITY_MONTH, DISTINCT_USERS."""
    return pd.read_sql(
        PACKAGE_USERS_QUERY,
        conn,
        params={"package_pattern": package_pattern},
    )


def build_users_chart(
    df: pd.DataFrame,
    package_label: str,
    chart_type: str = "bar",
    month_min: pd.Timestamp | None = None,
    month_max: pd.Timestamp | None = None,
) -> go.Figure:
    """Time series: month on x, distinct users on y. chart_type is 'bar' or 'line'. Optional month filter."""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data to display", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    df = df.copy()
    df["activity_date"] = pd.to_datetime(df["ACTIVITY_MONTH"])
    if month_min is not None:
        df = df[df["activity_date"] >= month_min]
    if month_max is not None:
        df = df[df["activity_date"] <= month_max]
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data in selected month range", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig
    title = f"Distinct users by month — {package_label}"
    labels = {"activity_date": "Month", "DISTINCT_USERS": "Distinct users"}
    if chart_type == "bar":
        fig = px.bar(
            df,
            x="activity_date",
            y="DISTINCT_USERS",
            title=title,
            labels=labels,
            text=df["DISTINCT_USERS"],
            text_auto=",.0f",
        )
        fig.update_traces(
            textposition="inside",
            insidetextanchor="end",
            textfont=dict(color="white", size=12),
            marker=dict(color="#2563eb", line=dict(width=1, color="rgba(0,0,0,0.2)")),
        )
        # Ensure legibility on light and dark: white text on solid bar with subtle border
        fig.update_layout(uniformtext_minsize=10, uniformtext_mode="hide")
    else:
        fig = px.line(
            df,
            x="activity_date",
            y="DISTINCT_USERS",
            title=title,
            labels=labels,
        )
    fig.update_layout(
        xaxis_title="Month",
        yaxis_title="Distinct users",
        hovermode="x unified",
        template="plotly_white",
        height=500,
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#31333F"),
        xaxis=dict(gridcolor="rgba(128,128,128,0.2)"),
        yaxis=dict(gridcolor="rgba(128,128,128,0.2)"),
    )
    return fig


def main():
    st.set_page_config(page_title="SnowSnake", page_icon="📊", layout="wide")
    st.title("SnowSnake")
    st.caption("Package usage: distinct users by month (conda telemetry)")

    if "conn" not in st.session_state:
        st.session_state.conn = None
    if "snowflake_user" not in st.session_state:
        st.session_state.snowflake_user = None
    if "package_users_df" not in st.session_state:
        st.session_state.package_users_df = None
    if "selected_packages" not in st.session_state:
        st.session_state.selected_packages = []
    if "resolved_packages" not in st.session_state:
        st.session_state.resolved_packages = []

    # ----- SSO (local): show login form until connected -----
    if _use_sso():
        if st.session_state.conn is None:
            username_from_env = os.environ.get("SNOWFLAKE_USER")
            with st.form("sso_login"):
                username = st.text_input(
                    "Snowflake username",
                    value=username_from_env or "",
                    placeholder="your.email@company.com",
                )
                submit = st.form_submit_button("Connect (opens browser for SSO)")
                if submit and username:
                    with st.spinner("Opening browser for Snowflake SSO…"):
                        try:
                            conn = get_connection_sso(username.strip())
                            st.session_state.conn = conn
                            st.session_state.snowflake_user = username.strip()
                            st.success("Connected.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Connection failed: {e}")
            st.stop()
        conn = st.session_state.conn
        st.sidebar.success(f"Connected as **{st.session_state.snowflake_user}**")
        if st.sidebar.button("Disconnect"):
            try:
                if st.session_state.conn:
                    st.session_state.conn.close()
            except Exception:
                pass
            st.session_state.conn = None
            st.session_state.snowflake_user = None
            st.session_state.package_users_df = None
            st.session_state.selected_packages = []
            st.session_state.resolved_packages = []
            st.rerun()
    else:
        # Key-pair: conn created on demand when user submits
        conn = None

    # ----- Saved groups (persisted to file) -----
    saved_groups = _load_saved_groups()
    group_options = [GROUP_PREFIX + name for name in sorted(saved_groups.keys())]

    # ----- Package selector and Submit -----
    st.subheader("Select packages or groups")
    try:
        package_list = _load_package_list()
    except Exception as e:
        st.error(f"Could not load package_list.csv: {e}")
        st.stop()
    # Groups at top (with icon), then packages
    all_options = group_options + package_list
    selected = st.multiselect(
        "Choose package groups and/or individual packages",
        options=all_options,
        default=st.session_state.selected_packages,
        key="package_multiselect",
    )
    packages = _resolve_selection_to_packages(selected, saved_groups) if selected else []

    # Save current selection as a named group
    with st.expander("Save selection as a group"):
        group_name = st.text_input("Group name", placeholder="e.g. Computer vision")
        if st.button("Save group"):
            if not group_name or not group_name.strip():
                st.warning("Enter a group name.")
            elif not packages:
                st.warning("Select at least one package or group to save.")
            else:
                saved_groups[group_name.strip()] = packages
                _save_saved_groups(saved_groups)
                st.success(f"Saved group **{group_name.strip()}** ({len(packages)} packages).")
                st.rerun()

    submit = st.button("Submit")
    if submit:
        if not packages:
            st.error("Select at least one package or group.")
        else:
            pattern = build_package_pattern(packages)
            if _use_sso():
                conn = st.session_state.conn
            else:
                try:
                    conn = get_connection()
                except ValueError as e:
                    st.error(f"Configuration error: {e}")
                    st.stop()
                except Exception as e:
                    st.error(f"Connection failed: {e}")
                    st.stop()
            with st.spinner("Querying distinct users by month…"):
                try:
                    df = load_package_users(conn, pattern)
                    st.session_state.package_users_df = df
                    st.session_state.selected_packages = selected  # keep display selection (groups + packages)
                    st.session_state.resolved_packages = packages  # actual list used for query
                    if not _use_sso() and conn:
                        try:
                            conn.close()
                        except Exception:
                            pass
                    st.success(f"Loaded data for: {', '.join(packages)}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Query failed: {e}")

    # ----- Chart (after a successful submit) -----
    df = st.session_state.package_users_df
    if df is not None and not df.empty:
        resolved = st.session_state.get("resolved_packages") or []
        package_label = ", ".join(resolved[:8]) + ("…" if len(resolved) > 8 else "")

        chart_type = st.radio(
            "Chart type",
            options=["bar", "line"],
            format_func=lambda x: "Bar chart" if x == "bar" else "Line chart",
            index=0,
            key="chart_type_radio",
            horizontal=True,
        )

        # Month filter: from / to
        df_dates = df.copy()
        df_dates["activity_date"] = pd.to_datetime(df_dates["ACTIVITY_MONTH"])
        months_available = sorted(df_dates["activity_date"].dt.to_period("M").astype(str).unique().tolist())
        if months_available:
            col_from, col_to, _ = st.columns([1, 1, 2])
            with col_from:
                month_from = st.selectbox(
                    "From month",
                    options=months_available,
                    index=0,
                    key="month_from",
                )
            with col_to:
                month_to = st.selectbox(
                    "To month",
                    options=months_available,
                    index=len(months_available) - 1,
                    key="month_to",
                )
            month_min = pd.Timestamp(min(month_from, month_to) + "-01")
            month_max = pd.Timestamp(max(month_from, month_to) + "-01")
        else:
            month_min = month_max = None

        fig = build_users_chart(df, package_label, chart_type=chart_type, month_min=month_min, month_max=month_max)
        st.plotly_chart(fig, use_container_width=True, key="package_users_chart")
        with st.expander("Data table"):
            if month_min is not None or month_max is not None:
                df_filtered = df_dates
                if month_min is not None:
                    df_filtered = df_filtered[df_filtered["activity_date"] >= month_min]
                if month_max is not None:
                    df_filtered = df_filtered[df_filtered["activity_date"] <= month_max]
                st.dataframe(df_filtered[["ACTIVITY_MONTH", "DISTINCT_USERS"]], use_container_width=True, hide_index=True)
            else:
                st.dataframe(df, use_container_width=True, hide_index=True)
    elif df is not None and df.empty:
        st.info("No rows returned for the selected packages.")
    else:
        st.info("Select one or more packages or groups and click **Submit** to see distinct users by month.")


if __name__ == "__main__":
    main()
