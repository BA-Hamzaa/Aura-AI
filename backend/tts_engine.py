"""
tts_engine.py \u2014 Text-to-Speech for Aura AI.
Speaks AI responses aloud using Windows SAPI (built-in, no install needed)
with a fallback to pyttsx3 if available.
"""

import threading
import queue
import re
import os
import sys

# \u2500\u2500 Try pyttsx3 first (cross-platform, better voice options) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
try:
    import pyttsx3
    import pythoncom
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

# \u2500\u2500 Windows SAPI fallback via ctypes \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
SAPI_AVAILABLE = sys.platform == "win32"


def _clean_for_speech(text: str) -> str:
    """Strip markdown, action tags, emojis, and special chars for clean TTS."""
    text = re.sub(r"<<ACTION:[^>]*>>", "", text)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(
        r"[\U0001F300-\U0001FFFF\U00002600-\U000027BF\U0000FE00-\U0000FEFF]+",
        "", text, flags=re.UNICODE
    )
    text = re.sub(r"[✅❌⚠️🔋🎤🖥️📸🔊🌐🔍💬🎵💻📝🧮🗂🎬🚀⚡📋✍️]", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class TTSEngine:
    """
    Thread-safe TTS engine using a single dedicated worker thread and queue.
    This fixes COM crashes on Windows.
    """

    def __init__(self):
        self._enabled = True
        self._volume = 1.0
        self._rate = 185
        self._queue = queue.Queue()
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()

    def _worker(self):
        engine = None
        if PYTTSX3_AVAILABLE:
            try:
                pythoncom.CoInitialize()
                engine = pyttsx3.init()
                engine.setProperty("rate", self._rate)
                engine.setProperty("volume", self._volume)
                voices = engine.getProperty("voices")
                if voices:
                    female = [v for v in voices if any(n in v.name for n in ["Zira", "Helena", "Hazel", "Female", "female"])]
                    engine.setProperty("voice", female[0].id if female else voices[0].id)
            except Exception:
                engine = None

        while True:
            text = self._queue.get()
            if text is None: break  
            if not self._enabled:
                self._queue.task_done()
                continue
            
            try:
                if engine:
                    engine.setProperty("rate", self._rate)
                    engine.setProperty("volume", self._volume)
                    engine.say(text)
                    engine.runAndWait()
                elif SAPI_AVAILABLE:
                    import subprocess
                    safe = text.replace("'", "''")
                    cmd = (
                        f"Add-Type -AssemblyName System.Speech; "
                        f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                        f"$s.Rate = 3; "
                        f"$s.Speak('{safe}')"
                    )
                    subprocess.run(
                        ["powershell", "-WindowStyle", "Hidden", "-Command", cmd],
                        capture_output=True, timeout=30
                    )
            except Exception:
                pass
            finally:
                self._queue.task_done()

    # ── Public API ────────────────────────────────────────────────────────────

    def speak(self, text: str, interrupt: bool = True):
        if not self._enabled: return
        clean = _clean_for_speech(text)
        if not clean: return
        
        if interrupt:
            self.stop()
        self._queue.put(clean)

    def stop(self):
        # Empty the queue
        with self._queue.mutex:
            self._queue.queue.clear()
        # pyttsx3 native stop from another thread is too dangerous on Windows COM,
        # so we just let current speech finish if it's already speaking. 

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        if not enabled:
            self.stop()

    def set_rate(self, rate: int):
        self._rate = rate

    def set_volume(self, volume: float):
        self._volume = max(0.0, min(1.0, volume))

    @property
    def available(self) -> bool:
        return PYTTSX3_AVAILABLE or SAPI_AVAILABLE


# Singleton instance used across the app
tts = TTSEngine()
