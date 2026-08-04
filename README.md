# 🤖 J.A.R.V.I.S. — Personal AI Assistant

> *Just A Rather Very Intelligent System*

A **production-grade** desktop AI assistant inspired by Iron Man's JARVIS. It runs silently on your Windows desktop, talks to you, controls your computer, remembers everything across sessions, and is **completely invisible when you share your screen**.

---

## ✨ Features

### 🧠 Intelligence
| Feature | Description |
|---------|-------------|
| 💬 **AI Chat** | Context-aware conversations powered by OpenRouter (free models) |
| 🧩 **Long-Term Memory** | Remembers facts, preferences, tasks and projects across sessions |
| 🗺️ **Smart Planning** | Decomposes complex requests into steps before executing |
| 🔒 **Safety Layer** | Classifies risk level — requires confirmation for dangerous actions |
| 🌍 **Multilingual** | Full UI + AI responses in English, French, and Arabic |

### 🎙️ Voice & Audio
| Feature | Description |
|---------|-------------|
| 🎤 **Voice Input** | Speak to J.A.R.V.I.S. directly via microphone |
| 🔊 **Text-to-Speech** | Responds out loud like Siri (pyttsx3 + Windows SAPI) |
| 💤 **Wake Word** | Say *"Jarvis"* to activate hands-free |
| 📝 **Live Transcription** | Transcribes meetings in real-time |
| 📋 **Smart Summaries** | One-click meeting summaries and action items |

### 🖥️ Desktop Automation
| Feature | Description |
|---------|-------------|
| 🚀 **Open/Close Apps** | Chrome, Spotify, VS Code, Discord, and more |
| 🌐 **Web Actions** | Search Google, open URLs, search YouTube |
| 📸 **Screenshot** | Capture and save the screen |
| 🔊 **Volume Control** | Set system volume (0–100%) |
| 🔒 **System Controls** | Lock, sleep, shutdown, restart |
| ✉️ **Email (Gmail)** | Draft and send emails via browser |
| 💬 **Discord Messages** | Send messages to Discord channels |
| 📡 **Wi-Fi Toggle** | Enable / disable Wi-Fi |

### 🔌 Plugin System
| Feature | Description |
|---------|-------------|
| 🌤️ **Weather** | Current weather for any city (no API key needed) |
| 🧮 **Calculator** | Safe math expression evaluator |
| 📋 **Clipboard** | Read/write system clipboard |
| 💻 **System Monitor** | CPU, RAM, disk usage live stats |
| 🧩 **Custom Plugins** | Drop `.py` files in `/plugins/` — auto-loaded at startup |

### 🛡️ Privacy & Stealth
| Feature | Description |
|---------|-------------|
| 👻 **Screen Share Invisible** | Hidden from Zoom, Teams, Meet, Discord, OBS via Windows API |
| 🔕 **Taskbar Hidden** | Does not appear in the taskbar or Alt+Tab |
| 💾 **Local Memory** | All memory stored locally in SQLite — nothing sent externally |
| 🔑 **API Key Only** | Only your questions go to OpenRouter; no personal data |

---

## 🚀 Quick Start

### Step 1 — First-time setup
```bash
# Double-click or run in terminal:
setup.bat
```
Installs all required Python packages automatically.

### Step 2 — Get a free OpenRouter API Key
1. Go to **https://openrouter.ai** and create a free account
2. Navigate to **Keys** → **Create Key**
3. Copy the key (starts with `sk-or-...`)
4. Free models are available with no credit card required

### Step 3 — Launch J.A.R.V.I.S.
```bash
# Double-click:
start.bat

# Or for a completely silent background launch:
"Aura AI.vbs"
```

### Step 4 — Enter your API key
- In the floating overlay, click the **⚙ gear icon**
- Paste your OpenRouter API key
- Click **Save** — stored securely in `.env`, only done once

### Step 5 — (Optional) Install Chrome Extension
1. Open Chrome → go to `chrome://extensions/`
2. Enable **Developer Mode** (top-right toggle)
3. Click **"Load unpacked"** → select the `chrome-extension/` folder
4. J.A.R.V.I.S. will auto-detect when you join a Zoom/Meet/Teams call

---

## ⌨️ Hotkeys

| Hotkey | Action |
|--------|--------|
| `Ctrl+Shift+Space` | Show / Hide the overlay |
| `Alt+Space` | Quick voice input |

---

## 💬 Example Commands

### Voice or Chat
```
"Open Spotify"                      → Launches Spotify
"Search cats on YouTube"            → Opens YouTube search
"What is my battery level?"         → Reports battery %
"Lock the screen"                   → Locks workstation
"Set volume to 60"                  → Adjusts audio volume
"Take a screenshot"                 → Saves to Desktop
"Send email to john@email.com about project update"
"Remember that I prefer dark mode"  → Saves to memory
"What did I tell you about my projects?" → Recalls from memory
"What's the weather in Paris?"      → Live weather via plugin
"Calculate 2^10 + 5*3"              → Safe math eval
```

### Action Tag System (AI embeds these automatically)
```
<<ACTION:open_app|app=spotify>>
<<ACTION:search_google|query=python tutorials>>
<<ACTION:system|action=lock>>
<<ACTION:volume|level=70>>
<<ACTION:send_email|to=a@b.com|subject=Hello|body=Message>>
```

---

## 📁 Project Structure

