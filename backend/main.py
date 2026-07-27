"""
FastAPI Backend — the brain of Aura AI.
Exposes REST endpoints and WebSocket for real-time updates to the HUD overlay.
Now includes TTS (text-to-speech) so Aura responds like Siri.
"""

import os
import sys
sys.stdout = open(os.devnull, "w", encoding="utf-8")
sys.stderr = open(os.devnull, "w", encoding="utf-8")
import json
import asyncio
import threading
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from openrouter_client import OpenRouterClient, test_key
from transcription import TranscriptionEngine
from automation import parse_and_execute_actions, strip_action_tags, execute_command
from tts_engine import tts

load_dotenv()

# ─── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="Aura AI", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── State ────────────────────────────────────────────────────────────────────
api_key: Optional[str] = os.getenv("OPENROUTER_API_KEY", "")
ai_client: Optional[OpenRouterClient] = None
transcription_engine: Optional[TranscriptionEngine] = None
transcript_log: list[str] = []
connected_clients: list[WebSocket] = []
transcription_active = False
tts_enabled = True


def get_ai() -> OpenRouterClient:
    global ai_client, api_key
    if not api_key:
        raise HTTPException(status_code=401, detail="No API key configured. Please set your OpenRouter API key.")
    if ai_client is None:
        ai_client = OpenRouterClient(api_key)
    return ai_client


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


main_loop = None

@app.on_event("startup")
def on_startup():
    global main_loop
    main_loop = asyncio.get_running_loop()

def broadcast_sync(message: dict):
    """Thread-safe broadcast — called from non-async AnyIO threads."""
    if main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(broadcast(message), main_loop)


# ─── Transcription Callbacks ──────────────────────────────────────────────────
def on_transcript_text(text: str):
    global transcript_log
    transcript_log.append(text)
    if len(transcript_log) > 200:
        transcript_log = transcript_log[-200:]

    ai = ai_client
    if ai:
        ai.update_transcript(text)

    broadcast_sync({"type": "transcript", "text": text})


def on_transcript_error(error: str):
    broadcast_sync({"type": "error", "text": error})


# ─── Models ───────────────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str
    speak: bool = True  # Whether to speak the response via TTS

class RephraseRequest(BaseModel):
    text: str

class ApiKeyRequest(BaseModel):
    api_key: str

class MeetingContext(BaseModel):
    title: str
    platform: str

class ManualCommand(BaseModel):
    command: str
    params: dict = {}

class TTSRequest(BaseModel):
    text: str

class TTSSettingsRequest(BaseModel):
    enabled: Optional[bool] = None
    rate: Optional[int] = None
    volume: Optional[float] = None

class VoiceAskRequest(BaseModel):
    """Ask from voice — always speak the response back."""
    question: str

class LanguageRequest(BaseModel):
    language: str  # 'en', 'fr', or 'ar'


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "status": "Aura AI running",
        "api_key_set": bool(api_key),
        "tts_available": tts.available,
        "tts_enabled": tts_enabled,
    }


@app.post("/api/key")
def set_api_key(req: ApiKeyRequest):
    """Validate then set the OpenRouter API key at runtime (no restart needed)."""
    global api_key, ai_client
    new_key = req.api_key.strip()

    result = test_key(new_key)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])

    # Key is valid (even if quota is exhausted) — save it
    api_key = new_key
    ai_client = OpenRouterClient(api_key)
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    with open(env_path, "w") as f:
        f.write(f"OPENROUTER_API_KEY={api_key}\n")

    resp = {"status": "API key saved successfully"}
    if result.get("warning"):
        resp["warning"] = result["warning"]
    return resp


@app.get("/api/key/status")
def key_status():
    return {"configured": bool(api_key)}


@app.post("/api/language")
def set_language(req: LanguageRequest):
    """Set the AI response language: 'en', 'fr', or 'ar'."""
    lang = req.language.lower().strip()
    if lang not in ("en", "fr", "ar"):
        raise HTTPException(status_code=400, detail="Language must be 'en', 'fr', or 'ar'")
    if ai_client:
        ai_client.set_language(lang)
    return {"status": "language updated", "language": lang}


@app.get("/api/language")
def get_language():
    lang = ai_client.language if ai_client else "en"
    return {"language": lang}


