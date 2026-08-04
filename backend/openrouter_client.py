"""
AI Client — wraps OpenRouter API for Aura AI.
Uses pure requests to directly call OpenRouter.
"""
import os
import requests
import json
import time
from typing import Optional

MODELS = [
    # -- Confirmed working free models (August 2026) --
    "google/gemma-4-26b-a4b-it:free",          # Fast, reliable
    "nvidia/nemotron-3-super-120b-a12b:free",   # High quality
    "nvidia/nemotron-3-nano-30b-a3b:free",      # Fast fallback
    "poolside/laguna-s-2.1:free",               # Good quality
    "openrouter/free",                          # Auto-router last resort

    # -- Additional free models (may have intermittent availability) --
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "google/gemma-4-31b-it:free",
    "cohere/north-mini-code:free",
]




def _fetch_live_free_models(api_key: str) -> list:
    """Dynamically fetch currently available free models from OpenRouter as last resort."""
    try:
        r = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10
        )
        if r.status_code == 200:
            all_models = r.json().get("data", [])
            return [
                m["id"] for m in all_models
                if str(m.get("pricing", {}).get("prompt", "1")) == "0"
                and ":free" in m["id"]
            ]
    except Exception:
        pass
    return []



def _friendly_error(e: Exception, status_code: int = 0, msg: str = "") -> str:
    """Convert HTTP exceptions into user-readable UI messages."""
    if status_code == 401 or "invalid" in msg.lower():
        return (
            "[ERROR] Invalid API key - rejected by OpenRouter.\n"
            "Double-check you copied the full key from openrouter.ai/keys"
        )
    if status_code == 402 or status_code == 429 or "insufficient_quota" in msg.lower():
        return (
            "[QUOTA] Insufficient OpenRouter credits.\n"
            "Your OpenRouter account is out of credits or hit a rate limit.\n"
            "Go to openrouter.ai to check your balance or ensure you're using free models."
        )
    first_line = str(e).split("\n")[0][:200]
    if not first_line and msg:
        first_line = msg[:200]
    return f"[ERROR] AI Error: {first_line or 'Unknown error'}"

def test_key(api_key: str) -> dict:
    """Quickly validate an API key via an OpenRouter generation.
    Tries multiple models so transient model errors don't block key acceptance.
    """
    # Models to probe when checking key validity
    _TEST_MODELS = [
        "mistralai/mistral-7b-instruct:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "openrouter/free",
    ]
    last_err_msg = ""
    last_status = 0
    for test_model in _TEST_MODELS:
        try:
            r = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "Aura AI"
                },
                json={
                    "model": test_model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5
                },
                timeout=12
            )
            if r.status_code == 200:
                return {"ok": True}

            resp = r.json() if r.text else {}
            err_msg = resp.get("error", {}).get("message", r.text)
            last_err_msg = err_msg
            last_status = r.status_code

            # Auth failure: immediately reject — no point trying other models
            if r.status_code == 401:
                return {"ok": False, "error": _friendly_error(Exception(err_msg), 401, err_msg)}

            # Quota/rate-limit: key is valid but out of credits
            if r.status_code in [402, 429] or "quota" in err_msg.lower() or "insufficient" in err_msg.lower():
                return {
                    "ok": True,
                    "quota_exhausted": True,
                    "warning": (
                        "Key saved, but OpenRouter indicates insufficient credits/quota. "
                        "Make sure you are using free models."
                    )
                }
            # Other model-specific error — try next model
            continue
        except requests.exceptions.Timeout:
            last_err_msg = "Request timed out"
            continue
        except Exception as e:
            last_err_msg = str(e)
            continue

    # All probes failed but NOT due to auth — assume key is valid (might be temporary)
    return {"ok": True, "warning": f"Could not fully verify key (network issue?): {last_err_msg[:100]}"}

_LANG_RULES = {
    "en": "IMPORTANT: Always respond in English only, regardless of what language the user writes in.",
    "fr": "IMPORTANT: Réponds TOUJOURS en français uniquement, peu importe la langue de l'utilisateur.",
    "ar": "مهم: أجب دائماً باللغة العربية فقط، بغض النظر عن لغة المستخدم.",
}

def _build_system_prompt(language: str = "en") -> str:

    lang_rule = _LANG_RULES.get(language, _LANG_RULES["en"])

    return f"""You are J.A.R.V.I.S. — a smart AI assistant like Siri, built into the user's Windows PC.

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



== STRICT RULE: WHEN TO USE ACTION TAGS ==

ONLY embed an <<ACTION:...>> tag when the user EXPLICITLY and DIRECTLY commands you to do something on the computer.

Explicit trigger words: open, launch, start, search on google, find on google, play, send, type, lock, mute, screenshot, close, shutdown, restart, sleep, set volume.



NEVER use action tags for:

- Questions about meaning, definitions, translations ("what does X mean", "translate X", "X in Arabic/French/etc.")

- General knowledge ("what is X", "who is X", "explain X", "how does X work")

- Casual conversation ("hi", "thanks", "what time is it")

- Proactive suggestions: NEVER say "Would you like me to search..." and NEVER open a browser unless explicitly told to.

- Anything the user did NOT explicitly instruct you to do on the computer.



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



User: what does stealth mean in Arabic?

Aura: In Arabic, stealth is takhafi, meaning hidden or covert.



User: translate hello to French

Aura: Hello in French is bonjour. Good evening is bonsoir.



User: how does wifi work?

Aura: Wi-Fi uses radio waves to wirelessly transmit data between your router and your devices.



REMEMBER: Keep answers short — they are SPOKEN OUT LOUD. No markdown. No long lists. NEVER open a browser, app, or website unless the user explicitly asks you to.

"""


