"""
Gemini AI Client — wraps Google's Gemini API for Aura AI.
Uses the new google-genai SDK with smart model fallback + auto-retry.
"""

from google import genai
from google.genai import types
from typing import Optional
import os
import time
import re


# Model priority list — tries each in order until one works
MODELS = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash-001",
]


def _friendly_error(e: Exception) -> str:
    """Convert SDK exceptions into short, user-readable messages."""
    msg = str(e)
    if "429" in msg or "quota" in msg.lower() or "RESOURCE_EXHAUSTED" in msg:
        return (
            "⚠️ Daily quota exhausted on this Google account.\n"
            "Creating a new key on the SAME account won't help — the quota is shared.\n\n"
            "👉 FIX: Sign in to a DIFFERENT Google account at aistudio.google.com,\n"
            "   create a key there, and paste it in ⚙ Settings."
        )
    if "401" in msg or "API_KEY_INVALID" in msg or "invalid" in msg.lower():
        return (
            "⚠️ Invalid API key — key rejected by Google.\n"
            "👉 Double-check the key in ⚙ Settings (must start with AIza...)"
        )
    if "403" in msg or "PERMISSION_DENIED" in msg:
        return (
            "⚠️ API key doesn't have permission.\n"
            "👉 Make sure the Gemini API is enabled in your Google Cloud project."
        )
    first_line = msg.split("\n")[0][:200]
    return f"⚠️ AI Error: {first_line}"


def test_key(api_key: str) -> dict:
    """
    Quickly validate an API key. Returns {"ok": True} or {"ok": False, "error": "..."}.
    Called from main.py before accepting a new key from the user.
    """
    try:
        client = genai.Client(api_key=api_key)
        client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents="hi",
            config=types.GenerateContentConfig(max_output_tokens=5)
        )
        return {"ok": True}
    except Exception as e:
        msg = str(e)
        if "429" in msg or "quota" in msg.lower() or "RESOURCE_EXHAUSTED" in msg:
            return {
                "ok": False,
                "quota_exhausted": True,
                "error": (
                    "Quota exhausted on this Google account.\n"
                    "Creating extra keys on the same account shares the same limit.\n"
                    "Use a key from a DIFFERENT Google account."
                )
            }
        if "401" in msg or "API_KEY_INVALID" in msg or "invalid" in msg.lower():
            return {"ok": False, "error": "Invalid API key — rejected by Google. Double-check you copied the full key."}
        return {"ok": False, "error": _friendly_error(e)}