@app.post("/api/ask")
def ask_question(req: AskRequest):
    try:
        ai = get_ai()
        raw_answer = ai.ask(req.question)
    except HTTPException:
        raise
    except Exception as e:
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            err = (
                "[QUOTA] Daily API quota exhausted.\n"
                "Go to aistudio.google.com/apikey, sign in with a DIFFERENT Google account, "
                "create a new key, and paste it in Settings."
            )
        else:
            err = f"[ERROR] AI Error: {msg[:200]}"
        return {"answer": err, "actions_triggered": 0}

    # Parse and execute any embedded action tags
    action_results = parse_and_execute_actions(
        raw_answer,
        callback=lambda r: broadcast_sync({"type": "action_result", "text": r.message, "success": r.success})
    )

    visible_answer = strip_action_tags(raw_answer)

    # Broadcast action notifications to HUD
    for r in action_results:
        broadcast_sync({"type": "action_result", "text": r.message, "success": True})

    # Speak the answer via TTS if enabled
    if req.speak and tts_enabled:
        threading.Thread(
            target=tts.speak,
            args=(visible_answer,),
            kwargs={"interrupt": True},
            daemon=True
        ).start()

    # Push the answer to HUD via WebSocket so it appears in the chat
    broadcast_sync({"type": "ai_response", "text": visible_answer})

    return {"answer": visible_answer, "actions_triggered": len(action_results)}


@app.post("/api/voice_ask")
def voice_ask(req: VoiceAskRequest):
    """Voice-triggered ask."""
    try:
        ai = get_ai()
        raw_answer = ai.ask(req.question)
    except HTTPException:
        raise
    except Exception as e:
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            err = "[QUOTA] Quota exhausted. Please update your API key in Settings."
        else:
            err = f"[ERROR] AI Error: {msg[:150]}"
        return {"answer": err, "actions_triggered": 0}

    action_results = parse_and_execute_actions(
        raw_answer,
        callback=lambda r: broadcast_sync({"type": "action_result", "text": r.message, "success": r.success})
    )

    visible_answer = strip_action_tags(raw_answer)

    for r in action_results:
        broadcast_sync({"type": "action_result", "text": r.message, "success": True})

    # Always speak voice responses
    threading.Thread(
        target=tts.speak,
        args=(visible_answer,),
        kwargs={"interrupt": True},
        daemon=True
    ).start()

    broadcast_sync({"type": "voice_response", "text": visible_answer, "question": req.question})

    return {"answer": visible_answer, "actions_triggered": len(action_results)}


@app.post("/api/command")
def run_command_directly(req: ManualCommand):
    """Execute a computer automation command directly from the HUD."""
    result = execute_command(req.command, req.params)
    broadcast_sync({"type": "action_result", "text": result.message, "success": result.success})
    return result.to_dict()


@app.post("/api/summarize")
def summarize():
    ai = get_ai()
    summary = ai.summarize()
    return {"summary": summary}


@app.post("/api/action-items")
def action_items():
    ai = get_ai()
    items = ai.get_action_items()
    return {"items": items}


@app.post("/api/rephrase")
def rephrase(req: RephraseRequest):
    ai = get_ai()
    result = ai.rephrase(req.text)
    return {"rephrased": result}


@app.get("/api/transcript")
def get_transcript():
    return {"transcript": transcript_log}


@app.delete("/api/transcript")
def clear_transcript():
    global transcript_log
    transcript_log = []
    if ai_client:
        ai_client.transcript_context = []
    return {"status": "cleared"}


# ─── TTS Endpoints ────────────────────────────────────────────────────────────

@app.post("/api/tts/speak")
def tts_speak(req: TTSRequest):
    """Speak arbitrary text via TTS."""
    if not tts_enabled:
        return {"status": "TTS disabled"}
    threading.Thread(target=tts.speak, args=(req.text,), daemon=True).start()
    return {"status": "speaking"}


@app.post("/api/tts/stop")
def tts_stop():
    """Stop any ongoing TTS speech."""
    tts.stop()
    return {"status": "stopped"}


@app.post("/api/tts/settings")
def tts_settings(req: TTSSettingsRequest):
    """Update TTS settings (enable/disable, rate, volume)."""
    global tts_enabled
    if req.enabled is not None:
        tts_enabled = req.enabled
        tts.set_enabled(req.enabled)
    if req.rate is not None:
        tts.set_rate(req.rate)
    if req.volume is not None:
        tts.set_volume(req.volume)
    return {
        "tts_enabled": tts_enabled,
        "available": tts.available
    }


@app.get("/api/tts/status")
def tts_status():
    return {
        "enabled": tts_enabled,
        "available": tts.available,
    }


# ─── Transcription Endpoints ──────────────────────────────────────────────────

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
    if ai_client:
        ai_client.update_transcript(
            f"[Meeting started: {ctx.title} on {ctx.platform}]"
        )
    broadcast_sync({"type": "meeting_detected", "title": ctx.title, "platform": ctx.platform})
    return {"status": "context updated"}


@app.post("/api/reset")
def reset_session():
    global transcript_log
    transcript_log = []
    tts.stop()
    if ai_client:
        ai_client.reset_chat()
    return {"status": "session reset"}


@app.post("/api/shutdown")
def shutdown_server():
    tts.stop()
    import os
    os._exit(0)
    return {"status": "shutting down"}


# ─── WebSocket for real-time HUD updates ──────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        await websocket.send_json({
            "type": "connected",
            "text": "Aura AI connected",
            "tts_available": tts.available,
        })
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


# ─── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
