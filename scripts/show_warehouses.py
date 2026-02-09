#!/usr/bin/env python3
"""
Connect as LABS with key-pair auth and run SHOW WAREHOUSES.
Use this to discover which warehouse name to set for SNOWFLAKE_WAREHOUSE.

  export SNOWFLAKE_USER=LABS
  export SNOWFLAKE_PRIVATE_KEY_PATH=../snowflake_private_key.pem
  export SNOWFLAKE_WAREHOUSE=LABS   # optional; LABS is the default
  python show_warehouses.py
"""
import os
import sys

# Allow importing app's auth helpers when run from project root or scripts/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import snowflake.connector
from cryptography.hazmat.primitives import serialization


def _load_private_key():
    path = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH")
    pem_content = os.environ.get("SNOWFLAKE_PRIVATE_KEY")
    if path:
        with open(path, "rb") as f:
            pem_bytes = f.read()
    elif pem_content:
        pem_bytes = pem_content.strip().replace("\\n", "\n").encode("utf-8")
    else:
        print("Set SNOWFLAKE_PRIVATE_KEY or SNOWFLAKE_PRIVATE_KEY_PATH", file=sys.stderr)
        sys.exit(1)
    passphrase = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
    password = passphrase.encode("utf-8") if passphrase else None
    return serialization.load_pem_private_key(pem_bytes, password=password)


def main():
    user = os.environ.get("SNOWFLAKE_USER", "LABS")
    warehouse = os.environ.get("SNOWFLAKE_WAREHOUSE", "LABS")
    conn_params = {
        "account": os.environ.get("SNOWFLAKE_ACCOUNT", "jfb46703.us-east-1"),
        "warehouse": warehouse,
        "database": os.environ.get("SNOWFLAKE_DATABASE", "ANALYTICS"),
        "schema": os.environ.get("SNOWFLAKE_SCHEMA", "INTERMEDIATE"),
    }
    print(f"Connecting as {user} with warehouse={warehouse} ...", file=sys.stderr)
    try:
        conn = snowflake.connector.connect(
            user=user,
            private_key=_load_private_key(),
            **conn_params,
        )
    except Exception as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        cur = conn.cursor()
        cur.execute("SHOW WAREHOUSES")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        # Print as table (simple)
        col_widths = [max(len(str(c)), 4) for c in cols]
        for i, r in enumerate(rows):
            for j, v in enumerate(r):
                col_widths[j] = max(col_widths[j], len(str(v)) if v else 4)
        fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
        print(fmt.format(*cols))
        print("-" * (sum(col_widths) + 2 * (len(cols) - 1)))
        for r in rows:
            print(fmt.format(*[str(v) if v is not None else "" for v in r]))
        print(f"\n({len(rows)} warehouse(s). Use the 'name' column for SNOWFLAKE_WAREHOUSE.)", file=sys.stderr)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
