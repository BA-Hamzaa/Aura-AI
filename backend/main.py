"""
FastAPI Backend — the brain of the AI Meeting Assistant.
Exposes REST endpoints and WebSocket for real-time updates to the HUD overlay.
"""

import os
import sys
sys.stdout = open(os.devnull, "w")
sys.stderr = open(os.devnull, "w")
import json
import asyncio
import threading
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from gemini_client import GeminiClient
from transcription import TranscriptionEngine
from automation import parse_and_execute_actions, strip_action_tags, execute_command

load_dotenv()

# ─── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="Aura AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── State ────────────────────────────────────────────────────────────────────
api_key: Optional[str] = os.getenv("GEMINI_API_KEY", "")
gemini: Optional[GeminiClient] = None
transcription_engine: Optional[TranscriptionEngine] = None
transcript_log: list[str] = []
connected_clients: list[WebSocket] = []
transcription_active = False


def get_gemini() -> GeminiClient:
    global gemini, api_key
    if not api_key:
        raise HTTPException(status_code=401, detail="No API key configured. Please set your Gemini API key.")
    if gemini is None:
        gemini = GeminiClient(api_key)
    return gemini


# ─── WebSocket Broadcast ───────────────────────────────────────────────────────
async def broadcast(message: dict):
    """Send a JSON message to all connected WebSocket clients (the HUD)."""
    dead = []
    for ws in connected_clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_clients.remove(ws)


def broadcast_sync(message: dict):
    """Thread-safe broadcast — called from non-async threads."""
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.run_coroutine_threadsafe(broadcast(message), loop)


# ─── Transcription Callbacks ──────────────────────────────────────────────────
def on_transcript_text(text: str):
    global transcript_log
    transcript_log.append(text)
    if len(transcript_log) > 200:
        transcript_log = transcript_log[-200:]

    ai = gemini
    if ai:
        ai.update_transcript(text)

    broadcast_sync({"type": "transcript", "text": text})


def on_transcript_error(error: str):
    broadcast_sync({"type": "error", "text": error})


# ─── Models ───────────────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str

class RephraseRequest(BaseModel):
    text: str

class ApiKeyRequest(BaseModel):
    api_key: str

class MeetingContext(BaseModel):
    title: str
    platform: str

class ManualCommand(BaseModel):
    command: str   # e.g. "open_url", "search_google", "discord_send", etc.
    params: dict = {}


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "AI Meeting Assistant running", "api_key_set": bool(api_key)}


@app.post("/api/key")
def set_api_key(req: ApiKeyRequest):
    """Set the Gemini API key at runtime (no restart needed)."""
    global api_key, gemini
    api_key = req.api_key.strip()
    gemini = GeminiClient(api_key)
    # Save to .env file for persistence
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    with open(env_path, "w") as f:
        f.write(f"GEMINI_API_KEY={api_key}\n")
    return {"status": "API key saved successfully"}


@app.get("/api/key/status")
def key_status():
    return {"configured": bool(api_key)}


@app.post("/api/ask")
def ask_question(req: AskRequest):
    ai = get_gemini()
    raw_answer = ai.ask(req.question)

    # Parse and execute any embedded action tags in the AI response
    action_results = parse_and_execute_actions(
        raw_answer,
        callback=lambda r: broadcast_sync({"type": "action_result", "text": r.message, "success": r.success})
    )

    # Strip action tags from visible answer
    visible_answer = strip_action_tags(raw_answer)

    # Broadcast action notifications to HUD
    for r in action_results:
        broadcast_sync({"type": "action_result", "text": r.message, "success": True})

    return {"answer": visible_answer, "actions_triggered": len(action_results)}


@app.post("/api/command")
def run_command_directly(req: ManualCommand):
    """Execute a computer automation command directly from the HUD."""
    result = execute_command(req.command, req.params)
    broadcast_sync({"type": "action_result", "text": result.message, "success": result.success})
    return result.to_dict()


@app.post("/api/summarize")
def summarize():
    ai = get_gemini()
    summary = ai.summarize()
    return {"summary": summary}


@app.post("/api/action-items")
def action_items():
    ai = get_gemini()
    items = ai.get_action_items()
    return {"items": items}


@app.post("/api/rephrase")
def rephrase(req: RephraseRequest):
    ai = get_gemini()
    result = ai.rephrase(req.text)
    return {"rephrased": result}


@app.get("/api/transcript")
def get_transcript():
    return {"transcript": transcript_log}


@app.delete("/api/transcript")
def clear_transcript():
    global transcript_log
    transcript_log = []
    if gemini:
        gemini.transcript_context = []
    return {"status": "cleared"}


@app.post("/api/transcription/start")
def start_transcription():
    global transcription_engine, transcription_active
    if transcription_active:
        return {"status": "already running"}
    transcription_engine = TranscriptionEngine(
        on_text=on_transcript_text,
        on_error=on_transcript_error
    )
    transcription_engine.start()
    transcription_active = True
    return {"status": "transcription started"}


@app.post("/api/transcription/stop")
def stop_transcription():
    global transcription_engine, transcription_active
    if transcription_engine:
        transcription_engine.stop()
        transcription_engine = None
    transcription_active = False
    return {"status": "transcription stopped"}


@app.get("/api/transcription/status")
def transcription_status():
    return {"active": transcription_active}


@app.post("/api/meeting/context")
def set_meeting_context(ctx: MeetingContext):
    """Called by Chrome extension when a meeting is detected."""
    if gemini:
        gemini.update_transcript(
            f"[Meeting started: {ctx.title} on {ctx.platform}]"
        )
    broadcast_sync({"type": "meeting_detected", "title": ctx.title, "platform": ctx.platform})
    return {"status": "context updated"}


@app.post("/api/reset")
def reset_session():
    global transcript_log
    transcript_log = []
    if gemini:
        gemini.reset_chat()
    return {"status": "session reset"}


@app.post("/api/shutdown")
def shutdown_server():
    import os, signal
    # On Windows, SIGTERM might not cleanly exit uvicorn, os._exit works safely here
    os._exit(0)
    return {"status": "shutting down"}


# ─── WebSocket for real-time HUD updates ──────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        await websocket.send_json({"type": "connected", "text": "AI Assistant connected"})
        while True:
            # Keep connection alive, receive any messages from HUD
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        connected_clients.remove(websocket)


# ─── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("  [AI] Aura AI - Backend")
    print("  Running on http://localhost:8000")
    print("=" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
