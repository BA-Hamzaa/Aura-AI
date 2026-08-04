"""
main.py — J.A.R.V.I.S. FastAPI Backend
Production-grade AI assistant backend with:
  - OpenRouter AI client
  - Long-term memory (SQLite + semantic search)
  - Planning system
  - Plugin SDK
  - Background task manager
  - Full logging
  - WebSocket real-time updates
"""

import os
import sys
import json
import asyncio
import threading
import time
from typing import Optional, List

# ── Silence console noise ────────────────────────────────────────────────────
sys.stdout = open(os.devnull, "w", encoding="utf-8")
sys.stderr = open(os.devnull, "w", encoding="utf-8")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# ── Load env ─────────────────────────────────────────────────────────────────
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_ENV_PATH)

# ── Internal modules ──────────────────────────────────────────────────────────
from openrouter_client import OpenRouterClient, test_key
from transcription import TranscriptionEngine
from automation import parse_and_execute_actions, strip_action_tags, execute_command
from tts_engine import tts
from memory import memory, MemoryEngine
from planner import planner, RiskLevel
from plugins import plugin_manager
from task_manager import task_manager
from logger import get_logger, get_ring_buffer, get_perf_tracker, timer

log = get_logger("main")

# ─── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="J.A.R.V.I.S.", version="3.0.0", description="Production AI Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Global State ─────────────────────────────────────────────────────────────
api_key: Optional[str] = os.getenv("OPENROUTER_API_KEY", "")
ai_client: Optional[OpenRouterClient] = None
transcription_engine: Optional[TranscriptionEngine] = None
transcript_log: list = []
connected_clients: list = []
transcription_active = False
tts_enabled = True
main_loop = None

# Current session ID
import uuid
_session_id = str(uuid.uuid4())[:8]


# ─── AI Client Factory ─────────────────────────────────────────────────────────
def get_ai() -> OpenRouterClient:
    global ai_client, api_key
    if not api_key:
        raise HTTPException(status_code=401, detail="No API key configured. Please set your OpenRouter API key.")
    if ai_client is None:
        ai_client = OpenRouterClient(api_key)
    return ai_client


# ─── WebSocket Broadcast ───────────────────────────────────────────────────────
async def broadcast(message: dict):
    dead = []
    for ws in connected_clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in connected_clients:
            connected_clients.remove(ws)


def broadcast_sync(message: dict):
    """Thread-safe broadcast from non-async threads."""
    if main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(broadcast(message), main_loop)


# ─── Startup / Shutdown ────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    global main_loop
    main_loop = asyncio.get_running_loop()
    task_manager.broadcast_fn = broadcast_sync
    # Load external plugins
    results = plugin_manager.load_all()
    for mod, err in results.items():
        if err:
            log.warning(f"Plugin '{mod}': {err}")
        else:
            log.info(f"Plugin loaded: {mod}")
    # Pre-init AI client if key available
    if api_key:
        try:
            ai_client  # triggers lazy init check but doesn't call get_ai()
        except Exception:
            pass
    log.info("J.A.R.V.I.S. backend started 🚀")


# ─── Transcription Callbacks ──────────────────────────────────────────────────
def on_transcript_text(text: str):
    global transcript_log
    transcript_log.append(text)
    if len(transcript_log) > 200:
        transcript_log = transcript_log[-200:]
    if ai_client:
        ai_client.update_transcript(text)
    broadcast_sync({"type": "transcript", "text": text})


def on_transcript_error(error: str):
    broadcast_sync({"type": "error", "text": error})


# ─── Pydantic Models ──────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str
    speak: bool = True
    use_memory: bool = True
    use_planning: bool = True

class VoiceAskRequest(BaseModel):
    question: str

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

class LanguageRequest(BaseModel):
    language: str

class MemoryRequest(BaseModel):
    value: str
    category: str = "general"
    key: str = ""
    importance: int = 1

class PreferenceRequest(BaseModel):
    key: str
    value: str

class TaskRequest(BaseModel):
    title: str
    description: str = ""
    priority: int = 3
    due_at: str = ""

class ReminderRequest(BaseModel):
    text: str
    remind_at: str  # ISO datetime string

class ProjectRequest(BaseModel):
    name: str
    description: str = ""

