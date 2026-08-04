# J.A.R.V.I.S. — Production AI Assistant
## Complete Architecture & Technical Documentation

---

## 1. System Overview

J.A.R.V.I.S. (Just A Rather Very Intelligent System) is a production-grade desktop AI assistant inspired by Iron Man's JARVIS. It runs locally on Windows, connects to cloud LLMs via OpenRouter, and provides a stealth-capable overlay UI.

**Design Philosophy:**
- Think before acting (planning layer)
- Remember across sessions (memory layer)
- Modular and extensible (plugin system)
- Safe by default (risk classification)
- Observable (structured logging)

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     USER INTERFACE LAYER                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Chat    │  │  Voice   │  │  Tasks   │  │  Plugins │   │
│  │   Tab    │  │  Input   │  │  Manager │  │  & Tools │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       └──────────────┴─────────────┴──────────────┘          │
│                         hud.py (Tkinter)                      │
└─────────────────────────────┬───────────────────────────────┘
                               │ HTTP / WebSocket
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER                         │
│                    main.py (FastAPI)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  /api/   │  │  /api/   │  │  /api/   │  │   /ws    │   │
│  │   ask    │  │  memory  │  │  plugins │  │ WebSocket │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────┘   │
└───────┼─────────────┼─────────────┼────────────────────────┘
        │             │             │
┌───────┼─────────────┼─────────────┼────────────────────────┐
│       │      DOMAIN / CORE LAYER  │                         │
│  ┌────▼─────┐  ┌────▼─────┐  ┌───▼──────┐  ┌──────────┐  │
│  │ Planner  │  │  Memory  │  │  Plugin  │  │  Task    │  │
│  │ planner  │  │  Engine  │  │  Manager │  │  Manager │  │
│  │  .py     │  │ memory.py│  │ plugins  │  │task_mgr  │  │
│  └────┬─────┘  └────┬─────┘  │  .py     │  │  .py     │  │
│       │             │         └──────────┘  └──────────┘  │
└───────┼─────────────┼──────────────────────────────────────┘
        │             │
┌───────┼─────────────┼──────────────────────────────────────┐
│       │  INFRASTRUCTURE LAYER     │                         │
│  ┌────▼─────┐  ┌────▼─────┐  ┌───▼──────┐  ┌──────────┐  │
│  │OpenRouter│  │  SQLite  │  │ Automation│  │   TTS    │  │
│  │  Client  │  │   DB     │  │automation │  │ engine   │  │
│  │openrouter│  │memory.db │  │  .py      │  │ tts_eng  │  │
│  │_client   │  └──────────┘  └──────────┘  │  .py     │  │
│  │  .py     │                               └──────────┘  │
│  └──────────┘                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Logger  │  │ Stealth  │  │Transcript│  │Wake Word │  │
│  │logger.py │  │stealth.py│  │transc.py │  │wake_word │  │
│  └──────────┘  └──────────┘  └──────────┘  │  .py     │  │
│                                             └──────────┘  │
└────────────────────────────────────────────────────────────┘
        │
