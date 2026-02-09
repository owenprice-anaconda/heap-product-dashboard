# SnowSnake

Web app that connects to Snowflake using RSA key-pair authentication (LABS service account) and shows an interactive time series of telemetry data. No login page—the app goes straight to the dashboard.

## Configuration

Set these environment variables in your deployment (or shell):

| Variable | Required | Description |
|----------|----------|-------------|
| **`SNOWFLAKE_USER`** | No | Snowflake user (default: `LABS`, the service account). |
| **`SNOWFLAKE_PRIVATE_KEY`** | One of these | Full PEM private key. Use `\n` for newlines if pasting as one line. |
| **`SNOWFLAKE_PRIVATE_KEY_PATH`** | One of these | Path to a file containing the PEM private key (e.g. a mounted secret). |
| **`SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`** | No | Passphrase if the private key is encrypted. |

You must provide the private key either as **`SNOWFLAKE_PRIVATE_KEY`** (PEM string) or **`SNOWFLAKE_PRIVATE_KEY_PATH`** (path to PEM file). The public key is registered in Snowflake for the LABS user by the data platform team.

## Setup and run (Pixi)

This project is configured as a [Pixi](https://pixi.sh) project. Install [pixi](https://pixi.sh/latest/getting_started/installation/) then:

```bash
cd heap-product-dashboard
pixi install
export SNOWFLAKE_USER=LABS
export SNOWFLAKE_PRIVATE_KEY_PATH=/path/to/your-private-key.pem
# or: export SNOWFLAKE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n..."
pixi run run
```

## Alternative: venv + pip

```bash
cd heap-product-dashboard
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
export SNOWFLAKE_USER=LABS
export SNOWFLAKE_PRIVATE_KEY_PATH=/path/to/your-private-key.pem
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

- **Connection**: Uses `ANALYTICS.INTERMEDIATE`, warehouse `default`, account `jfb46703.us-east-1`. Authentication via RSA key-pair (LABS service account); private key from `SNOWFLAKE_PRIVATE_KEY` or `SNOWFLAKE_PRIVATE_KEY_PATH`.
- **Chart**: Plotly time series of `stg_conda_unified_telemetry` aggregated by year/month, `activity_source`, and `product`.
