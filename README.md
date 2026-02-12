# SnowSnake

Web app that connects to Snowflake using RSA key-pair authentication (LABS service account) and shows an interactive time series of telemetry data. No login page—the app goes straight to the dashboard.

## Configuration

Set these environment variables in your deployment (or shell):

| Variable | Required | Description |
|----------|----------|-------------|
| **`SNOWFLAKE_USER`** | No | Snowflake user (default: `LABS`, the service account). |
| **`SNOWFLAKE_WAREHOUSE`** | No | Warehouse to use (default: `LABS`). Override with this env var if needed. |
| **`SNOWFLAKE_DATABASE`** | No | Database (default: `ANALYTICS`). |
| **`SNOWFLAKE_SCHEMA`** | No | Schema (default: `INTERMEDIATE`). |
| **`SNOWFLAKE_PRIVATE_KEY`** | One of these | Full PEM private key. Use `\n` for newlines if pasting as one line. |
| **`SNOWFLAKE_PRIVATE_KEY_PATH`** | One of these | Path to a file containing the PEM private key (e.g. a mounted secret). |
| **`SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`** | No | Passphrase if the private key is encrypted. |
| **`SNOWFLAKE_USE_SSO`** | Local only | Set to `1` (or `true`/`yes`) to use SSO (external browser) for local testing. |
| **`SNOWFLAKE_AUTH`** | Local only | Set to `externalbrowser` as an alternative to `SNOWFLAKE_USE_SSO=1`. |

**Deployment (key-pair):** Set **`SNOWFLAKE_PRIVATE_KEY`** or **`SNOWFLAKE_PRIVATE_KEY_PATH`**. User defaults to `LABS`, warehouse to `LABS`.

**Local testing (SSO):** Set **`SNOWFLAKE_USE_SSO=1`**. Run the app; enter your Snowflake username and click Connect. A browser window opens for SSO. Warehouse defaults to `default`. Do not set the private key env vars.

If you see "No active warehouse selected", set **`SNOWFLAKE_WAREHOUSE`** to the correct warehouse name.

### Discovering warehouses (key-pair auth; no UI)

Key-pair auth is used by the Python connector, not the Snowflake web UI. To list warehouses available to the LABS user, run the helper script (it connects as LABS with your key and runs `SHOW WAREHOUSES`). First try with warehouse `DEFAULT` (many accounts have one):

```bash
export SNOWFLAKE_USER=LABS
export SNOWFLAKE_PRIVATE_KEY_PATH=./snowflake_private_key.pem
export SNOWFLAKE_WAREHOUSE=LABS
pixi run show-warehouses
```

If you get "No active warehouse", try another warehouse name if you know one, or ask the data platform team. The script prints a table; use the **name** column value as `SNOWFLAKE_WAREHOUSE`.

### Local testing (SSO + default warehouse)

To run the dashboard locally with your personal Snowflake user and the `default` warehouse:

1. Set **`SNOWFLAKE_USE_SSO=1`**. Do **not** set `SNOWFLAKE_PRIVATE_KEY` or `SNOWFLAKE_PRIVATE_KEY_PATH`.
2. Run the app; enter your Snowflake username and click **Connect**. A browser window opens for SSO; complete login there.
3. The app uses warehouse `default` and caches the session.

```bash
export SNOWFLAKE_USE_SSO=1
pixi run run
```

Optional: set **`SNOWFLAKE_USER`** in the environment to pre-fill the username in the login form.

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