┌───────▼──────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                       │
│   OpenRouter API → [Gemma 4, Nemotron, Llama, etc.]      │
│   wttr.in (weather) · Web browsers · System APIs         │
└────────────────────────────────────────────────────────────┘
```

---

## 3. Folder Structure

```
project ai/
├── backend/
│   ├── main.py                # FastAPI app — all endpoints
│   ├── openrouter_client.py   # AI client with model fallback
│   ├── memory.py              # Long-term memory (SQLite + embeddings)
│   ├── planner.py             # Request decomposition & risk classification
│   ├── plugins.py             # Plugin SDK + built-in plugins
│   ├── task_manager.py        # Background task executor
│   ├── logger.py              # Structured logging + performance tracking
│   ├── automation.py          # Desktop automation tools
│   ├── tts_engine.py          # Text-to-speech engine
│   ├── transcription.py       # Speech-to-text transcription
│   ├── wake_word.py           # Wake word detection
│   ├── ai_client.py           # Thin wrapper
│   ├── gemini_client.py       # Legacy (keep for reference)
│   ├── requirements.txt       # Python dependencies
│   ├── .env                   # API keys (NOT committed)
│   └── jarvis_memory.db       # SQLite memory store (auto-created)
│
├── overlay/
│   ├── hud.py                 # Main UI — Tkinter premium HUD
│   ├── stealth.py             # Screen-share exclusion (Win32)
│   ├── wake_word.py           # Wake word (shared with backend)
│   ├── brain_icon.ico         # App icon
│   └── brain_icon.png         # High-res icon
│
├── plugins/                   # User/custom plugins (auto-discovered)
│   ├── __init__.py
│   └── example_plugin.py      # Example plugin template
│
├── chrome-extension/          # Browser integration
│   └── ...
│
├── logs/                      # Auto-created log files
│   └── jarvis.log             # Rotating JSON log
│
├── .env                       # Root env (may mirror backend/.env)
├── .gitignore
├── README.md
├── start.bat                  # Launch script
├── setup.bat                  # First-time setup
└── Aura AI.vbs                # Silent launch VBS script
```

---

## 4. Database Schema

**File:** `backend/jarvis_memory.db` (SQLite, WAL mode)

```sql
-- Facts: anything J.A.R.V.I.S. should remember
CREATE TABLE facts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL DEFAULT 'general',  -- e.g. 'project', 'preference', 'fact'
    key         TEXT,                             -- optional named key
    value       TEXT NOT NULL,                   -- the actual memory text
    embedding   BLOB,                            -- 384-dim float32 vector (sentence-transformers)
    importance  INTEGER DEFAULT 1,               -- 1=low, 5=critical
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- User preferences
CREATE TABLE preferences (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT NOT NULL UNIQUE,
    value       TEXT NOT NULL,                   -- JSON-encoded value
    updated_at  TEXT NOT NULL
);

-- Task list
CREATE TABLE tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT,
    status      TEXT DEFAULT 'pending',          -- pending | completed | cancelled
    priority    INTEGER DEFAULT 3,               -- 1=urgent, 5=low
    due_at      TEXT,                            -- ISO datetime
    created_at  TEXT NOT NULL,
    completed_at TEXT
);

-- Reminders
CREATE TABLE reminders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT NOT NULL,
    remind_at   TEXT NOT NULL,                   -- ISO datetime
    fired       INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL
);

-- Persistent conversation history
CREATE TABLE chat_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,                   -- 'user' | 'assistant'
    content     TEXT NOT NULL,
    timestamp   TEXT NOT NULL
);

-- Projects tracking
CREATE TABLE projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    status      TEXT DEFAULT 'active',
    metadata    TEXT DEFAULT '{}',               -- JSON blob
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
```

---

## 5. Memory Architecture

```
User says: "Remember that I prefer Python over Java"
           ▼
    memory.remember(value="...", category="preference", importance=2)
           ▼
    ┌─────────────────────────────────────────────────────┐
    │  SQLite INSERT + optional embedding generation       │
    │  (sentence-transformers MiniLM if installed)         │
    └─────────────────────────────────────────────────────┘

User asks: "What programming language do I prefer?"
           ▼
    memory.recall("programming language preference", limit=5)
           ▼
    ┌─────────────────────────────────────────────────────┐
    │  Mode A: Semantic search (cosine similarity)         │
    │    → Encode query → Compare vs stored embeddings     │
    │  Mode B: Keyword fallback (no sentence-transformers) │
    │    → SQL LIKE search on value text                   │
    └─────────────────────────────────────────────────────┘
           ▼
    Top-K results injected into AI system prompt as context
