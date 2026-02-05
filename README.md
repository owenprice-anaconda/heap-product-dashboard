# Heap Product Dashboard

Web app that connects to Snowflake using a programmatic access token and shows an interactive time series of telemetry data. No login page—the app goes straight to the dashboard.

## Configuration

Set these environment variables (e.g. in your deployment or shell):

- **`SNOWFLAKE_USER`** – Snowflake username that the token belongs to.
- **`SNOWFLAKE_TOKEN`** – Snowflake programmatic access token (used as password).

## Setup and run (Pixi)

This project is configured as a [Pixi](https://pixi.sh) project. Install [pixi](https://pixi.sh/latest/getting_started/installation/) then:

```bash
cd heap-product-dashboard
pixi install
export SNOWFLAKE_USER=your_snowflake_username
export SNOWFLAKE_TOKEN=your_access_token
pixi run run
```

Or in one step: `pixi run run` (set `SNOWFLAKE_USER` and `SNOWFLAKE_TOKEN` in your environment first).

## Alternative: venv + pip

```bash
cd heap-product-dashboard
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
export SNOWFLAKE_USER=your_snowflake_username
export SNOWFLAKE_TOKEN=your_access_token
streamlit run app.py
```

The dashboard loads immediately and shows an interactive time series of records by month (by `activity_source` and `product`). Use the legend and filters in the expander to narrow the view.

## Deployment (health endpoint)

For deployment, use the proxy server that exposes a health endpoint and forwards traffic to Streamlit:

```bash
pixi run start
```

- Listens on `PORT` (default 8080).
- **Health check:** `GET /health` returns `200` and `{"status": "ok"}`.
- All other paths are proxied to Streamlit.

## Details

- **Connection**: Uses `ANALYTICS.INTERMEDIATE`, warehouse `default`, account `jfb46703.us-east-1`. Authentication via programmatic access token (`SNOWFLAKE_TOKEN` env var, used as password).
- **Chart**: Plotly time series of `stg_conda_unified_telemetry` aggregated by year/month, `activity_source`, and `product`.
