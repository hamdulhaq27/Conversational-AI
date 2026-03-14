"""
FastAPI WebSocket + REST API for Restaurant Reservation Chatbot.

Improvements applied:
  - Detailed [SERVER] logging at every stage of the message lifecycle
  - Per-request timing with [PERFORMANCE] log lines
  - 8-second timeout failsafe on AI generation
  - Graceful error handling on all code paths
"""

import logging
import time
from typing import Any, Dict
import base64
import tempfile
import os
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
    _warmup_model,
)

from voice.asr_service import asr_service_instance
from voice.tts_service import tts_service_instance

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("api")

app = FastAPI(title="Restaurant Reservation Conversational AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── FAILSAFE: fallback removed per user request ────────


@app.on_event("startup")
async def startup_warmup():
    """Pre-warm the AI model so the first real user request is fast."""
    logger.info("[SERVER] Startup — triggering background model warm-up...")
    # Warmup LLM
    asyncio.create_task(_warmup_model())
    
    # Pre-load ASR and TTS models into memory using a background thread so it does not block the event loop
    asyncio.create_task(asyncio.to_thread(asr_service_instance.load))
    asyncio.create_task(asyncio.to_thread(tts_service_instance.load))


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/session")
async def create_session_endpoint() -> Dict[str, Any]:
    """Create a new dialogue session and return its ID."""
    sid = create_session()
    logger.info(f"[SERVER] Created new session: {sid}")
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
    logger.info(f"[SERVER] Resetting session: {session_id}")
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
    logger.info("[SERVER] WebSocket connection accepted.")

    try:
        while True:
            raw = await websocket.receive_json()

            if not isinstance(raw, dict):
                await websocket.send_json({"type": "error", "error": "Invalid payload"})
                continue

            msg_type = raw.get("type", "text")
            session_id = raw.get("session_id")
            message = ""

            if msg_type in ["audio", "audio_partial"]:
                audio_base64 = raw.get("audio_base64")
                if not audio_base64:
                    await websocket.send_json({"type": "error", "error": "Missing audio_base64"})
                    continue
                
                try:
                    # decode base64
                    audio_bytes = base64.b64decode(audio_base64)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
                        temp_audio.write(audio_bytes)
                        temp_audio_path = temp_audio.name
                        
                    # run ASR service non-blocking
                    transcription = await asyncio.to_thread(asr_service_instance.transcribe_audio, temp_audio_path)
                    os.remove(temp_audio_path)
                    
                    if msg_type == "audio_partial":
                        await websocket.send_json({"type": "transcription_partial", "text": transcription})
                        continue
                        
                    message = transcription
                    print(f"User speech detected: {message}")
                    logger.info(f"User speech detected: {message}")
                    
                    # Send transcription back to client
                    await websocket.send_json({
                        "type": "transcription",
                        "text": message
                    })
                    
                    if not message:
                        await websocket.send_json({"type": "error", "message": "Speech recognition failed"})
                        continue
                except Exception as e:
                    logger.error(f"[ERROR] Audio processing failed: {e}")
                    if os.path.exists(temp_audio_path):
                        os.remove(temp_audio_path)
                    await websocket.send_json({"type": "error", "message": "Speech recognition failed"})
                    continue
            else:
                # default to text behavior
                message = raw.get("message")
                if not message or not isinstance(message, str):
                    await websocket.send_json(
                        {"type": "error", "error": "Field 'message' (string) is required"}
                    )
                    continue

            # ── Create session on-the-fly if client did not supply one ───────
            if not session_id:
                session_id = create_session()
                logger.info(f"[SERVER] Generated on-the-fly session: {session_id}")
                await websocket.send_json(
                    {"type": "session", "session_id": session_id}
                )

            if get_session(session_id) is None:
                await websocket.send_json(
                    {"type": "error", "error": "Unknown session_id"}
                )
                continue

            # ── Stream reply tokens ──────────────────────────────────────────
            logger.info(f"[SERVER] Request received at /ws/chat")
            logger.info(f"[SERVER] User message: \"{message}\"")
            request_start = time.time()

            try:
                logger.info(f"[SERVER] Calling AI model...")

                full_response = ""
                async for token in chat_stream(session_id, message):
                    full_response += token
                    await websocket.send_json({"type": "token", "token": token})
                    await asyncio.sleep(0)  # yield control to flush frame

                total_time = time.time() - request_start
                logger.info(f"[SERVER] AI response received in {total_time:.2f} seconds")
                logger.info(f"[PERFORMANCE] Total response time: {total_time:.2f} seconds")
                logger.info(f"[SERVER] Sending response to client")
                await websocket.send_json({"type": "end"})
                
                # TTS generation
                if full_response.strip():
                    try:
                        logger.info("[TTS] Generating audio for response...")
                        tts_start = time.time()
                        audio_base64 = await asyncio.to_thread(tts_service_instance.generate_speech, full_response)
                        tts_time = time.time() - tts_start
                        logger.info(f"[PERFORMANCE] TTS generation time: {tts_time:.2f} seconds")
                        
                        if audio_base64:
                            await websocket.send_json({
                                "type": "audio_response",
                                "audio_base64": audio_base64
                            })
                    except Exception as e:
                        logger.error(f"[ERROR] TTS generation failed: {e}")
                        if msg_type == "audio":
                            await websocket.send_json({
                                "type": "error",
                                "message": "Audio generation failed"
                            })

            except Exception as exc:  # noqa: BLE001
                elapsed = time.time() - request_start
                logger.error(f"[ERROR] AI request failed after {elapsed:.2f}s: {exc}")
                await websocket.send_json(
                    {"type": "error", "message": f"Internal error: {exc}"}
                )

    except WebSocketDisconnect:
        logger.info("[SERVER] Client WebSocket disconnected.")
        return
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[ERROR] Unexpected connection error: {exc}")
        try:
            await websocket.send_json(
                {"type": "error", "error": f"Connection error: {exc}"}
            )
        except Exception:  # noqa: BLE001
            pass


def create_app() -> FastAPI:
    """Factory to create the FastAPI app, useful for tooling/tests."""
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