```
project ai/
├── backend/
│   ├── main.py               # FastAPI server — 40+ REST endpoints
│   ├── openrouter_client.py  # AI client with multi-model fallback
│   ├── memory.py             # Long-term SQLite memory + semantic search
│   ├── planner.py            # Request decomposition & risk classification
│   ├── plugins.py            # Plugin SDK + built-in plugins
│   ├── task_manager.py       # Background task executor
│   ├── logger.py             # Structured JSON logging + perf tracking
│   ├── automation.py         # Desktop automation tools
│   ├── tts_engine.py         # Text-to-speech engine (pyttsx3/SAPI)
│   ├── transcription.py      # Speech-to-text engine
│   ├── wake_word.py          # Wake word detection
│   ├── requirements.txt      # Python dependencies
│   ├── .env                  # API keys (never committed)
│   └── jarvis_memory.db      # SQLite memory store (auto-created)
│
├── overlay/
│   ├── hud.py                # Premium Tkinter HUD overlay
│   ├── stealth.py            # Win32 screen-capture exclusion
│   └── brain_icon.png/ico    # App icon
│
├── plugins/                  # Drop custom plugins here
│   ├── __init__.py
│   └── example_plugin.py     # Plugin template
│
├── chrome-extension/         # Browser integration
│   ├── manifest.json
│   ├── content.js
│   └── popup.html/js
│
├── logs/                     # Auto-created rotating JSON logs
├── ARCHITECTURE.md           # Full system architecture docs
├── setup.bat                 # First-time install
├── start.bat                 # Launch script
└── "Aura AI.vbs"             # Silent background launcher
```

---

## 🔌 API Reference (Backend — `localhost:8000`)

```
GET  /                            Status + system info
POST /api/ask                     Chat with AI
POST /api/voice_ask               Voice-triggered AI response
POST /api/key                     Set OpenRouter API key
POST /api/language                Set language (en/fr/ar)
POST /api/plan                    Get execution plan for request

GET  /api/memory/facts            List remembered facts
POST /api/memory/remember         Store a fact
POST /api/memory/recall           Semantic memory search
GET  /api/memory/history          Conversation history

POST /api/tasks                   Create a task
GET  /api/tasks                   List tasks
POST /api/reminders               Set a reminder

GET  /api/plugins                 List loaded plugins
POST /api/plugins/call            Call a plugin tool
POST /api/plugins/reload          Hot-reload plugins

GET  /api/logs                    Recent log entries
GET  /api/logs/performance        AI response timing stats

WS   /ws                          Real-time WebSocket updates
```

> Full API docs at `http://localhost:8000/docs` (Swagger UI, auto-generated)

---

## 🧩 Plugin SDK

Create a file in the `/plugins/` folder:

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
        )

    def tools(self) -> dict:
        return {"do_thing": self.do_thing}

    def do_thing(self, text: str) -> str:
        return f"Done: {text}"
```

J.A.R.V.I.S. auto-discovers and loads it at startup. Call it via:
- API: `POST /api/plugins/call` `{"tool": "do_thing", "kwargs": {"text": "hello"}}`
- Chat: *"Use my_plugin to do the thing with hello"*

---

## ❓ Troubleshooting

**Overlay is not invisible in screen share?**
→ Requires **Windows 10 Build 19041** or newer. Check: Settings → System → About.

**Voice input not working?**
→ Set your microphone as the default in Windows Sound settings → Input.

**"Backend not reachable" error?**
→ Run `setup.bat` first, then `start.bat`. The backend needs a few seconds to start.

**"No working AI model found"?**
→ Your API key may be invalid or OpenRouter is temporarily unavailable. Try a new key at `openrouter.ai/keys`.

**Memory not persisting between sessions?**
→ Check that `backend/jarvis_memory.db` exists. If deleted, memory resets.

**Plugin not loading?**
→ Ensure your plugin class inherits from `BasePlugin` and `plugins/` is in the project root.

---

## 🏗️ Architecture

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the full system design including:
- Layered architecture diagram
- Database schema
- Memory architecture
- Multi-agent orchestration
- Security model
- Full API reference
- Implementation roadmap

---

## 🔒 Privacy

- All memory is stored **locally** in `jarvis_memory.db` — nothing uploaded
- Only your chat questions and AI responses are sent to **OpenRouter** (your chosen LLM)
- Voice transcription uses Google's free Speech Recognition API
- No personal data is collected or stored by this app externally
- The stealth mode only prevents screen capture — it doesn't hide any network traffic

---

## 📋 Roadmap

- [x] AI chat + voice (TTS/STT)
- [x] Desktop automation (apps, browser, system)
- [x] Stealth mode (screen-share invisible)
- [x] Wake word detection
- [x] Multilingual UI (EN/FR/AR)
- [x] Long-term memory (SQLite)
- [x] Plugin SDK with built-in plugins
- [x] Planning & risk classification
- [x] Background task manager
- [x] Structured logging
- [ ] Vision / OCR (screen understanding)
- [ ] Knowledge base (PDF/Markdown indexing)
- [ ] Browser automation (Playwright)
- [ ] Local LLM support (Ollama)
- [ ] Calendar & scheduling integration
- [ ] Advanced HUD tabs (Memory, Logs, Tasks)

---

*J.A.R.V.I.S. v3.0 — Built with ❤️ using FastAPI, Tkinter, OpenRouter, and SQLite*