```

**Memory Types:**
| Type | Storage | Purpose |
|------|---------|---------|
| Short-term | In-memory list | Current conversation context (last 20 turns) |
| Long-term facts | SQLite `facts` | Remembered across all sessions |
| Preferences | SQLite `preferences` | User settings, coding style, voice prefs |
| Tasks | SQLite `tasks` | To-do items and action items |
| History | SQLite `chat_sessions` | Full conversation log, queryable |
| Projects | SQLite `projects` | Active projects and metadata |

---

## 6. Tool System

All automations use `execute_command(type, params)` dispatch pattern:

```python
# Pattern: <<ACTION:type|param1=value1|param2=value2>>
# Example: <<ACTION:open_app|app=spotify>>

TOOLS = {
    # Web & Browser
    "open_url"      → webbrowser.open(url)
    "search_google" → open browser with Google query
    "youtube"       → open YouTube search

    # Desktop Automation
    "open_app"      → subprocess.Popen(exe)
    "close_app"     → psutil kill by process name
    "type_text"     → pyautogui.typewrite()
    "key"           → pyautogui.hotkey()
    "screenshot"    → pyautogui.screenshot()

    # System
    "volume"        → pycaw IAudioEndpointVolume
    "system.lock"   → LockWorkStation()
    "system.sleep"  → SetSuspendState()
    "system.shutdown" → shutdown /s /t 10
    "system.restart"  → shutdown /r /t 10
    "system.battery"  → psutil.sensors_battery()
    "system.wifi"   → netsh interface

    # Communication
    "send_email"    → Gmail compose URL + pyautogui Ctrl+Enter
    "discord_send"  → focus Discord + pyautogui type

    # Plugins (extensible)
    "weather.get_weather"     → wttr.in API
    "calculator.calculate"    → safe AST eval
    "clipboard.read_clipboard"  → PowerShell Get-Clipboard
    "clipboard.write_clipboard" → PowerShell Set-Clipboard
    "system_info.*"           → psutil metrics
}
```

---

## 7. Plugin SDK

**To create a plugin:**

```python
# plugins/my_plugin.py
from backend.plugins import BasePlugin, PluginMetadata

class MyPlugin(BasePlugin):
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_plugin",
            description="Does something awesome",
            version="1.0.0",
            author="Your Name",
            permissions=["internet"],  # declared but not enforced yet
        )

    def tools(self) -> dict:
        return {
            "do_thing": self.do_thing,
        }

    def on_load(self):
        """Initialize resources."""
        pass

    def on_unload(self):
        """Release resources."""
        pass

    def do_thing(self, param: str) -> str:
        return f"Did the thing with: {param}"
```

Plugin is auto-discovered at startup and its tools are:
- Available via `/api/plugins/call` endpoint
- Callable from AI via `<<ACTION:my_plugin.do_thing|param=hello>>`
- Listed in the Plugins tab of the HUD

---

## 8. Multi-Agent Orchestration

Currently implemented as a **Coordinator + Intent Router** pattern:

```
User Request
     ▼
  Planner.plan(request)
     ├─ [automation intent] → AutomationAgent (automation.py)
     ├─ [memory intent]     → MemoryAgent (memory.py)
     ├─ [code intent]       → AI with coding system prompt
     ├─ [research intent]   → AI with research context
     ├─ [weather intent]    → WeatherPlugin
     ├─ [calculation]       → CalculatorPlugin
     └─ [general]           → OpenRouterClient.ask()