class PluginToolRequest(BaseModel):
    tool: str
    kwargs: dict = {}


# ─── Core Endpoints ───────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "status":       "J.A.R.V.I.S. running",
        "version":      "3.0.0",
        "api_key_set":  bool(api_key),
        "tts_available": tts.available,
        "tts_enabled":  tts_enabled,
        "memory_stats": memory.stats(),
        "plugins":      len(plugin_manager.list_plugins()),
        "session_id":   _session_id,
    }


@app.post("/api/key")
def set_api_key(req: ApiKeyRequest):
    global api_key, ai_client
    new_key = req.api_key.strip()
    result = test_key(new_key)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    api_key = new_key
    ai_client = OpenRouterClient(api_key)
    with open(_ENV_PATH, "w") as f:
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
    lang = req.language.lower().strip()
    if lang not in ("en", "fr", "ar"):
        raise HTTPException(status_code=400, detail="Language must be 'en', 'fr', or 'ar'")
    if ai_client:
        ai_client.set_language(lang)
    memory.set_preference("language", lang)
    return {"status": "language updated", "language": lang}


@app.get("/api/language")
def get_language():
    lang = ai_client.language if ai_client else memory.get_preference("language", "en")
    return {"language": lang}


# ─── Ask / Chat ───────────────────────────────────────────────────────────────

@app.post("/api/ask")
def ask_question(req: AskRequest):
    with timer("api.ask"):
        try:
            ai = get_ai()

            # ── Planning ─────────────────────────────────────────────────────
            plan = None
            if req.use_planning:
                plan = planner.plan(req.question)
                if plan.needs_confirmation and plan.complexity.value == "complex":
                    broadcast_sync({
                        "type": "plan_preview",
                        "summary": plan.summary,
                        "steps": len(plan.subtasks),
                    })

            # ── Memory context injection ──────────────────────────────────────
            question = req.question
            if req.use_memory:
                ctx = memory.build_context_summary()
                if ctx:
                    question = f"[Context from memory]\n{ctx}\n\n[User Request]\n{req.question}"

            with timer("ai.ask"):
                raw_answer = ai.ask(question)

        except HTTPException:
            raise
        except Exception as e:
            msg = str(e)
            if "429" in msg or "quota" in msg.lower():
                err = "[QUOTA] Daily API quota exhausted. Update your API key in Settings."
            else:
                err = f"[ERROR] AI Error: {msg[:200]}"
            return {"answer": err, "actions_triggered": 0}

    # ── Actions ───────────────────────────────────────────────────────────────
    action_results = parse_and_execute_actions(
        raw_answer,
        callback=lambda r: broadcast_sync({"type": "action_result", "text": r.message, "success": r.success})
    )
    visible_answer = strip_action_tags(raw_answer)

    for r in action_results:
        broadcast_sync({"type": "action_result", "text": r.message, "success": True})

    # ── Memory: save conversation ─────────────────────────────────────────────
    if req.use_memory:
        memory.save_message(_session_id, "user", req.question)
        memory.save_message(_session_id, "assistant", visible_answer)

    # ── TTS ───────────────────────────────────────────────────────────────────
    if req.speak and tts_enabled:
        threading.Thread(target=tts.speak, args=(visible_answer,), kwargs={"interrupt": True}, daemon=True).start()

    broadcast_sync({"type": "ai_response", "text": visible_answer})
    return {
        "answer":           visible_answer,
        "actions_triggered": len(action_results),
        "plan":             plan.to_dict() if plan else None,
    }


@app.post("/api/voice_ask")
def voice_ask(req: VoiceAskRequest):
    with timer("api.voice_ask"):
        try:
            ai = get_ai()
            # Planning check
            plan = planner.plan(req.question)
            raw_answer = ai.ask(req.question)
        except HTTPException:
            raise
        except Exception as e:
            msg = str(e)
            err = "[QUOTA] Quota exhausted." if "quota" in msg.lower() else f"[ERROR] {msg[:150]}"
            return {"answer": err, "actions_triggered": 0}

    action_results = parse_and_execute_actions(
        raw_answer,
        callback=lambda r: broadcast_sync({"type": "action_result", "text": r.message, "success": r.success})
    )
    visible_answer = strip_action_tags(raw_answer)

    for r in action_results:
        broadcast_sync({"type": "action_result", "text": r.message, "success": True})

    # Save to memory
    memory.save_message(_session_id, "user", req.question)
    memory.save_message(_session_id, "assistant", visible_answer)

    threading.Thread(target=tts.speak, args=(visible_answer,), kwargs={"interrupt": True}, daemon=True).start()
    broadcast_sync({"type": "voice_response", "text": visible_answer, "question": req.question})
    return {"answer": visible_answer, "actions_triggered": len(action_results)}


