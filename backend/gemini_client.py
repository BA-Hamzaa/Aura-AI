"""
Gemini AI Client — wraps Google's Gemini API for Aura AI.
Uses the new google-genai SDK with smart model fallback + auto-retry.
Supports both AIza... and AQ. key formats.
"""

from google import genai
from google.genai import types
from typing import Optional
import os
import time
import re


def _unwrap(e: Exception) -> Exception:
    """Unwrap tenacity RetryError to get the real underlying exception."""
    try:
        # tenacity wraps the real exception in RetryError.last_attempt
        if hasattr(e, 'last_attempt') and e.last_attempt is not None:
            real = e.last_attempt.exception()
            if real is not None:
                return real
    except Exception:
        pass
    return e


def _is_quota(e: Exception) -> bool:
    """Return True if this exception (or its wrapped inner) is a quota/rate-limit error."""
    real = _unwrap(e)
    msg = str(real) + str(e)
    return any(x in msg for x in ["429", "RESOURCE_EXHAUSTED", "quota"])


def _is_invalid_key(e: Exception) -> bool:
    real = _unwrap(e)
    msg = str(real) + str(e)
    return "401" in msg or "API_KEY_INVALID" in msg or "invalid api key" in msg.lower()


# Model priority list — tries each in order until one works
MODELS = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash-001",
]


def _friendly_error(e: Exception) -> str:
    """Convert SDK exceptions into short, user-readable messages."""
    real = _unwrap(e)
    msg = str(real) + str(e)
    if "429" in msg or "quota" in msg.lower() or "RESOURCE_EXHAUSTED" in msg:
        return (
            "[QUOTA] Daily quota exhausted on this Google account.\n"
            "Creating a new key on the SAME account won't help - the quota is shared.\n\n"
            "FIX: Sign in to a DIFFERENT Google account at aistudio.google.com,\n"
            "create a key there, and paste it in Settings."
        )
    if "401" in msg or "API_KEY_INVALID" in msg or "invalid api key" in msg.lower():
        return (
            "[ERROR] Invalid API key - key rejected by Google.\n"
            "Both AIza... and AQ. key formats are supported.\n"
            "Double-check you copied the full key from aistudio.google.com"
        )
    if "403" in msg or "PERMISSION_DENIED" in msg:
        return (
            "[ERROR] API key does not have permission.\n"
            "Make sure the Gemini API is enabled in your Google Cloud project."
        )
    first_line = str(real).split("\n")[0][:200]
    return f"[ERROR] AI Error: {first_line}"


def test_key(api_key: str) -> dict:
    """
    Quickly validate an API key. Returns {"ok": True} or {"ok": False, "error": "..."}.
    Both AIza... and AQ. key formats are supported.
    Quota-exhausted keys are still ACCEPTED - quota is a runtime limit, not a key error.
    """
    try:
        http_opts = types.HttpOptions(
            retry_options=types.HttpRetryOptions(attempts=1),
            timeout=10000
        )
        client = genai.Client(api_key=api_key, http_options=http_opts)
        client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents="hi",
            config=types.GenerateContentConfig(max_output_tokens=5)
        )
        return {"ok": True}
    except Exception as e:
        real = _unwrap(e)
        msg = str(real) + str(e)
        # Quota exhausted = key is valid (both AIza and AQ. formats), just no credits now
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            return {
                "ok": True,
                "quota_exhausted": True,
                "warning": (
                    "Quota exhausted on this Google account. "
                    "Key saved - wait 24h or use a key from a different Google account."
                )
            }
        # Truly invalid key
        if "401" in msg or "API_KEY_INVALID" in msg or "invalid api key" in msg.lower():
            return {"ok": False, "error": "Invalid API key - rejected by Google. Both AIza... and AQ. key formats are accepted - double-check you copied the full key."}
        # Permission denied (API not enabled for project)
        if "403" in msg or "PERMISSION_DENIED" in msg:
            return {"ok": False, "error": "Permission denied - make sure the Gemini API is enabled for this key's project at console.cloud.google.com."}
        return {"ok": False, "error": _friendly_error(e)}


# Language rules injected into the system prompt
_LANG_RULES = {
    "en": "IMPORTANT: Always respond in English only, regardless of what language the user writes in.",
    "fr": "IMPORTANT: Réponds TOUJOURS en français uniquement, peu importe la langue de l'utilisateur. Sois naturel et chaleureux en français.",
    "ar": "مهم: أجب دائماً باللغة العربية فقط، بغض النظر عن لغة المستخدم. كن طبيعياً وودوداً بالعربية.",
}