```

**Planned Agent Upgrades (roadmap):**
- `CodingAgent` — VS Code integration, code execution sandbox
- `ResearchAgent` — Web scraping + summarization pipeline
- `VisionAgent` — Screen capture + OCR + OpenCV
- `BrowserAgent` — Playwright automation
- `SchedulerAgent` — Calendar + reminder polling loop

---

## 9. Security Model

| Risk Level | Examples | Behavior |
|------------|----------|----------|
| LOW | search, open app, get weather | Execute immediately |
| MEDIUM | run script, close all apps, download | Log + notify user |
| HIGH | delete files, shutdown, send email, format | Require explicit confirmation |

Risk is classified by `planner.classify_risk(request)` using keyword matching and regex patterns.

**Current Safety Rules:**
- Destructive commands always tagged as HIGH risk
- `planner.plan(request).needs_confirmation` signals the HUD to show confirmation dialog
- No command runs without the AI client being initialized with a valid API key
- Stealth mode prevents screen-capture (screen sharing exclusion)

---

## 10. API Reference

### Core
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Status + system info |
| POST | `/api/ask` | Chat with AI |
| POST | `/api/voice_ask` | Voice-triggered AI response |
| POST | `/api/key` | Set OpenRouter API key |
| GET | `/api/key/status` | Check if key is configured |
| POST | `/api/language` | Set AI language (en/fr/ar) |
| POST | `/api/plan` | Get execution plan for a request |

### Memory
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/memory/remember` | Store a fact |
| POST | `/api/memory/recall` | Semantic search |
| GET | `/api/memory/facts` | List all facts |
| DELETE | `/api/memory/facts/{id}` | Forget a fact |
| GET | `/api/memory/stats` | Memory statistics |
| GET | `/api/memory/history` | Conversation history |

### Tasks & Reminders
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/tasks` | Create a task |
| GET | `/api/tasks` | List tasks |
| PATCH | `/api/tasks/{id}/complete` | Mark complete |
| POST | `/api/reminders` | Create reminder |
| GET | `/api/reminders` | List reminders |

### Plugins
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/plugins` | List loaded plugins |
| GET | `/api/plugins/tools` | List all tools |
| POST | `/api/plugins/call` | Call a plugin tool |
| POST | `/api/plugins/reload` | Hot-reload plugins |

### Logs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/logs` | Recent log entries |
| GET | `/api/logs/performance` | Timing stats |
| DELETE | `/api/logs` | Clear logs |

### TTS / Transcription
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/tts/speak` | Speak text |
| POST | `/api/tts/stop` | Stop speaking |
| POST | `/api/tts/settings` | Configure TTS |
| POST | `/api/transcription/start` | Start mic transcription |
| POST | `/api/transcription/stop` | Stop transcription |

### WebSocket: `ws://localhost:8000/ws`
| Event Type | Direction | Data |
|-----------|-----------|------|
| `connected` | Server→Client | Initial handshake |
| `ai_response` | Server→Client | AI text response |
| `voice_response` | Server→Client | Voice-triggered response |
| `action_result` | Server→Client | Automation result |
| `transcript` | Server→Client | Live transcription text |
| `task_queued/started/done/failed` | Server→Client | Background task updates |
| `plan_preview` | Server→Client | Execution plan notification |
| `meeting_detected` | Server→Client | Chrome extension meeting alert |
| `ping` | Client→Server | Keepalive |
| `pong` | Server→Client | Keepalive reply |

---

## 11. Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| AI Brain | OpenRouter API | Free models, failover, no vendor lock-in |
| Backend | FastAPI + uvicorn | Fast async, WebSocket native, auto docs |
| Frontend | Python Tkinter | No browser dependency, stealth-compatible |
| Memory | SQLite (WAL) | Zero-config, durable, cross-session |
| Semantic Search | sentence-transformers | Local, no API cost, offline capable |
| TTS | pyttsx3 / SAPI | Built-in Windows voices, no API needed |
| STT | SpeechRecognition + pyaudio | Works offline with Google fallback |
| Automation | pyautogui + psutil | Cross-app keyboard/mouse control |
| Volume | pycaw | Native Windows audio API |
| Stealth | Win32 SetWindowDisplayAffinity | True kernel-level capture exclusion |
| Logging | Python logging + JSON | Rotating files, searchable, structured |

---

## 12. Implementation Roadmap

