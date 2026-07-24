# 🤖 AI Meeting Assistant

A stealth AI assistant that sits on your desktop, helps during online meetings, and is **completely invisible when you share your screen**.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🛡️ **Screen Share Invisible** | Uses Windows API to hide from Zoom, Teams, Meet, Discord |
| 🎙️ **Live Transcription** | Listens to your mic and transcribes in real-time |
| 💬 **AI Chat** | Ask anything — context-aware answers from Gemini AI |
| 📝 **Smart Summaries** | One-click meeting summaries and action items |
| ✍️ **Rephrase Tool** | Make your text sound more professional |
| 🌐 **Chrome Extension** | Auto-detects your active meeting |
| 🌍 **Auto Language** | Works in English and Arabic automatically |

---

## 🚀 Quick Start

### Step 1 — First time only (setup)
Double-click **`setup.bat`** — installs all required packages.

### Step 2 — Get your free Gemini API Key
1. Go to **https://aistudio.google.com**
2. Sign in with your Google account
3. Click **"Get API Key"** → **"Create API key"**
4. Copy the key (starts with `AIza...`)

### Step 3 — Launch the app
Double-click **`start.bat`**

### Step 4 — Enter your API key
- In the floating overlay, click the **⚙ gear icon**
- Paste your Gemini API key
- Click **Save** — you only need to do this once!

### Step 5 — Install Chrome Extension (optional but recommended)
1. Open Chrome → go to `chrome://extensions/`
2. Enable **Developer Mode** (top right toggle)
3. Click **"Load unpacked"**
4. Select the `chrome-extension` folder in this project
5. The extension icon appears in your toolbar

---

## ⌨️ Hotkeys

| Hotkey | Action |
|--------|--------|
| `Ctrl+Shift+Space` | Show / Hide the overlay |

---

## 📁 Project Structure

```
project ai/
├── backend/
│   ├── main.py              # FastAPI server (port 8000)
│   ├── gemini_client.py     # AI wrapper
│   ├── transcription.py     # Speech-to-text
│   └── requirements.txt     # Python packages
├── overlay/
│   ├── hud.py               # Main overlay window
│   └── stealth.py           # Screen-capture exclusion
├── chrome-extension/
│   ├── manifest.json
│   ├── content.js           # Meeting detector
│   ├── popup.html           # Extension popup
│   └── popup.js
├── setup.bat                # First-time install
├── start.bat                # Launch everything
└── README.md
```

---

## ❓ Troubleshooting

**Overlay is not invisible in screen share?**
→ Requires Windows 10 version 2004 (Build 19041) or newer. Check: Settings → System → About.

**Transcription not working?**
→ Check your microphone is set as default in Windows Sound settings.

**"Backend not reachable" error?**
→ Make sure you ran `setup.bat` first to install packages.

**AI not responding?**
→ Check that your API key is entered correctly in the ⚙ settings.

---

## 🔒 Privacy

- Everything runs **locally on your computer**
- Audio is only sent to Google's free Speech Recognition API for transcription
- Your questions and meeting context are sent to Gemini API (Google)
- No data is stored on any external server by this app