class OpenRouterClient:
    def __init__(self, api_key: str, language: str = "en"):
        self.api_key = api_key
        self.language = language
        self.active_model = MODELS[0]
        self.chat_history = [] 
        self.transcript_context = []
        self._find_working_model()

    def set_language(self, language: str):
        if language in _LANG_RULES:
            self.language = language
            self.chat_history = []

    def _find_working_model(self):
        """Probe models in order and pick the first that responds."""
        for model in MODELS:
            try:
                r = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 5
                    },
                    timeout=15
                )
                if r.status_code == 200:
                    self.active_model = model
                    return
                # Auth failure — no point probing further
                if r.status_code == 401:
                    return
            except Exception:
                pass


    def _call_model(self, model_name: str, contents: str) -> str:
        messages = [{"role": "system", "content": _build_system_prompt(self.language)}]
        messages.append({"role": "user", "content": contents})

        r = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Aura AI"
            },
            json={
                "model": model_name,
                "messages": messages
            },
            timeout=40
        )
        
        if r.status_code != 200:
            err_msg = r.json().get("error", {}).get("message", r.text) if r.text else "No response"
            raise Exception(f"HTTP {r.status_code}: {err_msg}")
            
        data = r.json()
        return data["choices"][0]["message"]["content"]

    def _generate(self, prompt: str, with_history: bool = False) -> str:
        # Start with the active model, then try all static models
        models_to_try = [self.active_model] + [m for m in MODELS if m != self.active_model]

        contents = prompt
        if with_history and self.chat_history:
            hist = "\n".join(
                f"{r['role'].capitalize()}: {r['content']}"
                for r in self.chat_history[-8:]
            )
            contents = f"{hist}\nUser: {prompt}"

        last_error = "Unknown error"

        def _handle_critical_error(err_str: str) -> Optional[str]:
            if "401" in err_str or "unauthorized" in err_str.lower():
                return "[ERROR] Invalid API Key. Your OpenRouter key was rejected (401 User not found/Unauthorized). Please generate a new key."
            if "402" in err_str or "429" in err_str or "quota" in err_str.lower():
                return "[QUOTA] Insufficient OpenRouter credits. You are out of credits or hit a rate limit for this model."
            return None

        # Try each model — continue past model-specific errors, but abort on auth/quota
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
                last_error = str(e)
                critical = _handle_critical_error(last_error)
                if critical: return critical
                continue  # Try next model

        # All static models failed — dynamically discover live free models
        live_models = _fetch_live_free_models(self.api_key)
        for model_name in live_models:
            if model_name in models_to_try:
                continue  # Already tried
            try:
                answer = self._call_model(model_name, contents)
                self.active_model = model_name
                if with_history:
                    self.chat_history.append({"role": "user", "content": prompt})
                    self.chat_history.append({"role": "assistant", "content": answer})
                    if len(self.chat_history) > 20:
                        self.chat_history = self.chat_history[-20:]
                return answer
            except Exception as e:
                last_error = str(e)
                critical = _handle_critical_error(last_error)
                if critical: return critical
                continue

        return (
            f"[ERROR] No working AI model found right now.\n"
            f"Last error: {last_error}\n"
            "Please check openrouter.ai for free model availability."
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
            prompt = f"[Meeting transcript so far]:\n{transcript}\n\n[User command/question]: {question}"
        else:
            prompt = question
        return self._generate(prompt, with_history=True)

    def summarize(self) -> str:
        transcript = self.get_transcript_text()
        if not transcript: return "No transcript available yet."
        return self._generate(f"Summarize this meeting transcript in clear bullet points:\n\n{transcript}")

    def get_action_items(self) -> str:
        transcript = self.get_transcript_text()
        if not transcript: return "No transcript yet."
        return self._generate(f"Extract all action items from this meeting transcript:\n\n{transcript}")

    def rephrase(self, text: str) -> str:
        return self._generate(f"Rephrase the following to sound professional:\n\n{text}")

    def explain(self, topic: str) -> str:
        transcript = self.get_transcript_text()
        context = f"Meeting context: {transcript[-500:]}\n\n" if transcript else ""
        return self._generate(f"{context}Explain '{topic}' briefly in 2-3 sentences.")

    def reset_chat(self):
        self.transcript_context = []
        self.chat_history = []
