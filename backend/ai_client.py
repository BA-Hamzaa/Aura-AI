"""
AI Client — wraps OpenRouter API for Aura AI.
Uses pure requests to directly call OpenRouter.
"""
import os
import requests
import json
import time

MODELS = [
    # Premium / highly reliable fast models
    "google/gemini-2.5-flash", 
    "google/gemini-2.0-flash-lite-preview-02-05:free",
    "meta-llama/llama-3-8b-instruct:free"
]

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
            "Go to openrouter.ai to check your balance."
        )
    first_line = str(e).split("\n")[0][:200]
    if not first_line and msg:
        first_line = msg[:200]
    return f"[ERROR] AI Error: {first_line or 'Unknown error'}"

def test_key(api_key: str) -> dict:
    """Quickly validate an API key via a tiny OpenRouter generation."""
    try:
        r = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "meta-llama/llama-3-8b-instruct:free",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 5
            },
            timeout=10
        )
        if r.status_code == 200:
            return {"ok": True}
        
        # Parse error
        resp = r.json()
        err_msg = resp.get("error", {}).get("message", "")
        
        if r.status_code in [402, 429] or "quota" in err_msg.lower():
            return {
                "ok": True,
                "quota_exhausted": True,
                "warning": (
                    "Key saved, but OpenRouter indicates insufficient credits/quota. "
                    "Make sure you have funds or are using free models."
                )
            }
        return {"ok": False, "error": _friendly_error(Exception(err_msg), r.status_code, err_msg)}
    except Exception as e:
        return {"ok": False, "error": _friendly_error(e)}


_LANG_RULES = {
    "en": "IMPORTANT: Always respond in English only, regardless of what language the user writes in.",
    "fr": "IMPORTANT: Réponds TOUJOURS en français uniquement, peu importe la langue de l'utilisateur.",
    "ar": "مهم: أجب دائماً باللغة العربية فقط، بغض النظر عن لغة المستخدم.",
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
