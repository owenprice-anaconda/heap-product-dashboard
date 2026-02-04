"""
FastAPI app: GET /health and reverse proxy to Streamlit (HTTP + WebSocket).
"""
import os
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
import httpx
import websockets

STREAMLIT_PORT = os.environ.get("STREAMLIT_INTERNAL_PORT", "8501")
STREAMLIT_URL = f"http://127.0.0.1:{STREAMLIT_PORT}"
STREAMLIT_WS_URL = f"ws://127.0.0.1:{STREAMLIT_PORT}"

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_http(path: str, request: Request):
    url = f"{STREAMLIT_URL}/{path}"
    async with httpx.AsyncClient() as client:
        body = await request.body()
        headers = dict(request.headers)
        headers.pop("host", None)
        resp = await client.request(
            request.method,
            url,
            content=body,
            headers=headers,
            timeout=60.0,
        )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
        )


@app.websocket("/{path:path}")
async def proxy_ws(websocket: WebSocket, path: str):
    await websocket.accept()
    backend_ws_url = f"{STREAMLIT_WS_URL}/{path}"
    try:
        async with websockets.connect(backend_ws_url) as backend:
            async def forward_from_backend():
                try:
                    async for message in backend:
                        await websocket.send_bytes(message)
                except Exception:
                    pass
            async def forward_from_client():
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        await backend.send(data)
                except WebSocketDisconnect:
                    pass
                except Exception:
                    pass
            import asyncio
            await asyncio.gather(
                asyncio.create_task(forward_from_backend()),
                asyncio.create_task(forward_from_client()),
            )
    except Exception:
        pass
    try:
        await websocket.close()
    except Exception:
        pass