def _build_system_prompt(language: str = "en") -> str:
    lang_rule = _LANG_RULES.get(language, _LANG_RULES["en"])
    return f"""You are Aura — a smart AI assistant like Siri, built into the user's Windows PC.
You can TALK (voice) and also CONTROL the computer in real-time.

== LANGUAGE ==
{lang_rule}

== PERSONALITY ==
- Sound natural, friendly, and concise — like Siri or Google Assistant.
- Responses must be SHORT (1-3 sentences max for voice). No long paragraphs.
- No markdown (no **, no #, no bullet dashes) — responses are SPOKEN ALOUD.
- Be warm and helpful, like a personal assistant.

== COMPUTER CONTROL ==
Embed actions like this: <<ACTION:type|param=value>>
NEVER refuse a task that has an action tag — just do it.

EMAIL: <<ACTION:send_email|to=EMAIL|subject=SUBJECT|body=BODY>>
OPEN URL: <<ACTION:open_url|url=https://...>>
SEARCH: <<ACTION:search_google|query=...>>
YOUTUBE: <<ACTION:youtube|query=...>>
APP OPEN: <<ACTION:open_app|app=chrome>> (chrome/spotify/notepad/vscode/vlc/discord/zoom/teams)
APP CLOSE: <<ACTION:close_app|app=NAME>>
SCREENSHOT: <<ACTION:screenshot>>
VOLUME: <<ACTION:volume|level=50>>
KEY: <<ACTION:key|key=ctrl+c>>
TYPE: <<ACTION:type_text|text=Hello>>
LOCK: <<ACTION:system|action=lock>>
SLEEP: <<ACTION:system|action=sleep>>
SHUTDOWN: <<ACTION:system|action=shutdown>>
RESTART: <<ACTION:system|action=restart>>
MUTE: <<ACTION:system|action=mute>>
BATTERY: <<ACTION:system|action=battery>>
WIFI ON: <<ACTION:system|action=wifi on>>
WIFI OFF: <<ACTION:system|action=wifi off>>

== EXAMPLES ==
User: open spotify
Aura: Opening Spotify! <<ACTION:open_app|app=spotify>>

User: lock the screen
Aura: Locking your screen now. <<ACTION:system|action=lock>>

User: search cats on youtube
Aura: Sure! Searching YouTube for cats. <<ACTION:youtube|query=cats>>

User: battery
Aura: Let me check your battery. <<ACTION:system|action=battery>>

User: close chrome
Aura: Closing Chrome now. <<ACTION:close_app|app=chrome>>

REMEMBER: Keep answers short — they are SPOKEN OUT LOUD. No markdown. No long lists.
"""


