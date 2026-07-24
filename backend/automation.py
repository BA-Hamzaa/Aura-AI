"""
automation.py — Real-world action executor for Aura AI.

Handles commands parsed from AI responses:
  - open_url        → Opens a URL in the default browser
  - open_app        → Launches an installed application
  - discord_send    → Sends a message in Discord (active channel)
  - type_text       → Types text using the keyboard
  - screenshot      → Takes a screenshot and saves it
  - search_google   → Opens Google with a search query
  - volume          → Controls system volume
  - close_app       → Closes a running application
"""

import os
import re
import time
import subprocess
import threading
import webbrowser
import urllib.parse
from typing import Callable, Optional

# Optional: pyautogui for typing/clicking (pip install pyautogui)
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
except ImportError:
    PYAUTOGUI_AVAILABLE = False

# Optional: pycaw for volume control (pip install pycaw)
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False


# ─── Known App Shortcuts ──────────────────────────────────────────────────────
APP_MAP = {
    "discord":      "discord",
    "chrome":       "chrome",
    "google chrome":"chrome",
    "firefox":      "firefox",
    "notepad":      "notepad",
    "calculator":   "calc",
    "calc":         "calc",
    "explorer":     "explorer",
    "word":         "winword",
    "excel":        "excel",
    "powerpoint":   "powerpnt",
    "vlc":          "vlc",
    "spotify":      "spotify",
    "vscode":       "code",
    "vs code":      "code",
    "terminal":     "cmd",
    "cmd":          "cmd",
    "powershell":   "powershell",
    "task manager": "taskmgr",
    "paint":        "mspaint",
}

# ─── Action Result ────────────────────────────────────────────────────────────
class ActionResult:
    def __init__(self, success: bool, message: str, action: str = ""):
        self.success = success
        self.message = message
        self.action  = action

    def to_dict(self):
        return {"success": self.success, "message": self.message, "action": self.action}


# ─── Core Action Functions ────────────────────────────────────────────────────