@app.post("/api/command")
def run_command_directly(req: ManualCommand):
    # Safety check
    risk = planner.classify_risk(req.command)
    result = execute_command(req.command, req.params)
    broadcast_sync({"type": "action_result", "text": result.message, "success": result.success})
    resp = result.to_dict()
    resp["risk"] = risk.value
    return resp


# ─── Memory Endpoints ─────────────────────────────────────────────────────────

@app.post("/api/memory/remember")
def api_remember(req: MemoryRequest):
    fact_id = memory.remember(req.value, req.category, req.key, req.importance)
    return {"status": "saved", "id": fact_id}


@app.post("/api/memory/recall")
def api_recall(req: MemoryRequest):
    results = memory.recall(req.value, limit=8, category=req.category)
    return {"results": results}


@app.get("/api/memory/facts")
def api_list_facts(category: str = "", limit: int = 50):
    return {"facts": memory.list_facts(category, limit)}


@app.delete("/api/memory/facts/{fact_id}")
def api_forget(fact_id: int):
    memory.forget(fact_id)
    return {"status": "deleted"}


@app.get("/api/memory/stats")
def api_memory_stats():
    return memory.stats()


@app.get("/api/memory/history")
def api_chat_history(session_id: str = "", limit: int = 30):
    sid = session_id or _session_id
    return {"history": memory.get_history(sid, limit), "session_id": sid}


# ─── Preferences Endpoints ────────────────────────────────────────────────────

@app.post("/api/preferences")
def set_preference(req: PreferenceRequest):
    memory.set_preference(req.key, req.value)
    return {"status": "saved", "key": req.key}


@app.get("/api/preferences")
def get_all_preferences():
    return {"preferences": memory.all_preferences()}


@app.get("/api/preferences/{key}")
def get_preference(key: str):
    return {"key": key, "value": memory.get_preference(key)}


# ─── Tasks Endpoints ──────────────────────────────────────────────────────────

@app.post("/api/tasks")
def create_task(req: TaskRequest):
    task_id = memory.add_task(req.title, req.description, req.priority, req.due_at)
    return {"status": "created", "id": task_id}


@app.get("/api/tasks")
def list_tasks(status: str = "pending"):
    return {"tasks": memory.get_tasks(status)}


@app.patch("/api/tasks/{task_id}/complete")
def complete_task(task_id: int):
    memory.complete_task(task_id)
    return {"status": "completed"}


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    memory.delete_task(task_id)
    return {"status": "deleted"}


# ─── Reminders Endpoints ──────────────────────────────────────────────────────

@app.post("/api/reminders")
def create_reminder(req: ReminderRequest):
    reminder_id = memory.add_reminder(req.text, req.remind_at)
    return {"status": "created", "id": reminder_id}


@app.get("/api/reminders")
def list_reminders():
    return {"reminders": memory.list_reminders()}


# ─── Projects Endpoints ───────────────────────────────────────────────────────

@app.post("/api/projects")
def create_project(req: ProjectRequest):
    project_id = memory.add_project(req.name, req.description)
    return {"status": "created", "id": project_id}


@app.get("/api/projects")
def list_projects():
    return {"projects": memory.get_projects()}


# ─── Plugin Endpoints ─────────────────────────────────────────────────────────

@app.get("/api/plugins")
def list_plugins():
    return {"plugins": plugin_manager.list_plugins()}


@app.get("/api/plugins/tools")
def list_tools():
    return {"tools": plugin_manager.list_tools()}


@app.post("/api/plugins/call")
def call_plugin_tool(req: PluginToolRequest):
    try:
        result = plugin_manager.call_tool(req.tool, **req.kwargs)
        return {"result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/plugins/reload")