SYSTEM_PROMPT = """You are Aura AI — a powerful computer automation assistant. You DIRECTLY CONTROL the user's computer.

CRITICAL: You have a real action execution system. When the user asks you to do ANYTHING on the computer, you MUST embed the correct action tag. You are NOT a regular chatbot — you are a computer controller.

Embed actions using this format: <<ACTION:action_type|param1=value1|param2=value2>>

=== YOUR CAPABILITIES ===

📧 EMAIL (YOU CAN SEND REAL EMAILS):
  <<ACTION:send_email|to=EMAIL|subject=SUBJECT|body=BODY>>
  - This opens Gmail and sends the email automatically. IT WORKS.
  - If user says "send mail to X says Y" → use subject="Message" body=Y

🌐 WEB & BROWSER:
  <<ACTION:open_url|url=https://...>>
  <<ACTION:search_google|query=...>>
  <<ACTION:youtube|query=...>>

💬 DISCORD:
  <<ACTION:discord_send|message=...>>
  <<ACTION:open_app|app=discord>>

🖥️ APPS:
  <<ACTION:open_app|app=chrome>>      (also: spotify, notepad, vscode, vlc, zoom, teams...)
  <<ACTION:close_app|app=spotify>>
  <<ACTION:screenshot>>
  <<ACTION:volume|level=50>>
  <<ACTION:key|key=ctrl+c>>
  <<ACTION:type_text|text=Hello>>

⚡ SYSTEM:
  <<ACTION:system|action=lock>>
  <<ACTION:system|action=sleep>>
  <<ACTION:system|action=shutdown>>
  <<ACTION:system|action=restart>>
  <<ACTION:system|action=mute>>
  <<ACTION:system|action=wifi on>>
  <<ACTION:system|action=wifi off>>
  <<ACTION:system|action=battery>>

=== STRICT RULES ===
1. ALWAYS use action tags for any computer task — never refuse.
2. NEVER say "I can't", "I don't have the ability", "I'm unable to" for tasks that have action tags.
3. NEVER say you cannot send emails — you CAN via <<ACTION:send_email|...>>.
4. If email subject is missing, use "Message". If body is missing, use what the user said.
5. Be short and direct. Just confirm + embed the tag.
6. Support English and Arabic — respond in same language as user.
7. Chain multiple actions if needed.

=== FORBIDDEN PHRASES (NEVER SAY THESE) ===
- "I can't send emails"
- "I don't have that functionality"  
- "I'm unable to"
- "I cannot directly"
- "I don't have access to"

=== EXAMPLES ===
User: "send mail to hamza@gmail.com says hi how are you"
You: "Sending the email now! <<ACTION:send_email|to=hamza@gmail.com|subject=Message|body=hi how are you>>"

User: "send mail to :john@gmail.com , says : meeting tomorrow at 9am"
You: "Sending! <<ACTION:send_email|to=john@gmail.com|subject=Meeting|body=meeting tomorrow at 9am>>"

User: "open youtube"
You: "Opening YouTube! <<ACTION:youtube>>"

User: "close discord"
You: "Closing Discord. <<ACTION:close_app|app=discord>>"

User: "lock screen"
You: "Locking screen! <<ACTION:system|action=lock>>"

User: "open google and search python"  
You: "Searching Google for Python! <<ACTION:search_google|query=python>>"
"""



class GeminiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)
        self.active_model = None
        self.chat_history = []   # manual history for context
        self.transcript_context = []
        self._find_working_model()

    def _find_working_model(self):
        """Probe each model in order, pick the first that responds."""
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
                msg = str(e)
                if any(x in msg for x in ["429", "RESOURCE_EXHAUSTED", "quota"]):
                    continue  # quota exceeded, try next
                elif "404" in msg or "not found" in msg.lower() or "no longer available" in msg.lower():
                    continue  # model not available
                # Unknown error — stop here, use this model anyway
                self.active_model = model_name
                return

        # All models exhausted quota — default to first, errors will surface as friendly messages
        self.active_model = MODELS[0]


    def _call_model(self, model_name: str, contents: str) -> str:
        """Call one model with automatic retry on per-minute rate limits."""
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                resp = self.client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                    )
                )
                return resp.text
            except Exception as e:
                msg = str(e)
                is_quota = any(x in msg for x in ["429", "RESOURCE_EXHAUSTED", "quota"])
                if not is_quota:
                    raise  # non-quota error, let caller handle

                # Check if this is a daily limit (limit: 0) or per-minute (short retry)
                is_daily = "limit: 0" in msg
                retry_match = re.search(r'seconds: (\d+)', msg)
                retry_secs = int(retry_match.group(1)) if retry_match else 60

                if is_daily or retry_secs > 120 or attempt >= max_retries:
                    raise  # daily limit or too long to wait — bubble up

                # Per-minute limit: wait and retry
                time.sleep(min(retry_secs + 2, 35))
        raise Exception("Max retries reached")

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
                msg = str(e)
                if any(x in msg for x in ["429", "RESOURCE_EXHAUSTED", "quota"]):
                    continue  # try next model
                elif "404" in msg or "not found" in msg.lower() or "no longer available" in msg.lower():
                    continue  # model gone, try next
                else:
                    return _friendly_error(e)

        return (
            "⚠️ Daily API quota exhausted on this key.\n"
            "Your key has no remaining quota for today.\n\n"
            "👉 TO FIX THIS:\n"
            "1. Go to: aistudio.google.com/apikey\n"
            "2. Click 'Create API Key'\n"
            "3. Copy the new key (starts with AIza...)\n"
            "4. Click ⚙ Settings in this app and paste it in\n\n"
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
