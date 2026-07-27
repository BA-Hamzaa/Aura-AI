"""
wake_word.py — Lightweight wake-word detector for Aura AI.
Listens in background for "hey aura" or "aura" and triggers a callback.
Uses Google STT (same as main voice engine) — no extra packages needed.
"""

import threading
import speech_recognition as sr


class WakeWordDetector:
    """
    Continuously listens in a background thread.
    When wake word is detected, calls `on_wake_word()`.
    """

    WAKE_WORDS = [
        "hey aura", "hi aura", "okay aura", "ok aura",
        "aura", "هيا أورا", "أورا",
    ]

    def __init__(self, on_wake_word, sensitivity: float = 0.0):
        self._on_wake_word = on_wake_word
        self._running = False
        self._thread = None
        self._sensitivity = sensitivity

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 2500
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.5

        while self._running:
            try:
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    while self._running:
                        try:
                            audio = recognizer.listen(
                                source,
                                timeout=4,
                                phrase_time_limit=3
                            )
                            text = recognizer.recognize_google(audio).lower().strip()
                            for ww in self.WAKE_WORDS:
                                if ww in text:
                                    self._on_wake_word()
                                    break
                        except sr.WaitTimeoutError:
                            continue
                        except sr.UnknownValueError:
                            continue
                        except sr.RequestError:
                            break  # network issue, will retry outer loop
                        except Exception:
                            continue
            except Exception:
                if self._running:
                    import time
                    time.sleep(2)
