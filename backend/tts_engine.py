"""
tts_engine.py — Text-to-Speech for Aura AI.
Speaks AI responses aloud using Windows SAPI (built-in, no install needed)
with a fallback to pyttsx3 if available.
"""

import threading
import re
import os
import sys

# ── Try pyttsx3 first (cross-platform, better voice options) ─────────────────
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

# ── Windows SAPI fallback via ctypes ─────────────────────────────────────────
SAPI_AVAILABLE = sys.platform == "win32"


def _clean_for_speech(text: str) -> str:
    """Strip markdown, action tags, emojis, and special chars for clean TTS."""
    # Remove action tags <<ACTION:...>>
    text = re.sub(r"<<ACTION:[^>]*>>", "", text)
    # Remove markdown bold/italic
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    # Remove markdown headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove emojis (broad unicode range)
    text = re.sub(
        r"[\U0001F300-\U0001FFFF\U00002600-\U000027BF\U0000FE00-\U0000FEFF]+",
        "", text, flags=re.UNICODE
    )
    # Remove common emoji symbols and special chars used in the app
    text = re.sub(r"[✅❌⚠️🔋🎤🖥️📸🔊🌐🔍💬🎵💻📝🧮🗂🎬🚀⚡📋✍️]", "", text)
    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    # Collapse multiple spaces/newlines
    text = re.sub(r"\s+", " ", text).strip()
    return text


class TTSEngine:
    """
    Thread-safe TTS engine. Speaks text in a background thread.
    pyttsx3 is initialized lazily (first use) to avoid blocking startup.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._engine = None
        self._engine_ready = False
        self._engine_failed = False
        self._enabled = True
        self._volume = 1.0
        self._rate = 185
        # Init in background thread so server starts instantly
        threading.Thread(target=self._init_engine, daemon=True).start()

    def _init_engine(self):
        """Initialize pyttsx3 in background — never blocks the caller."""
        if not PYTTSX3_AVAILABLE:
            self._engine_failed = True
            return
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", self._rate)
            engine.setProperty("volume", self._volume)
            voices = engine.getProperty("voices")
            if voices:
                female = [v for v in voices if any(
                    n in v.name for n in ["Zira", "Helena", "Hazel", "Female", "female"]
                )]
                engine.setProperty(
                    "voice", female[0].id if female else voices[0].id
                )
            self._engine = engine
            self._engine_ready = True
        except Exception:
            self._engine_failed = True

    # ── Public API ────────────────────────────────────────────────────────────

    def speak(self, text: str, interrupt: bool = True):
        """Speak text. If interrupt=True, cancel current speech first."""
        if not self._enabled:
            return
        clean = _clean_for_speech(text)
        if not clean:
            return
        if interrupt:
            self.stop()
        threading.Thread(target=self._speak_worker, args=(clean,), daemon=True).start()

    def stop(self):
        """Stop any ongoing speech immediately."""
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        if not enabled:
            self.stop()

    def set_rate(self, rate: int):
        self._rate = rate
        if self._engine:
            try:
                self._engine.setProperty("rate", rate)
            except Exception:
                pass

    def set_volume(self, volume: float):
        self._volume = max(0.0, min(1.0, volume))
        if self._engine:
            try:
                self._engine.setProperty("volume", self._volume)
            except Exception:
                pass

    @property
    def available(self) -> bool:
        return self._engine_ready or SAPI_AVAILABLE

    # ── Internal ──────────────────────────────────────────────────────────────

    def _speak_worker(self, text: str):
        """Run TTS in this thread."""
        with self._lock:
            try:
                if self._engine_ready and self._engine:
                    self._speak_pyttsx3(text)
                elif SAPI_AVAILABLE:
                    self._speak_sapi(text)
            except Exception:
                pass

    def _speak_pyttsx3(self, text: str):
        try:
            # Re-init engine if it was stopped mid-speech
            if not self._engine:
                return
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception:
            # pyttsx3 can crash; fall back to SAPI
            self._engine = None
            if SAPI_AVAILABLE:
                self._speak_sapi(text)

    def _speak_sapi(self, text: str):
        """Use Windows SAPI via PowerShell — no extra packages needed."""
        try:
            import subprocess
            # Escape single quotes in text
            safe = text.replace("'", "''")
            cmd = (
                f"Add-Type -AssemblyName System.Speech; "
                f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$s.Rate = 3; "
                f"$s.Speak('{safe}')"
            )
            subprocess.run(
                ["powershell", "-WindowStyle", "Hidden", "-Command", cmd],
                capture_output=True,
                timeout=30
            )
        except Exception:
            pass


# Singleton instance used across the app
tts = TTSEngine()