### ✅ Phase 1 — Complete (v1-v2)
- [x] FastAPI backend
- [x] OpenRouter AI with model fallback
- [x] Tkinter HUD overlay
- [x] TTS (pyttsx3 + SAPI)
- [x] STT (SpeechRecognition)
- [x] Desktop automation (apps, URLs, system)
- [x] Email via Gmail browser
- [x] Stealth mode (screen-share exclusion)
- [x] Wake word detection
- [x] Multilingual UI (EN/FR/AR)
- [x] Chrome extension integration
- [x] WebSocket real-time updates

### ✅ Phase 2 — Complete (v3.0 current)
- [x] Long-term memory (SQLite)
- [x] Semantic vector search (optional)
- [x] Planning system (intent detection, risk classification)
- [x] Plugin SDK (auto-discovery, hot-reload)
- [x] Built-in plugins (weather, calculator, clipboard, system monitor)
- [x] Background task manager (parallel, cancelable, progress)
- [x] Structured logging (JSON rotating files + ring buffer)
- [x] Performance tracking
- [x] Tasks & reminders API
- [x] Projects tracking
- [x] Preferences persistence
- [x] Conversation history persistence

### 🔄 Phase 3 — Planned (v4.0)
- [ ] Vision Agent (OpenCV + pytesseract OCR)
- [ ] Screen understanding (detect UI elements)
- [ ] Coding Agent (code execution sandbox)
- [ ] Research Agent (web scraping + summarization)
- [ ] Browser Agent (Playwright automation)
- [ ] Knowledge Base (PDF/Markdown indexing)
- [ ] Advanced HUD: Memory tab, Logs tab, Tasks tab
- [ ] Reminder polling daemon
- [ ] Calendar integration
- [ ] Git integration tools
- [ ] Docker management

### 🔮 Phase 4 — Future
- [ ] Local LLM support (Ollama integration)
- [ ] Multi-monitor support
- [ ] Mobile companion app
- [ ] Cross-platform (macOS/Linux)
- [ ] Face recognition (optional)
- [ ] Advanced wake word (Porcupine)
- [ ] Real-time translation
- [ ] Voice cloning / custom TTS

---

## 13. Configuration Reference

**`backend/.env`:**
```env
OPENROUTER_API_KEY=sk-or-...
```

**Memory preferences (set via API):**
```
language      = "en" | "fr" | "ar"
tts_enabled   = true | false
tts_rate      = 185 (words/min)
tts_volume    = 1.0 (0.0-1.0)
```

**Plugin configuration:** Each plugin defines its own config in `PluginMetadata.config`.

---

## 14. Testing

```bash
# Backend tests
cd backend

# Test API key
python test_key_probe.py

# Test server endpoints
python test_server.py

# Test AI response
python test_ask.py

# Test screenshot evaluation
python test_screenshot_eval.py
```

**Test categories planned:**
- Unit tests: `pytest backend/tests/unit/`
- Integration tests: `pytest backend/tests/integration/`
- E2E: Playwright tests against HUD

---

## 15. Deployment

### Local Development
```bash
# Setup (first time)
setup.bat

# Launch (normal)
start.bat

# Or via VBS for silent start
"Aura AI.vbs"
```

### Environment Requirements
- Windows 10/11 (build 19041+ for stealth mode)
- Python 3.10+
- Microphone (for voice features)
- OpenRouter API key (free tier available)

---

## 16. Best Practices

1. **Never commit `.env` files** — API keys must stay local
2. **Always use `broadcast_sync()` from background threads** — never call async functions from threads directly
3. **Plugins must be stateless or manage their own thread safety** — the plugin manager holds references but doesn't protect plugin internals
4. **Use `timer("operation")` context manager** for all external API calls to track latency
5. **Check `task.cancelled` in long-running tasks** — allows clean cancellation
6. **Keep AI prompts short** — cost and latency scale with token count
7. **Memory recall can be slow if embeddings aren't cached** — the `SentenceTransformer` model loads once at startup
8. **HUD Tkinter is single-threaded** — all UI updates must go through `root.after()` or scheduled from the main thread

---

*Generated: 2026-08-04 | J.A.R.V.I.S. v3.0*