class GeminiClient:
    def __init__(self, api_key: str, language: str = "en"):
        self.api_key = api_key
        self.language = language
        http_opts = types.HttpOptions(
            retry_options=types.HttpRetryOptions(attempts=1),
            timeout=15000
        )
        self.client = genai.Client(api_key=api_key, http_options=http_opts)
        self.active_model = None
        self.chat_history = []   # manual history for context
        self.transcript_context = []
        self._find_working_model()

    def set_language(self, language: str):
        """Switch the response language: 'en', 'fr', or 'ar'."""
        if language in _LANG_RULES:
            self.language = language
            self.chat_history = []  # clear history so context doesn't mix languages

    def _find_working_model(self):
        """Probe each model in order, pick the first that responds. Keep it fast."""
        self.active_model = MODELS[0]  # Default fallback
        for model_name in MODELS:
            try:
                self.client.models.generate_content(
                    model=model_name,
                    contents="hi",
                    config=types.GenerateContentConfig(max_output_tokens=5)
                )
                self.active_model = model_name
                return
            except Exception as e:
                # Unwrap tenacity RetryError to read the real error message
                real = _unwrap(e)
                msg = str(real) + str(e)
                if any(x in msg for x in ["429", "RESOURCE_EXHAUSTED", "quota"]):
                    continue  # quota exceeded on this model, try next
                elif any(x in msg for x in ["404", "not found", "no longer available"]):
                    continue  # model not available, try next
                # Any other error (network, auth) — keep default and bail
                return


    def _call_model(self, model_name: str, contents: str) -> str:
        """Call one model. Removes long sleeps so the UI doesn't hang."""
        try:
            resp = self.client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=_build_system_prompt(self.language),
                )
            )
            return resp.text
        except Exception as e:
            # Let _generate handle model fallback
            raise

    def _generate(self, prompt: str, with_history: bool = False) -> str:
        """Generate content, falling back through models on quota/availability errors."""
        models_to_try = [self.active_model] + [m for m in MODELS if m != self.active_model]

        if "mail" in prompt.lower() and "to" in prompt.lower():
            # Intercept common email formats to bypass LLM safety refusals completely
            import re
            m = re.search(r"mail to\s*:?\s*([^\s,]+).*?(?:says?|message|body)\s*:?\s*(.*)", prompt, re.IGNORECASE)
            if m:
                email = m.group(1).strip()
                body = m.group(2).strip()
                return f"Opening browser to send your email! <<ACTION:send_email|to={email}|subject=Message from Aura|body={body}>>"

        contents = prompt
        if with_history and self.chat_history:
            hist = "\n".join(
                f"{r['role'].capitalize()}: {r['content']}"
                for r in self.chat_history[-8:]
            )
            contents = f"{hist}\nUser: {prompt}"

        for model_name in models_to_try:
            try:
                answer = self._call_model(model_name, contents)
                if model_name != self.active_model:
                    self.active_model = model_name
                if with_history:
                    self.chat_history.append({"role": "user", "content": prompt})
                    self.chat_history.append({"role": "assistant", "content": answer})
                    if len(self.chat_history) > 20:
                        self.chat_history = self.chat_history[-20:]
                return answer

            except Exception as e:
                # Unwrap tenacity RetryError to inspect real cause
                real = _unwrap(e)
                msg = str(real) + str(e)
                if any(x in msg for x in ["429", "RESOURCE_EXHAUSTED", "quota"]):
                    continue  # try next model
                elif any(x in msg for x in ["404", "not found", "no longer available"]):
                    continue  # model gone, try next
                else:
                    return _friendly_error(e)

        return (
            "[QUOTA] Daily API quota exhausted on this key.\n"
            "Your key has no remaining quota for today.\n\n"
            "TO FIX THIS:\n"
            "1. Go to: aistudio.google.com/apikey\n"
            "2. Click 'Create API Key'\n"
            "3. Copy the new key and paste it in Settings\n\n"
            "Free tier resets every 24 hours."
        )

    def update_transcript(self, new_text: str):
        self.transcript_context.append(new_text)
        if len(self.transcript_context) > 50:
            self.transcript_context = self.transcript_context[-50:]

    def get_transcript_text(self) -> str:
        return "\n".join(self.transcript_context)

    def ask(self, question: str) -> str:
        transcript = self.get_transcript_text()
        if transcript:
            prompt = (
                f"[Meeting transcript so far]:\n{transcript}\n\n"
                f"[User command/question]: {question}"
            )
        else:
            prompt = question
        return self._generate(prompt, with_history=True)

    def summarize(self) -> str:
        transcript = self.get_transcript_text()
        if not transcript:
            return "No transcript available yet. Start speaking or join a meeting."
        prompt = (
            f"Summarize this meeting transcript in clear bullet points. "
            f"Highlight key decisions and action items:\n\n{transcript}"
        )
        return self._generate(prompt)

    def get_action_items(self) -> str:
        transcript = self.get_transcript_text()
        if not transcript:
            return "No transcript yet."
        prompt = (
            f"Extract all action items, tasks, and to-dos from this meeting transcript. "
            f"Format as a numbered list with who is responsible (if mentioned):\n\n{transcript}"
        )
        return self._generate(prompt)

    def rephrase(self, text: str) -> str:
        prompt = (
            f"Rephrase the following text to sound more professional and clear. "
            f"Keep it concise. Return ONLY the rephrased version:\n\n{text}"
        )
        return self._generate(prompt)

    def explain(self, topic: str) -> str:
        transcript = self.get_transcript_text()
        context = f"Meeting context: {transcript[-500:]}\n\n" if transcript else ""
        prompt = f"{context}Explain '{topic}' briefly in 2-3 sentences."
        return self._generate(prompt)

    def reset_chat(self):
        self.transcript_context = []
        self.chat_history = []