def open_url(url: str) -> ActionResult:
    """Open a URL in the default browser."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        webbrowser.open(url)
        return ActionResult(True, f"✅ Opened: {url}", "open_url")
    except Exception as e:
        return ActionResult(False, f"❌ Failed to open URL: {e}", "open_url")


def search_google(query: str) -> ActionResult:
    """Open Google search for a query."""
    encoded = urllib.parse.quote_plus(query)
    url = f"https://www.google.com/search?q={encoded}"
    return open_url(url)


def open_youtube(query: str = "") -> ActionResult:
    """Open YouTube, optionally with a search."""
    if query:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.youtube.com/results?search_query={encoded}"
    else:
        url = "https://www.youtube.com"
    return open_url(url)


def open_app(app_name: str) -> ActionResult:
    """Launch an application by name."""
    name_lower = app_name.lower().strip()
    exe = APP_MAP.get(name_lower, name_lower)
    try:
        subprocess.Popen(exe, shell=True)
        return ActionResult(True, f"✅ Launched: {app_name}", "open_app")
    except Exception as e:
        return ActionResult(False, f"❌ Failed to launch '{app_name}': {e}", "open_app")


def discord_send(message: str, delay: float = 1.5) -> ActionResult:
    """
    Send a message in the currently-active Discord channel.
    Discord must be open and focused on a text channel.
    Uses pyautogui to click the message field and type.
    """
    if not PYAUTOGUI_AVAILABLE:
        return ActionResult(False, "❌ pyautogui not installed. Run: pip install pyautogui", "discord_send")

    try:
        # Focus Discord window first
        _focus_window("discord")
        time.sleep(delay)

        # Click the message input area (bottom center of screen, where Discord's input usually is)
        sw, sh = pyautogui.size()
        pyautogui.click(sw // 2, sh - 60)
        time.sleep(0.3)

        # Use Ctrl+A to clear then type
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.typewrite(message, interval=0.03)
        time.sleep(0.2)
        pyautogui.press("enter")

        return ActionResult(True, f"✅ Discord message sent: \"{message}\"", "discord_send")
    except Exception as e:
        return ActionResult(False, f"❌ Discord send failed: {e}", "discord_send")


def type_text(text: str, delay: float = 0.5) -> ActionResult:
    """Type text using the keyboard after a short delay."""
    if not PYAUTOGUI_AVAILABLE:
        return ActionResult(False, "❌ pyautogui not installed. Run: pip install pyautogui", "type_text")
    try:
        time.sleep(delay)
        pyautogui.typewrite(text, interval=0.04)
        return ActionResult(True, f"✅ Typed: \"{text}\"", "type_text")
    except Exception as e:
        return ActionResult(False, f"❌ Type failed: {e}", "type_text")


def take_screenshot(save_path: str = "") -> ActionResult:
    """Take a screenshot and save it."""
    if not PYAUTOGUI_AVAILABLE:
        return ActionResult(False, "❌ pyautogui not installed. Run: pip install pyautogui", "screenshot")
    try:
        if not save_path:
            from datetime import datetime
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            save_path = os.path.join(desktop, f"screenshot_{ts}.png")
        img = pyautogui.screenshot()
        img.save(save_path)
        return ActionResult(True, f"✅ Screenshot saved: {save_path}", "screenshot")
    except Exception as e:
        return ActionResult(False, f"❌ Screenshot failed: {e}", "screenshot")


def set_volume(level: int) -> ActionResult:
    """Set system volume (0-100)."""
    if not PYCAW_AVAILABLE:
        # Fallback: use nircmd or powershell
        try:
            vol_scalar = max(0, min(100, level))
            # Use powershell as fallback
            ps_cmd = f"(New-Object -ComObject WScript.Shell).SendKeys([char]173)"
            # This is a rough fallback, nircmd would be better
            return ActionResult(False, "❌ pycaw not installed. Run: pip install pycaw comtypes", "volume")
        except Exception as e:
            return ActionResult(False, f"❌ Volume control failed: {e}", "volume")
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        scalar = max(0.0, min(1.0, level / 100.0))
        volume.SetMasterVolumeLevelScalar(scalar, None)
        return ActionResult(True, f"✅ Volume set to {level}%", "volume")
    except Exception as e:
        return ActionResult(False, f"❌ Volume control failed: {e}", "volume")


def press_key(key: str) -> ActionResult:
    """Press a keyboard key or hotkey combo like 'ctrl+c'."""
    if not PYAUTOGUI_AVAILABLE:
        return ActionResult(False, "❌ pyautogui not installed.", "press_key")
    try:
        if "+" in key:
            keys = [k.strip() for k in key.split("+")]
            pyautogui.hotkey(*keys)
        else:
            pyautogui.press(key)
        return ActionResult(True, f"✅ Key pressed: {key}", "press_key")
    except Exception as e:
        return ActionResult(False, f"❌ Key press failed: {e}", "press_key")


# ─── Window Focus Helper ──────────────────────────────────────────────────────

def _focus_window(app_name: str):
    """Try to bring a window to focus using Windows API."""
    try:
        import ctypes
        import ctypes.wintypes

        EnumWindows       = ctypes.windll.user32.EnumWindows
        GetWindowText     = ctypes.windll.user32.GetWindowTextW
        SetForegroundWin  = ctypes.windll.user32.SetForegroundWindow
        IsWindowVisible   = ctypes.windll.user32.IsWindowVisible
        ShowWindow        = ctypes.windll.user32.ShowWindow

        found = []
        name_lower = app_name.lower()

        def enum_callback(hwnd, lparam):
            if IsWindowVisible(hwnd):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    GetWindowText(hwnd, buf, length + 1)
                    if name_lower in buf.value.lower():
                        found.append(hwnd)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        EnumWindows(WNDENUMPROC(enum_callback), 0)

        if found:
            hwnd = found[0]
            ShowWindow(hwnd, 9)   # SW_RESTORE
            SetForegroundWin(hwnd)
        else:
            # Not open — launch it first
            open_app(app_name)
            time.sleep(2.0)
    except Exception:
        pass


# ─── Command Dispatcher ───────────────────────────────────────────────────────

def execute_command(command_type: str, params: dict) -> ActionResult:
    """Main dispatcher — routes command to the right function."""
    cmd = command_type.lower().strip()

    if cmd in ("open_url", "open"):
        return open_url(params.get("url", params.get("value", "")))

    elif cmd in ("search_google", "google", "search"):
        return search_google(params.get("query", params.get("value", "")))

    elif cmd in ("youtube",):
        return open_youtube(params.get("query", params.get("value", "")))

    elif cmd in ("open_app", "launch", "app"):
        return open_app(params.get("app", params.get("value", "")))

    elif cmd in ("discord_send", "discord"):
        return discord_send(
            params.get("message", params.get("value", "")),
            delay=float(params.get("delay", 1.5))
        )

    elif cmd in ("type", "type_text"):
        return type_text(params.get("text", params.get("value", "")))

    elif cmd in ("screenshot", "capture"):
        return take_screenshot(params.get("path", ""))

    elif cmd in ("volume", "set_volume"):
        return set_volume(int(params.get("level", params.get("value", 50))))

    elif cmd in ("key", "press_key", "hotkey"):
        return press_key(params.get("key", params.get("value", "")))

    elif cmd in ("open_discord",):
        res = open_app("discord")
        return res

    else:
        return ActionResult(False, f"❌ Unknown command: '{command_type}'", cmd)


# ─── AI Response Action Parser ────────────────────────────────────────────────

# Pattern: <<ACTION:type|param1=value1|param2=value2>>
ACTION_PATTERN = re.compile(r"<<ACTION:([a-zA-Z_]+)\|?([^>]*)>>")

def parse_and_execute_actions(ai_response: str, callback: Optional[Callable] = None) -> list[ActionResult]:
    """
    Scan an AI response for embedded action tags and execute them.

    AI should embed actions like:
        <<ACTION:open_url|url=https://google.com>>
        <<ACTION:search_google|query=python tutorials>>
        <<ACTION:discord_send|message=Hello there!>>
        <<ACTION:open_app|app=discord>>
        <<ACTION:screenshot>>
        <<ACTION:volume|level=50>>
        <<ACTION:key|key=ctrl+c>>

    Returns a list of ActionResult objects.
    """
    results = []
    matches = ACTION_PATTERN.findall(ai_response)

    for action_type, params_str in matches:
        params = {}
        if params_str:
            for part in params_str.split("|"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    params[k.strip()] = v.strip()
                else:
                    params["value"] = part.strip()

        def run_action(at=action_type, p=params):
            result = execute_command(at, p)
            if callback:
                callback(result)
            return result

        # Run actions in background thread to not block the UI
        t = threading.Thread(target=run_action, daemon=True)
        t.start()
        results.append(ActionResult(True, f"⚡ Executing: {action_type}", action_type))

    return results


def strip_action_tags(text: str) -> str:
    """Remove action tags from the AI's visible response text."""
    return ACTION_PATTERN.sub("", text).strip()
