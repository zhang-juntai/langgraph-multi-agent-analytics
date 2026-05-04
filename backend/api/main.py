"""FastAPI application with a single product entry: WebSocket chat."""

from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.websocket.handler import websocket_chat

app = FastAPI(
    title="Enterprise Data Agent",
    description="WebSocket-only data analysis agent service.",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static/figures", StaticFiles(directory=str(OUTPUT_DIR)), name="figures")


@app.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """Run the P1 analysis graph for one chat session."""
    await websocket_chat(websocket, session_id)
