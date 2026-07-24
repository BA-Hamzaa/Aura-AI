"""
Transcription Engine — captures microphone audio and converts to text
using Google's free Speech Recognition API.
Runs in a background thread and pushes text via a callback.
"""

import speech_recognition as sr
import threading
import queue
from typing import Callable, Optional


class TranscriptionEngine:
    def __init__(self, on_text: Callable[[str], None], on_error: Optional[Callable[[str], None]] = None):
        """
        Args:
            on_text: Callback called with each recognized text chunk.
            on_error: Optional callback called with error messages.
        """
        self.on_text = on_text
        self.on_error = on_error or (lambda e: print(f"[Transcription Error] {e}"))
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._mic: Optional[sr.Microphone] = None
        self._stop_event = threading.Event()

    def start(self):
        """Start continuous transcription in background thread."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop transcription."""
        self._running = False
        self._stop_event.set()

    def _listen_loop(self):
        """Continuous listening loop using background listening."""
        try:
            mic_list = sr.Microphone.list_microphone_names()
            print(f"[Transcription] Available mics: {mic_list}")
        except Exception:
            pass

        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                print("[Transcription] Microphone ready, listening...")

                while self._running and not self._stop_event.is_set():
                    try:
                        audio = self.recognizer.listen(
                            source,
                            timeout=5,
                            phrase_time_limit=10
                        )
                        # Run recognition in a separate thread so we keep listening
                        threading.Thread(
                            target=self._recognize,
                            args=(audio,),
                            daemon=True
                        ).start()
                    except sr.WaitTimeoutError:
                        continue  # No speech, keep looping
                    except Exception as e:
                        if self._running:
                            self.on_error(f"Listen error: {e}")
                        break

        except Exception as e:
            self.on_error(f"Microphone error: {e}")

    def _recognize(self, audio: sr.AudioData):
        """Run Google STT on an audio chunk."""
        try:
            text = self.recognizer.recognize_google(audio, show_all=False)
            if text and text.strip():
                self.on_text(text.strip())
        except sr.UnknownValueError:
            pass  # Silence or unintelligible — ignore
        except sr.RequestError as e:
            self.on_error(f"Google STT API error: {e}")
        except Exception as e:
            self.on_error(f"Recognition error: {e}")

    @staticmethod
    def list_microphones() -> list:
        """Return list of available microphone names."""
        try:
            return sr.Microphone.list_microphone_names()
        except Exception:
            return []
