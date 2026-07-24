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
            "⚠️ API quota exceeded.\n"
            "Your free-tier limit has been used up for today.\n"
            "👉 Solution: Go to aistudio.google.com, create a NEW API key\n"
            "   from a different Google account, then click ⚙ Settings to update it."
        )
    if "401" in msg or "API_KEY_INVALID" in msg or "invalid" in msg.lower():
        return (
            "⚠️ Invalid API key.\n"
            "👉 Open ⚙ Settings and check your Gemini API key."
        )
    if "403" in msg or "PERMISSION_DENIED" in msg:
        return (
            "⚠️ API key doesn't have permission.\n"
            "👉 Make sure the Gemini API is enabled in your Google Cloud project."
        )
    first_line = msg.split("\n")[0][:200]
    return f"⚠️ AI Error: {first_line}"


SYSTEM_PROMPT = """You are Aura AI — intelligent, fast, and capable of controlling the computer.

You can EXECUTE REAL ACTIONS on his computer by embedding action tags in your response.
Use this format: <<ACTION:action_type|param1=value1|param2=value2>>

=== AVAILABLE ACTIONS ===

🌐 WEB & BROWSER:
  - Open a URL:           <<ACTION:open_url|url=https://google.com>>
  - Google search:        <<ACTION:search_google|query=your search here>>
  - Open YouTube:         <<ACTION:youtube|query=lofi music>>
  - Open YouTube (home):  <<ACTION:youtube>>

💬 DISCORD:
  - Send a message:       <<ACTION:discord_send|message=Hey! How are you?>>
  - Open Discord:         <<ACTION:open_app|app=discord>>

🖥️ APPS & SYSTEM:
  - Open any app:         <<ACTION:open_app|app=chrome>>
  - Open calculator:      <<ACTION:open_app|app=calculator>>
  - Open VS Code:         <<ACTION:open_app|app=vscode>>
  - Open Spotify:         <<ACTION:open_app|app=spotify>>
  - Open Notepad:         <<ACTION:open_app|app=notepad>>
  - Take screenshot:      <<ACTION:screenshot>>
  - Set volume (0-100):   <<ACTION:volume|level=50>>
  - Press a key/hotkey:   <<ACTION:key|key=ctrl+c>>
  - Type text:            <<ACTION:type_text|text=Hello world>>

=== RULES ===
1. When the user asks you to do something on the computer (open, search, send, launch, etc.), ALWAYS embed the correct action tag.
2. You can combine a normal text reply WITH an action tag in the same response.
3. Remove the action tag from the visible text naturally — just embed it where it fits.
4. When sending Discord messages, confirm what you're sending and to whom.
5. Be concise and direct. Don't over-explain.
6. Support both English and Arabic — auto-detect and respond in the same language.
7. You can chain multiple actions in one response if needed.

=== EXAMPLES ===
User: "Open Google"
You: "Opening Google for you! <<ACTION:open_url|url=https://google.com>>"

User: "Search for Python tutorials on Google"
You: "Searching Google for Python tutorials. <<ACTION:search_google|query=Python tutorials>>"

User: "Send a message on Discord saying 'I'll be right back'"
You: "Sending that message to Discord now! <<ACTION:discord_send|message=I'll be right back>>"

User: "Open YouTube and search for lofi music"
You: "Opening YouTube with lofi music search! <<ACTION:youtube|query=lofi music>>"

User: "Take a screenshot"
You: "Screenshot taken and saved to your Desktop! <<ACTION:screenshot>>"

User: "Set volume to 30%"
You: "Volume set to 30%. <<ACTION:volume|level=30>>"

You are smart enough to understand natural language commands and map them to the right actions.
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

        contents = prompt
        if with_history and self.chat_history:
            hist = "\n".join(
                f"{'User' if r['role'] == 'user' else 'Assistant'}: {r['content']}"
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