def reload_plugins():
    plugin_manager.load_all()
    return {"plugins": plugin_manager.list_plugins()}


# ─── Background Task Manager Endpoints ────────────────────────────────────────

@app.get("/api/bg_tasks")
def list_bg_tasks(status: str = ""):
    return {"tasks": task_manager.list_tasks(status), "stats": task_manager.stats()}


@app.delete("/api/bg_tasks/{task_id}")
def cancel_bg_task(task_id: str):
    ok = task_manager.cancel(task_id)
    return {"cancelled": ok}


@app.post("/api/bg_tasks/clear")
def clear_done_tasks():
    count = task_manager.clear_done()
    return {"cleared": count}


# ─── Logs Endpoints ───────────────────────────────────────────────────────────

@app.get("/api/logs")
def get_logs(limit: int = 100, level: str = ""):
    ring = get_ring_buffer()
    return {"logs": ring.get_logs(limit, level)}


@app.delete("/api/logs")
def clear_logs():
    get_ring_buffer().clear()
    return {"status": "cleared"}


@app.get("/api/logs/performance")
def perf_stats():
    tracker = get_perf_tracker()
    return {
        "ai_ask":       tracker.stats("ai.ask"),
        "api_ask":      tracker.stats("api.ask"),
        "voice_ask":    tracker.stats("api.voice_ask"),
        "recent":       tracker.get_recent(20),
    }


# ─── Planning Endpoints ───────────────────────────────────────────────────────

@app.post("/api/plan")
def create_plan(req: AskRequest):
    plan = planner.plan(req.question)
    return {"plan": plan.to_dict()}


# ─── TTS Endpoints ────────────────────────────────────────────────────────────

@app.post("/api/tts/speak")
def tts_speak(req: TTSRequest):
    if not tts_enabled:
        return {"status": "TTS disabled"}
    threading.Thread(target=tts.speak, args=(req.text,), daemon=True).start()
    return {"status": "speaking"}


@app.post("/api/tts/stop")
def tts_stop():
    tts.stop()
    return {"status": "stopped"}


@app.post("/api/tts/settings")
def tts_settings(req: TTSSettingsRequest):
    global tts_enabled
    if req.enabled is not None:
        tts_enabled = req.enabled
        tts.set_enabled(req.enabled)
    if req.rate is not None:
        tts.set_rate(req.rate)
    if req.volume is not None:
        tts.set_volume(req.volume)
    return {"tts_enabled": tts_enabled, "available": tts.available}


@app.get("/api/tts/status")
def tts_status():
    return {"enabled": tts_enabled, "available": tts.available}


# ─── Transcription Endpoints ──────────────────────────────────────────────────

@app.post("/api/transcription/start")
def start_transcription():
    global transcription_engine, transcription_active
    if transcription_active:
        return {"status": "already running"}
    transcription_engine = TranscriptionEngine(on_text=on_transcript_text, on_error=on_transcript_error)
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


# ─── Transcript Endpoints ─────────────────────────────────────────────────────

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


# ─── Summarize / Action Items / Rephrase ──────────────────────────────────────

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


# ─── Meeting Context ──────────────────────────────────────────────────────────

@app.post("/api/meeting/context")
def set_meeting_context(ctx: MeetingContext):
    if ai_client:
        ai_client.update_transcript(f"[Meeting started: {ctx.title} on {ctx.platform}]")
    broadcast_sync({"type": "meeting_detected", "title": ctx.title, "platform": ctx.platform})
    return {"status": "context updated"}


# ─── Session / Reset ──────────────────────────────────────────────────────────

@app.post("/api/reset")
def reset_session():
    global transcript_log, _session_id
    transcript_log = []
    tts.stop()
    if ai_client:
        ai_client.reset_chat()
    _session_id = str(uuid.uuid4())[:8]
    return {"status": "session reset", "new_session_id": _session_id}


@app.post("/api/shutdown")
def shutdown_server():
    tts.stop()
    os._exit(0)


# ─── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        await websocket.send_json({
            "type":          "connected",
            "text":          "J.A.R.V.I.S. connected",
            "tts_available": tts.available,
            "session_id":    _session_id,
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
