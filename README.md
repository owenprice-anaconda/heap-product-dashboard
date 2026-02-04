# Heap Product Dashboard

Web app that authenticates to Snowflake (external browser SSO), caches the token, and shows an interactive time series of telemetry data.

## Setup and run (Pixi)

This project is configured as a [Pixi](https://pixi.sh) project. Install [pixi](https://pixi.sh/latest/getting_started/installation/) then:

```bash
cd heap-product-dashboard
pixi install
pixi run run
```

Or in one step: `pixi run run` (pixi installs the environment on first run if needed).

## Alternative: venv + pip

```bash
cd heap-product-dashboard
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
streamlit run app.py
```

Then:

1. Enter your **Snowflake username** and click **Connect**. A browser window will open for SSO; complete login there.
2. The connector caches the token (e.g. for ~4 hours) so you can reconnect without logging in again.
3. The dashboard loads and shows an interactive time series of records by month (by `activity_source` and `product`). Use the legend and filters in the expander to narrow the view.

## Deployment (health endpoint)

For deployment, use the proxy server that exposes a health endpoint and forwards traffic to Streamlit:

```bash
pixi run start
```

- Listens on `PORT` (default 8080).
- **Health check:** `GET /health` returns `200` and `{"status": "ok"}`.
- All other paths are proxied to Streamlit.

## Details

- **Connection**: Uses `ANALYTICS.INTERMEDIATE`, warehouse `default`, account `jfb46703.us-east-1`, `authenticator=externalbrowser`.
- **Token cache**: `client_request_mfa_token=True` so the Snowflake Python connector caches the MFA token on disk for reuse.
- **Chart**: Plotly time series of `stg_conda_unified_telemetry` aggregated by year/month, `activity_source`, and `product`.
