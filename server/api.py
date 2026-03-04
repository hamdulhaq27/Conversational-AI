import logging
from typing import Any, Dict

import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from conversation_manager import (
    create_session,
    get_session,
    reset_session,
    session_debug_info,
    chat_stream,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("api")

app = FastAPI(title="Restaurant Reservation Conversational AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://conversational-ai-gules.vercel.app/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/session")
async def create_session_endpoint() -> Dict[str, Any]:
    """Create a new dialogue session and return its ID."""
    sid = create_session()
    logger.info(f"Created new session: {sid}")
    return {"session_id": sid}


@app.get("/session/{session_id}")
async def get_session_info(session_id: str) -> Dict[str, Any]:
    """Return debug information for a session (safe for tools like Postman)."""
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_debug_info(session_id)


@app.post("/session/{session_id}/reset")
async def reset_session_endpoint(session_id: str) -> Dict[str, Any]:
    """Reset an existing session back to its initial state."""
    logger.info(f"Resetting session: {session_id}")
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    reset_session(session_id)
    return {"session_id": session_id, "reset": True}


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    """
    WebSocket chat endpoint.

    Contract:
      • Client sends JSON messages: {"session_id": "...", "message": "text"}
        - If session_id is null/missing, a new session is created and sent back.
      • Server streams back JSON frames:
          {"type": "session", "session_id": "..."}
          {"type": "token", "token": "partial text"}
          {"type": "end"}           # end of single assistant reply
          {"type": "error", "error": "description"}
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted.")

    try:
        while True:
            raw = await websocket.receive_json()

            if not isinstance(raw, dict):
                await websocket.send_json({"type": "error", "error": "Invalid payload"})
                continue

            message = raw.get("message")
            session_id = raw.get("session_id")

            if not message or not isinstance(message, str):
                await websocket.send_json(
                    {"type": "error", "error": "Field 'message' (string) is required"}
                )
                continue

            # Create session on-the-fly if client did not supply one
            if not session_id:
                session_id = create_session()
                logger.info(f"Generated on-the-fly session: {session_id}")
                await websocket.send_json(
                    {"type": "session", "session_id": session_id}
                )

            if get_session(session_id) is None:
                await websocket.send_json(
                    {"type": "error", "error": "Unknown session_id"}
                )
                continue

            # Stream reply tokens from conversation_manager.chat_stream
            logger.info(f"[{session_id}] Processing user message: '{message}'")
            try:
                # Use async for to prevent blocking the FastAPI event loop
                async for token in chat_stream(session_id, message):
                    await websocket.send_json({"type": "token", "token": token})
                    # Await a tiny sleep to force flush out the websocket frame if needed
                    await asyncio.sleep(0)

                logger.info(f"[{session_id}] Finished streaming response.")
                await websocket.send_json({"type": "end"})
            except Exception as exc:  # noqa: BLE001
                logger.error(f"[{session_id}] Internal error during generation: {exc}")
                await websocket.send_json(
                    {"type": "error", "error": f"Internal error: {exc}"}
                )
    except WebSocketDisconnect:
        logger.info("Client WebSocket disconnected.")
        return
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Unexpected connection error: {exc}")
        # Unexpected server-side error; best-effort notification.
        try:
            await websocket.send_json(
                {"type": "error", "error": f"Connection error: {exc}"}
            )
        except Exception:  # noqa: BLE001
            pass


def create_app() -> FastAPI:
    """
    Factory to create the FastAPI app, useful for tooling/tests.
    """
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )

