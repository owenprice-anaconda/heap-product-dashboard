"""
Entrypoint that serves GET /health and proxies all other traffic to Streamlit.
Run: python server.py  (or pixi run start)
Uses PORT env var (default 8080). Health check: GET /health
"""
import os
import subprocess
import sys
import time

# Start Streamlit in a subprocess on an internal port
STREAMLIT_PORT = os.environ.get("STREAMLIT_INTERNAL_PORT", "8501")
STREAMLIT_ADDRESS = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8080"))

def main():
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port", STREAMLIT_PORT,
            "--server.address", STREAMLIT_ADDRESS,
            "--server.headless", "true",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for Streamlit to be ready
    for _ in range(30):
        try:
            import urllib.request
            urllib.request.urlopen(f"http://{STREAMLIT_ADDRESS}:{STREAMLIT_PORT}/", timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    else:
        proc.terminate()
        sys.exit(1)

    # Run proxy with health endpoint
    from proxy import app
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")

if __name__ == "__main__":
    main()
