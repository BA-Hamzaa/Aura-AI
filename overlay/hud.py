"""
hud.py — Premium AI Assistant HUD Overlay
Beautiful dark glass UI with animated accents and rich styling.
"""

import tkinter as tk
from tkinter import scrolledtext
import threading
import requests
import json
import websocket
import time
import os
import sys
import ctypes
import math

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

try:
    if SR_AVAILABLE:
        from wake_word import WakeWordDetector
        WAKE_WORD_AVAILABLE = True
    else:
        WAKE_WORD_AVAILABLE = False
except ImportError:
    WAKE_WORD_AVAILABLE = False

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u'AuraAI.HUD.1')
except Exception:
    pass

sys.stdout = open(os.devnull, "w")
sys.stderr = open(os.devnull, "w")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stealth import apply_stealth, remove_stealth, hide_from_taskbar, hide_from_taskbar_early, get_window_hwnd, get_screen_size

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

BACKEND = "http://localhost:8000"
WS_URL  = "ws://localhost:8000/ws"

BG_ROOT       = "#0b0e18"
BG_DARK       = "#0d1020"
BG_PANEL      = "#101528"
BG_CARD       = "#151a30"
BG_CARD2      = "#181e35"
BG_INPUT      = "#1c2240"
BG_INPUT_FOC  = "#222850"

ACCENT        = "#7c6fff"
ACCENT_LIGHT  = "#b8adff"
ACCENT_HOVER  = "#9d96ff"
ACCENT_DARK   = "#3d3880"
ACCENT_GLOW   = "#5548cc"

CYAN          = "#00e5c0"
CYAN_DARK     = "#00b89a"
PURPLE        = "#b06bff"
PINK          = "#ff6eb4"
ORANGE        = "#ffaa4d"
RED           = "#ff5f5f"
GREEN         = "#00e5c0"
YELLOW        = "#ffd166"

TEXT_PRIMARY  = "#ffffff"
TEXT_SEC      = "#b0b8d0"
TEXT_MUTED    = "#6a7094"
TEXT_ACCENT   = "#b8adff"

BORDER        = "#1e2545"
BORDER_GLOW   = "#303868"

FONT          = "Segoe UI"
FONT_BOLD     = "Segoe UI Semibold"
FONT_MONO     = "Cascadia Code"

TRANSLATIONS = {
    "en": {
        "subtitle":          "AI · Stealth · Always On",
        "tab_chat":          "💬  Chat",
        "tab_transcript":    "🎙  Transcript",
        "tab_actions":       "⚡  Actions",
        "ask_placeholder":   "Ask anything...",
        "input_hint":        "Enter to send · Shift+Enter for newline",
        "send_btn":          "Send  ↵",
        "api_warning":       "⚠️  No API key — click ⚙ to add your free OpenRouter key",
        "chip_battery":      "🔋  Battery",
        "chip_screenshot":   "📸  Screenshot",
        "chip_lock":         "🔒  Lock PC",
        "chip_summarize":    "📋  Summarize",
        "chip_spotify":      "🎵  Spotify",
        "chip_mute":         "🔇  Mute",
        "chip_prompts":      ["What is my battery status?", "Take a screenshot",
                              "Lock the screen", "Summarize the meeting so far",
                              "Open Spotify", "Mute the audio"],
        "start_listening":   "🎙  Start Listening",
        "stop_listening":    "⏹  Stop Listening",
        "clear_btn":         "🗑  Clear",
        "idle_lbl":          " IDLE",
        "live_lbl":          " LIVE",
        "connecting":        "Connecting...",
        "ai_ready":          "✅  AI ready",
        "ai_ready_tts":      "✅  Aura ready (TTS on)",
        "backend_connected": "✅  Backend connected",
        "hotkeys":           "Ctrl+Shift+Space: Hide  |  Alt+Space: Voice",
        "session_refreshed": "Session refreshed!",
        "session_refresh_s": "🔄  Session refreshed",
        "voice_on":          "Voice ON",
        "voice_off":         "Voice OFF",
        "stealth_active":    "🛡️  Stealth active",
        "listening":         "🎤  Listening... (speak now)",
        "no_speech":         "No speech detected",
        "not_understood":    "Couldn't understand — try again",
        "quota_warn":        "⚠️  Quota exhausted — key saved",
    },
    "fr": {
        "subtitle":          "IA · Discret · Toujours actif",
        "tab_chat":          "💬  Chat",
        "tab_transcript":    "🎙  Transcription",
        "tab_actions":       "⚡  Actions",
        "ask_placeholder":   "Posez une question...",
        "input_hint":        "Entrée pour envoyer · Maj+Entrée pour nouvelle ligne",
        "send_btn":          "Envoyer  ↵",
        "api_warning":       "⚠️  Pas de clé API - cliquez ⚙ pour ajouter votre clé OpenRouter gratuite",
        "chip_battery":      "🔋  Batterie",
        "chip_screenshot":   "📸  Capture",
        "chip_lock":         "🔒  Verrouiller",
        "chip_summarize":    "📋  Résumer",
        "chip_spotify":      "🎵  Spotify",
        "chip_mute":         "🔇  Muet",
        "chip_prompts":      ["Quel est mon niveau de batterie ?", "Prendre une capture d'écran",
                              "Verrouiller l'écran", "Résumer la réunion jusqu'ici",
                              "Ouvrir Spotify", "Couper le son"],
        "start_listening":   "🎙  Démarrer l'écoute",
        "stop_listening":    "⏹  Arrêter l'écoute",
        "clear_btn":         "🗑  Effacer",
        "idle_lbl":          " INACTIF",
        "live_lbl":          " EN DIRECT",
        "connecting":        "Connexion...",
        "ai_ready":          "✅  IA prête",
        "ai_ready_tts":      "✅  Aura prête (voix activée)",
        "backend_connected": "✅  Serveur connecté",
        "hotkeys":           "Ctrl+Maj+Espace : Masquer  |  Alt+Espace : Voix",
        "session_refreshed": "Session réinitialisée !",
        "session_refresh_s": "🔄  Session réinitialisée",
        "voice_on":          "Voix activée",
        "voice_off":         "Voix désactivée",
        "stealth_active":    "🛡️  Mode discret actif",
        "listening":         "🎤  Écoute en cours...",
        "no_speech":         "Aucune parole détectée",
        "not_understood":    "Impossible de comprendre — réessayez",
        "quota_warn":        "⚠️  Quota épuisé — clé sauvegardée",
    },
    "ar": {
        "subtitle":          "ذكاء اصطناعي · خفي · دائماً نشط",
        "tab_chat":          "💬  محادثة",
        "tab_transcript":    "🎙  النص",
        "tab_actions":       "⚡  إجراءات",
        "ask_placeholder":   "اسأل أي شيء...",
        "input_hint":        "Enter للإرسال · Shift+Enter لسطر جديد",
        "send_btn":          "إرسال  ↵",
        "api_warning":       "⚠️  لا يوجد مفتاح API - انقر ⚙ لإضافة مفتاح OpenRouter المجاني",
        "chip_battery":      "🔋  بطارية",
        "chip_screenshot":   "📸  لقطة شاشة",
        "chip_lock":         "🔒  قفل الشاشة",
        "chip_summarize":    "📋  تلخيص",
        "chip_spotify":      "🎵  سبوتيفاي",
        "chip_mute":         "🔇  كتم الصوت",
        "chip_prompts":      ["ما مستوى البطارية؟", "التقط لقطة شاشة",
                              "قفل الشاشة", "لخص الاجتماع حتى الآن",
                              "افتح سبوتيفاي", "كتم الصوت"],
        "start_listening":   "🎙  بدء الاستماع",
        "stop_listening":    "⏹  إيقاف الاستماع",
        "clear_btn":         "🗑  مسح",
        "idle_lbl":          " خامل",
        "live_lbl":          " مباشر",
        "connecting":        "جارٍ الاتصال...",
        "ai_ready":          "✅  الذكاء الاصطناعي جاهز",
        "ai_ready_tts":      "✅  أورا جاهزة (الصوت مفعّل)",
        "backend_connected": "✅  متصل بالخادم",
        "hotkeys":           "Ctrl+Shift+Space: إخفاء  |  Alt+Space: صوت",
        "session_refreshed": "تمت إعادة تعيين الجلسة!",
        "session_refresh_s": "🔄  إعادة تعيين الجلسة",
        "voice_on":          "الصوت مفعّل",
        "voice_off":         "الصوت معطّل",
        "stealth_active":    "🛡️  الوضع الخفي نشط",
        "listening":         "🎤  جارٍ الاستماع...",
        "no_speech":         "لم يتم اكتشاف كلام",
        "not_understood":    "لم أفهم — حاول مجدداً",
        "quota_warn":        "⚠️  الحصة منتهية — تم حفظ المفتاح",
    },
}

def api_post(endpoint, payload=None, timeout=60):
    try:
        r = requests.post(f"{BACKEND}/{endpoint}", json=payload or {}, timeout=timeout)
        if not r.content:
            return {"error": "Empty response from server"}
        try:
            return r.json()
        except Exception:
            return {"detail": r.text or "Server error", "error": r.text or "Server error"}
    except requests.exceptions.ReadTimeout:
        return {"error": "⚠️ Connection timed out — Aura is taking too long to think. Please try again."}
    except requests.exceptions.ConnectionError:
        return {"error": "⚠️ Backend not reachable — is the server running?"}
    except Exception as e:
        return {"error": str(e)}

def api_get(endpoint, timeout=10):
    try:
        r = requests.get(f"{BACKEND}/{endpoint}", timeout=timeout)
        return r.json()
    except requests.exceptions.ReadTimeout:
        return {"error": "Request timed out"}
    except Exception as e:
        return {"error": str(e)}

def rounded_rect(canvas, x1, y1, x2, y2, r=12, **kwargs):
    points = [
        x1+r, y1,  x2-r, y1,
        x2, y1,    x2, y1+r,
        x2, y2-r,  x2, y2,
        x2-r, y2,  x1+r, y2,
        x1, y2,    x1, y2-r,
        x1, y1+r,  x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)

class AIAssistantHUD:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Aura AI")
        self.root.configure(bg=BG_ROOT)
        sw, sh = get_screen_size()
        w, h = 750, 580
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.withdraw()
        self.root.overrideredirect(False)
        self.root.attributes("-topmost", False)
        self.root.attributes("-alpha", 0.97)
        self.root.resizable(True, True)
        self.root.minsize(380, 540)

        self.transcription_active = False
        self.api_key_configured = False
        self._drag_x = self._drag_y = 0
        self._pulse_phase = 0
        self._pulse_running = False
        self._icon_small = None
        self._tk_icon = None
        self._status_icon = None
        self._mic_listening = False
        self._mic_stop_event = threading.Event()  # for immediately stopping mic
        self._mic_btn = None
        self._voice_mode = False
        self._tts_enabled = True
        self._wave_phase = 0
        self._wave_running = False
        self._wave_bars = []
        self._wake_word_enabled = False
        self._stealth_on = True   # track whether screen-share exclusion is active
        self._wake_detector = None
        
        # dynamic translations
        self._current_language = "en"
        self._lang_btn = None
        self._w = {}
        self._chip_widgets = []


        self._load_icon()
        self._build_ui()
        self._check_backend()
        self._connect_websocket()
        self._start_pulse()

        self.root.bind("<Control-Shift-space>", self._toggle_visibility)
        self.root.bind("<Alt-space>", lambda e: self._start_voice_input())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── Phase 1: hide from taskbar BEFORE the window is ever shown ──────
        # update_idletasks() forces tkinter to allocate the real Win32 HWND
        # while the window is still withdrawn, so GetAncestor can walk up to
        # the top-level handle and strip WS_EX_APPWINDOW immediately.
        self.root.update_idletasks()
        hide_from_taskbar_early(self.root.winfo_id())

        # ── Phase 2: show the window (taskbar button already suppressed) ─────
        self.root.deiconify()
        self.root.update_idletasks()

        # ── Phase 3: apply capture-exclusion once FindWindowW can locate it ──
        self.root.after(500, self._apply_stealth)

        self._apply_translations()

    def _tr(self, key: str) -> str:
        lang = TRANSLATIONS.get(self._current_language, TRANSLATIONS["en"])
        return lang.get(key, TRANSLATIONS["en"].get(key, key))

    def _set_language(self, code: str):
        if code == self._current_language:
            return
        self._current_language = code
        names = {"en": "English", "fr": "Français", "ar": "عربي"}
        if hasattr(self, "_lang_btn"):
            self._lang_btn.configure(text=f"{names.get(code, code)} ▾")
            
        def update():
            try:
                requests.post(f"{BACKEND}/api/language", json={"language": code}, timeout=5)
            except Exception:
                pass
        threading.Thread(target=update, daemon=True).start()
        self._apply_translations()
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.configure(state=tk.DISABLED)
        
        self._toast(f"🌐  {names.get(code, code)}", YELLOW)
        self._set_status(f"🌐  {names.get(code, code)}", YELLOW)

    def _cycle_language(self, event=None):
        order = ["en", "fr", "ar"]
        try:
            nxt = order[(order.index(self._current_language) + 1) % len(order)]
        except ValueError:
            nxt = "en"
        self._set_language(nxt)

    def _apply_translations(self):
        simple_keys = ["subtitle", "api_warning", "input_hint", "send_btn", "clear_btn"]
        for key in simple_keys:
            w = self._w.get(key)
            if w:
                try: w.configure(text=self._tr(key))
                except: pass

        current_text = self.chat_input.get("1.0", tk.END).strip()
        old_placeholders = [TRANSLATIONS[lang]["ask_placeholder"] for lang in TRANSLATIONS]
        if current_text in old_placeholders or not current_text:
            self.chat_input.delete("1.0", tk.END)
            self.chat_input.insert("1.0", self._tr("ask_placeholder"))
            self.chat_input.configure(fg=TEXT_MUTED)

        if not self.transcription_active:
            w = self._w.get("start_listening")
            if w:
                try: w.configure(text=self._tr("start_listening"))
                except: pass

        for chip_widget, chip_key in self._chip_widgets:
            try: chip_widget.configure(text=self._tr(chip_key))
            except: pass

        tab_map = {"chat": "tab_chat", "transcript": "tab_transcript", "actions": "tab_actions"}
        for tab_key, tr_key in tab_map.items():
            btn = self.tab_buttons.get(tab_key)
            if btn:
                try: btn.configure(text=self._tr(tr_key))
                except: pass

        if not self.transcription_active:
            self.live_label.configure(text=self._tr("idle_lbl"))

    def _load_icon(self):
        base = os.path.dirname(os.path.abspath(__file__))
        ico_path = os.path.join(base, "brain_icon.ico")
        png_path = os.path.join(base, "brain_icon.png")
        if not os.path.exists(png_path) or not PIL_AVAILABLE:
            return
        try:
            img = Image.open(png_path).convert("RGBA")
            if os.path.exists(ico_path):
                self.root.iconbitmap(default=ico_path)
                hwnd = self.root.winfo_id()
                if hwnd:
                    WM_SETICON = 0x0080
                    hicon = ctypes.windll.shell32.ExtractIconW(0, ico_path, 0)
                    if hicon:
                        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 1, hicon)
                        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 0, hicon)
            ico32 = img.resize((32, 32), Image.LANCZOS)
            self._tk_icon = ImageTk.PhotoImage(ico32)
            self.root.iconphoto(True, self._tk_icon)
            self._icon_small = ImageTk.PhotoImage(img.resize((34, 34), Image.LANCZOS))
            self._status_icon = ImageTk.PhotoImage(img.resize((14, 14), Image.LANCZOS))
        except Exception:
            pass

    def _start_pulse(self):
        self._pulse_running = True
        self._animate_pulse()

    def _animate_pulse(self):
        if not self._pulse_running: return
        self._pulse_phase = (self._pulse_phase + 0.08) % (2 * math.pi)
        alpha = int(160 + 95 * math.sin(self._pulse_phase))
        color = f"#{alpha:02x}e5c0" if self.transcription_active else f"#{alpha//3:02x}{alpha//3:02x}{alpha//2:02x}"
        try: self.pulse_dot.configure(fg=color)
        except: pass
        self.root.after(50, self._animate_pulse)

    def _build_ui(self):
        self.main = tk.Frame(self.root, bg=BG_ROOT)
        self.main.pack(fill=tk.BOTH, expand=True)
        self._build_header()
        self._build_tab_bar()
        self._build_content()
        self._build_status_bar()

    def _build_header(self):
        for color, h in [(ACCENT_DARK, 1), (ACCENT, 2), (ACCENT_LIGHT, 1)]:
            tk.Frame(self.main, bg=color, height=h).pack(fill=tk.X)
        hdr = tk.Frame(self.main, bg=BG_PANEL, pady=14)
        hdr.pack(fill=tk.X)
        hdr.bind("<Button-1>", self._start_drag)
        hdr.bind("<B1-Motion>", self._do_drag)
        left = tk.Frame(hdr, bg=BG_PANEL)
        left.pack(side=tk.LEFT, padx=16)
        left.bind("<Button-1>", self._start_drag)
        left.bind("<B1-Motion>", self._do_drag)
        if self._icon_small:
            icon_canvas = tk.Canvas(left, width=44, height=44, bg=BG_PANEL, highlightthickness=0)
            icon_canvas.pack(side=tk.LEFT, padx=(0, 12))
            icon_canvas.create_oval(2, 2, 42, 42, outline=ACCENT_DARK, width=1)
            icon_canvas.create_image(22, 22, image=self._icon_small)
            icon_canvas.bind("<Button-1>", self._start_drag)
            icon_canvas.bind("<B1-Motion>", self._do_drag)
        else:
            tk.Label(left, text="🧠", bg=BG_PANEL, font=(FONT, 22)).pack(side=tk.LEFT, padx=(0, 12))
        
        title_col = tk.Frame(left, bg=BG_PANEL)
        title_col.pack(side=tk.LEFT)
        title_col.bind("<Button-1>", self._start_drag)
        title_col.bind("<B1-Motion>", self._do_drag)
        tk.Label(title_col, text="Aura AI", fg=TEXT_PRIMARY, bg=BG_PANEL,
                 font=(FONT_BOLD, 16, "bold")).pack(anchor=tk.W)
        
        sub_row = tk.Frame(title_col, bg=BG_PANEL)
        sub_row.pack(anchor=tk.W)
        self.pulse_dot = tk.Label(sub_row, text="●", fg=TEXT_MUTED, bg=BG_PANEL, font=(FONT, 9))
        self.pulse_dot.pack(side=tk.LEFT)
        _subtitle = tk.Label(sub_row, text="  AI · Stealth · Always On", fg=TEXT_SEC, bg=BG_PANEL, font=(FONT, 9))
        _subtitle.pack(side=tk.LEFT)
        self._w["subtitle"] = _subtitle

        right = tk.Frame(hdr, bg=BG_PANEL)
        right.pack(side=tk.RIGHT, padx=12)
        pill = tk.Frame(right, bg="#0a2018", padx=10, pady=4)
        pill.pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(pill, text="🛡  STEALTH", fg=CYAN, bg="#0a2018", font=(FONT, 8, "bold")).pack()
        self._voice_mode_btn = self._make_ctrl_btn(right, "🎤", self._activate_siri_mode, ACCENT_LIGHT)
        self._voice_mode_btn.pack(side=tk.LEFT, padx=2)

        # Custom Dropdown language selector
        names = {"en": "English", "fr": "Français", "ar": "عربي"}
        self._lang_btn = tk.Button(right, text=f"{names.get(self._current_language, 'English')} ▾", 
                                   bg=BG_PANEL, fg=TEXT_PRIMARY, font=(FONT, 9, "bold"),
                                   relief=tk.FLAT, bd=0, padx=8, pady=3, cursor="hand2", activebackground=BG_CARD)
        self._lang_btn.pack(side=tk.LEFT, padx=4)
        
        def _show_custom_dropdown(event):
            if hasattr(self, "_lang_drop") and self._lang_drop.winfo_exists():
                self._lang_drop.destroy()
                return

            # Compute relative position inside the root window
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()
            x = self._lang_btn.winfo_rootx() - rx
            y = self._lang_btn.winfo_rooty() - ry + self._lang_btn.winfo_height() + 2

            drop = tk.Frame(self.root, bg=BORDER)
            drop.place(x=x, y=y, width=120)
            self._lang_drop = drop
            
            f = tk.Frame(drop, bg=BG_DARK, padx=2, pady=2)
            f.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
            
            def _select(code, w=drop):
                self._set_language(code)
                w.destroy()
                
            for code, label in [("en", "English"), ("fr", "Français"), ("ar", "عربي")]:
                fg = YELLOW if code == self._current_language else TEXT_PRIMARY
                b = tk.Button(f, text=label, bg=BG_DARK, fg=fg, font=(FONT, 9),
                              relief=tk.FLAT, bd=0, anchor="w", padx=12, pady=6, cursor="hand2",
                              activebackground=BG_CARD, activeforeground="white")
                b.pack(fill=tk.X)
                b.bind("<Button-1>", lambda e, c=code: _select(c))
                b.bind("<Enter>", lambda e, w=b: w.configure(bg=BG_CARD))
                b.bind("<Leave>", lambda e, w=b: w.configure(bg=BG_DARK))
                
            # Close it if user clicks anywhere outside the drop frame
            def _close_if_outside(e):
                if not drop.winfo_exists(): return
                dx, dy, dw, dh = drop.winfo_rootx(), drop.winfo_rooty(), drop.winfo_width(), drop.winfo_height()
                if not (dx <= e.x_root <= dx + dw and dy <= e.y_root <= dy + dh):
                    # Only destroy if they didn't just click the toggle button itself
                    bx, by, bw, bh = self._lang_btn.winfo_rootx(), self._lang_btn.winfo_rooty(), self._lang_btn.winfo_width(), self._lang_btn.winfo_height()
                    if not (bx <= e.x_root <= bx + bw and by <= e.y_root <= by + bh):
                        drop.destroy()
            
            # Bind the click to the main root window
            self.root.bind("<Button-1>", _close_if_outside, add="+")
            
        self._lang_btn.bind("<Button-1>", _show_custom_dropdown)
        self._lang_btn.bind("<Enter>", lambda e: self._lang_btn.configure(bg=BG_CARD))
        self._lang_btn.bind("<Leave>", lambda e: self._lang_btn.configure(bg=BG_PANEL))

        self._make_ctrl_btn(right, "⚙", self._open_settings, TEXT_SEC).pack(side=tk.LEFT, padx=(6, 2))

        self._make_ctrl_btn(right, "↺", self._action_refresh, ORANGE).pack(side=tk.LEFT, padx=2)
        self._make_ctrl_btn(right, "✕", self._on_close, RED).pack(side=tk.LEFT, padx=2)
        tk.Frame(self.main, bg=BORDER, height=1).pack(fill=tk.X)
    def _build_tab_bar(self):
        self.tab_bar = tk.Frame(self.main, bg=BG_PANEL, height=46)
        self.tab_bar.pack(fill=tk.X)
        self.tab_bar.pack_propagate(False)
        self.active_tab = tk.StringVar(value="chat")
        self.tab_buttons = {}
        self.tab_frames = {}
        self._tab_indicators = {}
        tabs = [("💬  Chat", "chat"), ("🎙  Transcript", "transcript"), ("⚡  Actions", "actions")]
        tab_inner = tk.Frame(self.tab_bar, bg=BG_PANEL)
        tab_inner.pack(side=tk.LEFT, fill=tk.Y, padx=8)
        for label, key in tabs:
            col = tk.Frame(tab_inner, bg=BG_PANEL)
            col.pack(side=tk.LEFT, padx=3, pady=6)
            btn = tk.Button(col, text=label,
                bg=ACCENT if key == "chat" else BG_PANEL,
                fg=TEXT_PRIMARY if key == "chat" else TEXT_SEC,
                font=(FONT, 10, "bold"), relief=tk.FLAT, bd=0, padx=14, pady=6, cursor="hand2",
                command=lambda k=key: self._switch_tab(k))
            btn.pack()
            indicator = tk.Frame(col, bg=ACCENT if key == "chat" else BG_PANEL, height=2)
            indicator.pack(fill=tk.X, padx=4)
            self.tab_buttons[key] = btn
            self._tab_indicators[key] = indicator
            if key != "chat": self._hover(btn, BG_CARD, BG_PANEL, TEXT_PRIMARY, TEXT_SEC)
        tk.Frame(self.main, bg=BORDER, height=1).pack(fill=tk.X)

    def _switch_tab(self, key):
        self.active_tab.set(key)
        for k, frame in self.tab_frames.items():
            if k == key:
                frame.pack(fill=tk.BOTH, expand=True)
                self.tab_buttons[k].configure(bg=ACCENT, fg=TEXT_PRIMARY)
                self._tab_indicators[k].configure(bg=ACCENT)
            else:
                frame.pack_forget()
                self.tab_buttons[k].configure(bg=BG_PANEL, fg=TEXT_SEC)
                self._tab_indicators[k].configure(bg=BG_PANEL)

    def _build_content(self):
        self.content = tk.Frame(self.main, bg=BG_DARK)
        self.content.pack(fill=tk.BOTH, expand=True)
        self._build_chat_tab()
        self._build_transcript_tab()
        self._build_actions_tab()
        self._switch_tab("chat")

    def _build_chat_tab(self):
        frame = tk.Frame(self.content, bg=BG_DARK)
        self.tab_frames["chat"] = frame

        self.api_warning = tk.Frame(frame, bg="#1a1000", pady=6, padx=12)
        self.api_warning.pack(fill=tk.X, padx=12, pady=(10, 0))
        _warn_lbl = tk.Label(self.api_warning, text="⚠️  No API key — click ⚙ to add your free OpenRouter key", fg=ORANGE, bg="#1a1000", font=(FONT, 10))
        _warn_lbl.pack()
        self._w["api_warning"] = _warn_lbl

        input_panel = tk.Frame(frame, bg=BG_CARD, pady=10, padx=12)
        input_panel.pack(fill=tk.X, side=tk.BOTTOM, padx=12, pady=(0, 6))

        input_border = tk.Frame(input_panel, bg=BORDER_GLOW, padx=1, pady=1)
        input_border.pack(fill=tk.X)
        self.chat_input = tk.Text(input_border, bg=BG_INPUT, fg=TEXT_PRIMARY, font=(FONT, 11),
            relief=tk.FLAT, bd=0, height=2, wrap=tk.WORD, insertbackground=ACCENT_LIGHT, padx=12, pady=8)
        self.chat_input.pack(fill=tk.X)
        self.chat_input.insert("1.0", "Ask anything...")
        self.chat_input.configure(fg=TEXT_MUTED)
        self.chat_input.bind("<FocusIn>", self._inp_focus_in)
        self.chat_input.bind("<FocusOut>", self._inp_focus_out)
        self.chat_input.bind("<Return>", self._on_enter)
        self.chat_input.bind("<Shift-Return>", lambda e: None)
        self._input_border = input_border

        btn_row = tk.Frame(input_panel, bg=BG_CARD)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        _hint = tk.Label(btn_row, text="Enter to send · Shift+Enter for newline", fg=TEXT_MUTED, bg=BG_CARD, font=(FONT, 8))
        _hint.pack(side=tk.LEFT)
        self._w["input_hint"] = _hint

        _send = tk.Button(btn_row, text="Send  ↵", bg=ACCENT, fg="white", font=(FONT_BOLD, 9, "bold"),
            relief=tk.FLAT, bd=0, padx=18, pady=7, cursor="hand2", activebackground=ACCENT_HOVER, activeforeground="white", command=self._send_chat)
        _send.pack(side=tk.RIGHT, padx=(4, 0))
        self._hover(_send, ACCENT_HOVER, ACCENT)
        self._w["send_btn"] = _send

        mic_color = CYAN if SR_AVAILABLE else TEXT_MUTED
        self._mic_btn = tk.Button(btn_row, text="🎤", bg=BG_CARD2, fg=mic_color, font=(FONT, 12),
            relief=tk.FLAT, bd=0, padx=10, pady=4, cursor="hand2" if SR_AVAILABLE else "arrow",
            activebackground=BG_INPUT, activeforeground=CYAN, command=self._start_voice_input if SR_AVAILABLE else lambda: None)
        self._mic_btn.pack(side=tk.RIGHT, padx=(0, 4))
        if SR_AVAILABLE: self._hover(self._mic_btn, BG_INPUT, BG_CARD2, CYAN, mic_color)

        chips_frame = tk.Frame(frame, bg=BG_DARK)
        chips_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=12, pady=(0, 4))
        self._chips_frame = chips_frame
        
        chip_labels = ["chip_battery", "chip_screenshot", "chip_lock", "chip_summarize", "chip_spotify", "chip_mute"]
        for i, ck in enumerate(chip_labels):
            chip = tk.Button(chips_frame, text=self._tr(ck), bg=BG_CARD2, fg=TEXT_SEC, font=(FONT, 9),
                relief=tk.FLAT, bd=0, padx=10, pady=5, cursor="hand2",
                command=lambda idx=i: self._quick_ask(TRANSLATIONS[self._current_language]["chip_prompts"][idx]))
            chip.pack(side=tk.LEFT, padx=2)
            self._hover(chip, BG_INPUT, BG_CARD2, TEXT_ACCENT, TEXT_SEC)
            self._chip_widgets.append((chip, ck))

        chat_outer = tk.Frame(frame, bg=BORDER, bd=0)
        chat_outer.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)
        self.chat_display = tk.Text(chat_outer, bg=BG_CARD, fg=TEXT_PRIMARY, font=(FONT, 11),
            relief=tk.FLAT, bd=0, wrap=tk.WORD, state=tk.DISABLED, insertbackground=ACCENT,
            selectbackground=ACCENT_DARK, selectforeground=TEXT_PRIMARY, padx=14, pady=12, spacing1=3, spacing2=2, spacing3=5)
        scroll = tk.Scrollbar(chat_outer, command=self.chat_display.yview, bg=BG_CARD, troughcolor=BG_CARD2, activebackground=ACCENT_DARK, width=6, relief=tk.FLAT, bd=0)
        self.chat_display.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.chat_display.tag_configure("user_label", foreground=ACCENT_LIGHT, font=(FONT_BOLD, 10, "bold"))
        self.chat_display.tag_configure("user_msg", foreground=TEXT_PRIMARY, font=(FONT, 11), lmargin1=12, lmargin2=12)
        self.chat_display.tag_configure("ai_label", foreground=CYAN, font=(FONT_BOLD, 10, "bold"))
        self.chat_display.tag_configure("ai_msg", foreground="#e8ecff", font=(FONT, 11), lmargin1=12, lmargin2=12)
        self.chat_display.tag_configure("thinking", foreground=TEXT_SEC, font=(FONT, 10, "italic"), lmargin1=12)
        self.chat_display.tag_configure("divider", foreground=BORDER_GLOW, font=(FONT, 7))

    def _inp_focus_in(self, event):
        self._input_border.configure(bg=ACCENT_DARK)
        if self.chat_input.get("1.0", tk.END).strip() in [TRANSLATIONS[l]["ask_placeholder"] for l in TRANSLATIONS]:
            self.chat_input.delete("1.0", tk.END)
            self.chat_input.configure(fg=TEXT_PRIMARY)

    def _inp_focus_out(self, event):
        self._input_border.configure(bg=BORDER_GLOW)
        if not self.chat_input.get("1.0", tk.END).strip():
            self.chat_input.insert("1.0", self._tr("ask_placeholder"))
            self.chat_input.configure(fg=TEXT_MUTED)

    def _build_transcript_tab(self):
        frame = tk.Frame(self.content, bg=BG_DARK)
        self.tab_frames["transcript"] = frame
        ctrl = tk.Frame(frame, bg=BG_DARK)
        ctrl.pack(fill=tk.X, padx=12, pady=12)

        self.mic_btn = tk.Button(ctrl, text="🎙  Start Listening", bg=CYAN, fg=BG_ROOT, font=(FONT_BOLD, 9, "bold"),
            relief=tk.FLAT, bd=0, padx=16, pady=8, cursor="hand2", command=self._toggle_transcription)
        self.mic_btn.pack(side=tk.LEFT)
        self._w["start_listening"] = self.mic_btn

        _clear = tk.Button(ctrl, text="🗑  Clear", bg=BG_CARD2, fg=TEXT_SEC, font=(FONT, 9), relief=tk.FLAT, bd=0,
            padx=12, pady=8, cursor="hand2", command=self._clear_transcript)
        _clear.pack(side=tk.LEFT, padx=8)
        self._hover(_clear, BG_INPUT, BG_CARD2)
        self._w["clear_btn"] = _clear

        live_frame = tk.Frame(ctrl, bg=BG_DARK)
        live_frame.pack(side=tk.RIGHT)
        self.live_dot = tk.Label(live_frame, text="●", fg=TEXT_MUTED, bg=BG_DARK, font=(FONT, 10))
        self.live_dot.pack(side=tk.LEFT)
        self.live_label = tk.Label(live_frame, text=" IDLE", fg=TEXT_MUTED, bg=BG_DARK, font=(FONT, 8, "bold"))
        self.live_label.pack(side=tk.LEFT)

        t_outer = tk.Frame(frame, bg=BORDER)
        t_outer.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.transcript_display = tk.Text(t_outer, bg=BG_CARD, fg=TEXT_PRIMARY, font=(FONT_MONO, 11),
            relief=tk.FLAT, bd=0, wrap=tk.WORD, state=tk.DISABLED, padx=12, pady=12, spacing1=3, spacing2=2, spacing3=5)
        ts_scroll = tk.Scrollbar(t_outer, command=self.transcript_display.yview, bg=BG_CARD, troughcolor=BG_CARD2, width=6, relief=tk.FLAT, bd=0)
        self.transcript_display.configure(yscrollcommand=ts_scroll.set)
        ts_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.transcript_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.transcript_display.tag_configure("ts", foreground=TEXT_SEC, font=(FONT_MONO, 9))
        self.transcript_display.tag_configure("line", foreground=TEXT_PRIMARY, font=(FONT_MONO, 11))

    def _build_actions_tab(self):
        frame = tk.Frame(self.content, bg=BG_DARK)
        self.tab_frames["actions"] = frame
        canvas = tk.Canvas(frame, bg=BG_DARK, highlightthickness=0)
        sb = tk.Scrollbar(frame, orient="vertical", command=canvas.yview, bg=BG_DARK, troughcolor=BG_CARD, width=6, relief=tk.FLAT, bd=0)
        sf = tk.Frame(canvas, bg=BG_DARK)
        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        def _sec(title, icon=""):
            row = tk.Frame(sf, bg=BG_DARK)
            row.pack(fill=tk.X, padx=12, pady=(16, 0))
            tk.Label(row, text=f"{icon}  {title}", fg=ACCENT_LIGHT, bg=BG_DARK, font=(FONT_BOLD, 11, "bold")).pack(side=tk.LEFT)
            tk.Frame(sf, bg=BORDER_GLOW, height=1).pack(fill=tk.X, padx=12, pady=(4, 8))

        def _card():
            c = tk.Frame(sf, bg=BG_CARD, padx=10, pady=8)
            c.pack(fill=tk.X, padx=12, pady=(0, 4))
            return c

        _sec("Open URL", "🌐")
        c = _card()
        self.url_entry = tk.Entry(c, bg=BG_INPUT, fg=TEXT_PRIMARY, font=(FONT, 10), relief=tk.FLAT, bd=0, insertbackground=TEXT_PRIMARY)
        self.url_entry.insert(0, "https://")
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 8))
        self._pill_btn(c, "Open", ACCENT, self._cmd_open_url).pack(side=tk.RIGHT)

        _sec("Google Search", "🔍")
        c = _card()
        self.google_entry = tk.Entry(c, bg=BG_INPUT, fg=TEXT_PRIMARY, font=(FONT, 10), relief=tk.FLAT, bd=0, insertbackground=TEXT_PRIMARY)
        self.google_entry.insert(0, "Search...")
        self.google_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 8))
        self._pill_btn(c, "Search", "#34a853", self._cmd_google_search).pack(side=tk.RIGHT)

        _sec("Discord Message", "💬")
        tk.Label(sf, text="  Discord must be open on a text channel", fg=TEXT_SEC, bg=BG_DARK, font=(FONT, 8)).pack(padx=12, anchor=tk.W, pady=(0, 4))
        self.discord_entry = tk.Text(sf, bg=BG_INPUT, fg=TEXT_PRIMARY, font=(FONT, 10), relief=tk.FLAT, bd=0, height=2, wrap=tk.WORD, insertbackground=TEXT_PRIMARY, padx=10, pady=8)
        self.discord_entry.pack(fill=tk.X, padx=12, pady=(0, 6))
        dr = tk.Frame(sf, bg=BG_DARK)
        dr.pack(fill=tk.X, padx=12, pady=(0, 4))
        self._pill_btn(dr, "📨  Send", "#5865F2", self._cmd_discord_send).pack(side=tk.LEFT)
        self._pill_btn(dr, "Open Discord", BG_CARD, lambda: self._run_command("open_app", {"app": "discord"}), fg_color="#5865F2").pack(side=tk.LEFT, padx=6)

        _sec("Launch Apps", "🚀")
        grid = tk.Frame(sf, bg=BG_DARK)
        grid.pack(fill=tk.X, padx=12)
        apps = [("🌐 Chrome", "chrome", "#EA4335"), ("🎵 Spotify", "spotify", "#1DB954"), ("💻 VS Code", "code", ACCENT),
                ("📝 Notepad", "notepad", ORANGE), ("🧮 Calc", "calc", CYAN), ("🗂 Explorer", "explorer", TEXT_SEC),
                ("💬 Discord", "discord", "#5865F2"), ("🎬 VLC", "vlc", "#FF8800")]
        for i, (label, app, color) in enumerate(apps):
            btn = tk.Button(grid, text=label, bg=BG_CARD2, fg=color, font=(FONT, 9, "bold"), relief=tk.FLAT, bd=0, padx=6, pady=10, cursor="hand2", command=lambda a=app: self._run_command("open_app", {"app": a}))
            btn.grid(row=i//2, column=i%2, padx=3, pady=3, sticky="ew")
            self._hover(btn, BG_INPUT, BG_CARD2)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        _sec("System", "🖥️")
        sc = tk.Frame(sf, bg=BG_DARK)
        sc.pack(fill=tk.X, padx=12)
        self._pill_btn(sc, "📸  Screenshot", CYAN_DARK, lambda: self._run_command("screenshot", {}), fg_color=BG_ROOT).pack(side=tk.LEFT)
        vf = tk.Frame(sf, bg=BG_DARK)
        vf.pack(fill=tk.X, padx=12, pady=(8, 4))
        tk.Label(vf, text="🔊", fg=TEXT_SEC, bg=BG_DARK, font=(FONT, 10)).pack(side=tk.LEFT)
        self.vol_slider = tk.Scale(vf, from_=0, to=100, orient=tk.HORIZONTAL, bg=BG_DARK, fg=TEXT_PRIMARY, highlightthickness=0, troughcolor=BG_INPUT, activebackground=ACCENT, sliderrelief=tk.FLAT, length=160, showvalue=True, font=(FONT, 7))
        self.vol_slider.set(50)
        self.vol_slider.pack(side=tk.LEFT, padx=8)
        self._pill_btn(vf, "Set", ACCENT, lambda: self._run_command("volume", {"level": self.vol_slider.get()})).pack(side=tk.LEFT)
        _sec("Meeting", "📋")
        for label, color, cmd in [("📋  Summarize Meeting", ACCENT, self._action_summarize), ("✅  Extract Action Items", CYAN, self._action_items), ("🔄  Reset Session", ORANGE, self._action_reset)]:
            btn = tk.Button(sf, text=label, bg=BG_CARD2, fg=color, font=(FONT, 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=11, anchor=tk.W, cursor="hand2", command=cmd)
            btn.pack(fill=tk.X, padx=12, pady=2)
            self._hover(btn, BG_INPUT, BG_CARD2)
        _sec("Rephrase Tool", "✍️")
        self.rephrase_input = tk.Text(sf, bg=BG_INPUT, fg=TEXT_PRIMARY, font=(FONT, 10), relief=tk.FLAT, bd=0, height=3, wrap=tk.WORD, insertbackground=TEXT_PRIMARY, padx=10, pady=8)
        self.rephrase_input.pack(fill=tk.X, padx=12, pady=(0, 6))
        self._pill_btn(sf, "✨  Rephrase Professionally", PINK, self._action_rephrase, fg_color=BG_ROOT, padx=14, pady=8).pack(padx=12, anchor=tk.W, pady=(0, 6))
        result_outer = tk.Frame(sf, bg=BORDER)
        result_outer.pack(fill=tk.X, padx=12, pady=(0, 16))
        self.actions_result = tk.Text(result_outer, bg=BG_CARD, fg=TEXT_PRIMARY, font=(FONT, 10), relief=tk.FLAT, bd=0, height=5, wrap=tk.WORD, state=tk.DISABLED, padx=12, pady=10)
        self.actions_result.pack(fill=tk.X)

    def _build_status_bar(self):
        tk.Frame(self.main, bg=BORDER, height=1).pack(fill=tk.X)
        bar = tk.Frame(self.main, bg=BG_PANEL, pady=5)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        left_bar = tk.Frame(bar, bg=BG_PANEL)
        left_bar.pack(side=tk.LEFT, padx=10)
        if self._status_icon:
            tk.Label(left_bar, image=self._status_icon, bg=BG_PANEL).pack(side=tk.LEFT, padx=(0, 6))
        self.status_label = tk.Label(left_bar, text="Connecting...", fg=TEXT_SEC, bg=BG_PANEL, font=(FONT, 8))
        self.status_label.pack(side=tk.LEFT)
        self._hint_label = tk.Label(bar, text="Ctrl+Shift+Space: Shield ON  |  Alt+Space: Voice", fg=TEXT_SEC, bg=BG_PANEL, font=(FONT, 8))
        self._hint_label.pack(side=tk.RIGHT, padx=10)

    def _make_ctrl_btn(self, parent, text, cmd, color):
        btn = tk.Button(parent, text=text, bg=BG_PANEL, fg=color, font=(FONT, 11), relief=tk.FLAT, bd=0, padx=5, pady=3, cursor="hand2", command=cmd, activebackground=BG_CARD, activeforeground=color)
        btn.bind("<Enter>", lambda e: btn.configure(bg=BG_CARD))
        btn.bind("<Leave>", lambda e: btn.configure(bg=BG_PANEL))
        return btn

    def _pill_btn(self, parent, text, bg_color, cmd, fg_color="white", padx=12, pady=6):
        btn = tk.Button(parent, text=text, bg=bg_color, fg=fg_color, font=(FONT, 10, "bold"), relief=tk.FLAT, bd=0, padx=padx, pady=pady, cursor="hand2", command=cmd, activebackground=bg_color, activeforeground=fg_color)
        return btn

    def _hover(self, w, hc, nc, hfg=None, nfg=None):
        w.bind("<Enter>", lambda e: w.configure(bg=hc, **({"fg": hfg} if hfg else {})))
        w.bind("<Leave>", lambda e: w.configure(bg=nc, **({"fg": nfg} if nfg else {})))

    def _set_status(self, msg, color=TEXT_MUTED):
        self.status_label.configure(text=msg, fg=color)

    def _start_drag(self, e):
        self._drag_x = e.x_root - self.root.winfo_x()
        self._drag_y = e.y_root - self.root.winfo_y()

    def _do_drag(self, e):
        self.root.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")

    def _on_enter(self, event):
        if not event.state & 0x1:
            self._send_chat()
            return "break"

    def _send_chat(self):
        q = self.chat_input.get("1.0", tk.END).strip()
        if not q or q in [TRANSLATIONS[l]["ask_placeholder"] for l in TRANSLATIONS]: return
        self.chat_input.delete("1.0", tk.END)
        self._append_chat("You", q, "user_label", "user_msg")
        self._append_chat("AI", "Thinking...", "ai_label", "thinking")
        threading.Thread(target=self._fetch_ai_response, args=(q,), daemon=True).start()

    def _quick_ask(self, prompt):
        self._append_chat("You", prompt, "user_label", "user_msg")
        self._append_chat("AI", "Thinking...", "ai_label", "thinking")
        threading.Thread(target=self._fetch_ai_response, args=(prompt,), daemon=True).start()

    def _fetch_ai_response(self, q):
        # We pass speak=False so it only speaks if the user clicks the 🔊 icon
        result = api_post("api/ask", {"question": q, "speak": False}, timeout=60)
        answer = result.get("answer", result.get("error", "No response"))
        # Fallback: if AI answered but didn't embed action tags, detect keywords
        self._try_keyword_action(q)
        self.root.after(0, self._replace_thinking, answer)

    def _append_chat(self, sender, msg, label_tag, msg_tag):
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"\n{sender}:\n", label_tag)
        self.chat_display.insert(tk.END, f"{msg}\n", msg_tag)
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def _replace_thinking(self, answer):
        self.chat_display.configure(state=tk.NORMAL)
        content = self.chat_display.get("1.0", tk.END)
        idx = content.rfind("Thinking...")
        if idx >= 0:
            start_index = f"1.0 + {idx} chars"
            end_index = f"1.0 + {idx + len('Thinking...')} chars"
            self.chat_display.delete(start_index, end_index)
            self.chat_display.insert(start_index, answer, "ai_msg")
            
            # Add a clickable speaker icon immediately after the text
            speaker_idx = f"{start_index} + {len(answer)} chars"
            self.chat_display.insert(speaker_idx, "  ")
            
            # We use a Label inside the Text widget
            btn = tk.Label(
                self.chat_display, 
                text="🔊", 
                bg=BG_DARK, 
                fg=CYAN, 
                font=(FONT, 10), 
                cursor="hand2"
            )
            # When clicked, send exactly this answer text to the TTS endpoint
            btn.bind("<Button-1>", lambda e, a=answer: threading.Thread(
                target=lambda: api_post("api/tts/speak", {"text": a}), 
                daemon=True
            ).start())
            
            self.chat_display.window_create(f"{speaker_idx} + 2 chars", window=btn)

        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def _toggle_transcription(self):
        if self.transcription_active:
            api_post("api/transcription/stop")
            self.transcription_active = False
            self.mic_btn.configure(text=self._tr("start_listening"), bg=CYAN)
            self.live_dot.configure(fg=TEXT_MUTED)
            self.live_label.configure(text=self._tr("idle_lbl"), fg=TEXT_MUTED)
            self._set_status("Transcription stopped", TEXT_MUTED)
        else:
            api_post("api/transcription/start")
            self.transcription_active = True
            self.mic_btn.configure(text=self._tr("stop_listening"), bg=RED)
            self.live_dot.configure(fg=RED)
            self.live_label.configure(text=self._tr("live_lbl"), fg=GREEN)
            self._set_status("🎙  Listening...", GREEN)

    def _add_transcript_line(self, text):
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M")
        self.transcript_display.configure(state=tk.NORMAL)
        self.transcript_display.insert(tk.END, f"[{ts}] ", "ts")
        self.transcript_display.insert(tk.END, f"{text}\n", "line")
        self.transcript_display.configure(state=tk.DISABLED)
        self.transcript_display.see(tk.END)

    def _clear_transcript(self):
        try:
            requests.delete(f"{BACKEND}/api/transcript", timeout=3)
        except Exception:
            pass
        self.transcript_display.configure(state=tk.NORMAL)
        self.transcript_display.delete("1.0", tk.END)
        self.transcript_display.configure(state=tk.DISABLED)

    def _action_summarize(self):
        self._set_ar("⏳ Summarizing...")
        threading.Thread(target=lambda: self._run_action("api/summarize", "summary"), daemon=True).start()

    def _action_items(self):
        self._set_ar("⏳ Extracting action items...")
        threading.Thread(target=lambda: self._run_action("api/action-items", "items"), daemon=True).start()

    def _action_reset(self):
        api_post("api/reset")
        self._clear_transcript()
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.configure(state=tk.DISABLED)
        self._set_status("Session reset", ORANGE)

    def _action_refresh(self):
        api_post("api/reset")
        self._clear_transcript()
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.configure(state=tk.DISABLED)
        self._set_status(self._tr("session_refresh_s"), ORANGE)
        self._toast(self._tr("session_refreshed"), ORANGE)

    def _activate_siri_mode(self):
        self._voice_mode = True
        self._start_voice_input()

    def _toggle_tts(self):
        self._tts_enabled = not self._tts_enabled
        icon = "🔊" if self._tts_enabled else "🔇"
        color = CYAN if self._tts_enabled else TEXT_MUTED
        self._tts_btn.configure(text=icon, fg=color)
        label = self._tr("voice_on") if self._tts_enabled else self._tr("voice_off")
        self._toast(label, CYAN if self._tts_enabled else TEXT_MUTED)
        def update():
            try: requests.post(f"{BACKEND}/api/tts/settings", json={"enabled": self._tts_enabled}, timeout=3)
            except: pass
        threading.Thread(target=update, daemon=True).start()

    def _start_voice_input(self):
        if self._mic_listening:
            # Already listening — user clicked Stop
            self._mic_stop_event.set()
            return
        if not SR_AVAILABLE:
            self._toast("SpeechRecognition not installed", RED)
            return
        self._mic_listening = True
        self._mic_stop_event.clear()
        if self._mic_btn:
            self._mic_btn.configure(fg=RED, bg=BG_INPUT, text="⏹ Stop")
        self._voice_mode_btn.configure(fg=RED, text="⏹")
        self._set_status(self._tr("listening"), CYAN)

        def listen():
            recognizer = sr.Recognizer()
            collected_audio = []
            try:
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    # Listen in short 1-second chunks so stop-event is checked frequently
                    while not self._mic_stop_event.is_set():
                        try:
                            chunk = recognizer.listen(source, timeout=1, phrase_time_limit=15)
                            collected_audio.append(chunk)
                            # If we got a chunk and stop wasn't pressed, keep going for phrase end
                            # recognizer naturally stops at phrase_time_limit
                            break  # got a complete phrase — process it
                        except sr.WaitTimeoutError:
                            continue  # no speech yet, check stop_event again

                if self._mic_stop_event.is_set() and not collected_audio:
                    self.root.after(0, self._mic_done)
                    return

                if not collected_audio:
                    self.root.after(0, self._toast, self._tr("no_speech"), ORANGE)
                    self.root.after(0, self._mic_done)
                    return

                audio = collected_audio[0]
                text = recognizer.recognize_google(audio)
                self.root.after(0, self._inject_voice_text, text)

            except sr.UnknownValueError:
                self.root.after(0, self._toast, self._tr("not_understood"), ORANGE)
                self.root.after(0, self._mic_done)
            except Exception as e:
                self.root.after(0, self._toast, f"Mic error: {e}", RED)
                self.root.after(0, self._mic_done)

        threading.Thread(target=listen, daemon=True).start()
    def _inject_voice_text(self, text):
        self._mic_done()
        self.chat_input.delete("1.0", tk.END)
        self.chat_input.configure(fg=TEXT_PRIMARY)
        q = text.strip()
        self._append_chat("You 🎤", q, "user_label", "user_msg")
        self._append_chat("Aura", "Thinking...", "ai_label", "thinking")
        threading.Thread(target=self._fetch_voice_response, args=(q,), daemon=True).start()

    def _fetch_voice_response(self, text):
        result = api_post("api/voice_ask", {"question": text}, timeout=60)
        answer = result.get("answer", result.get("error", "No response"))
        # Fallback: if AI answered but didn't embed action tags, detect keywords
        self._try_keyword_action(text)
        self.root.after(0, self._replace_thinking, answer)

    def _mic_done(self):
        self._mic_listening = False
        self._voice_mode = False
        self._mic_stop_event.clear()
        if self._mic_btn:
            self._mic_btn.configure(fg=CYAN, bg=BG_CARD2, text="🎤")
        self._voice_mode_btn.configure(fg=ACCENT_LIGHT, text="🎤")
        self._set_status("✅ AI Ready", GREEN)

    def _try_keyword_action(self, text: str):
        """Keyword-based fallback to execute actions even if AI skips the <<ACTION>> tags."""
        q = text.lower().strip()
        # App opening
        app_keywords = {
            "spotify": "spotify", "chrome": "chrome", "google chrome": "chrome",
            "firefox": "firefox", "discord": "discord", "notepad": "notepad",
            "calculator": "calc", "vs code": "code", "vscode": "code",
            "vlc": "vlc", "teams": "teams", "zoom": "zoom",
            "whatsapp": "whatsapp", "telegram": "telegram",
            "explorer": "explorer", "file manager": "explorer",
            "paint": "mspaint", "word": "winword", "excel": "excel",
        }
        open_triggers = ["open ", "launch ", "start ", "run ", "play "]
        for trigger in open_triggers:
            if trigger in q:
                rest = q.split(trigger, 1)[1].strip()
                for keyword, app in app_keywords.items():
                    if keyword in rest:
                        threading.Thread(
                            target=lambda a=app: api_post("api/command", {"command": "open_app", "params": {"app": a}}, timeout=10),
                            daemon=True
                        ).start()
                        return
        # Direct app mention (e.g. just "spotify")
        for keyword, app in app_keywords.items():
            if q == keyword or q == "open " + keyword:
                threading.Thread(
                    target=lambda a=app: api_post("api/command", {"command": "open_app", "params": {"app": a}}, timeout=10),
                    daemon=True
                ).start()
                return
        # System actions
        if any(w in q for w in ["lock", "lock screen", "lock the screen", "lock pc"]):
            threading.Thread(
                target=lambda: api_post("api/command", {"command": "system", "params": {"action": "lock"}}, timeout=5),
                daemon=True
            ).start()
        elif any(w in q for w in ["screenshot", "take a screenshot", "capture screen"]):
            threading.Thread(
                target=lambda: api_post("api/command", {"command": "screenshot", "params": {}}, timeout=10),
                daemon=True
            ).start()
        elif any(w in q for w in ["mute", "mute audio", "mute the audio", "mute sound"]):
            threading.Thread(
                target=lambda: api_post("api/command", {"command": "system", "params": {"action": "mute"}}, timeout=5),
                daemon=True
            ).start()
        elif any(w in q for w in ["battery", "battery status", "battery level"]):
            threading.Thread(
                target=lambda: api_post("api/command", {"command": "system", "params": {"action": "battery"}}, timeout=5),
                daemon=True
            ).start()
        elif any(w in q for w in ["shutdown", "shut down", "turn off computer"]):
            threading.Thread(
                target=lambda: api_post("api/command", {"command": "system", "params": {"action": "shutdown"}}, timeout=5),
                daemon=True
            ).start()
        elif any(w in q for w in ["restart", "reboot"]):
            threading.Thread(
                target=lambda: api_post("api/command", {"command": "system", "params": {"action": "restart"}}, timeout=5),
                daemon=True
            ).start()
        elif any(w in q for w in ["sleep", "sleep mode"]):
            threading.Thread(
                target=lambda: api_post("api/command", {"command": "system", "params": {"action": "sleep"}}, timeout=5),
                daemon=True
            ).start()

    def _action_rephrase(self):
        text = self.rephrase_input.get("1.0", tk.END).strip()
        if not text: return
        self._set_ar("⏳ Rephrasing...")
        def _do():
            r = api_post("api/rephrase", {"text": text}, timeout=15)
            ans = r.get("rephrased", r.get("error", ""))
            self.root.after(0, self._set_ar, ans)
        threading.Thread(target=_do, daemon=True).start()

    def _run_action(self, endpoint, key):
        r = api_post(endpoint, timeout=30)
        ans = r.get(key, r.get("error", ""))
        self.root.after(0, self._set_ar, ans)

    def _run_command(self, cmd, params):
        self._set_status(f"⚡ Running {cmd}...", CYAN)
        def _do():
            r = api_post("api/command", {"command": cmd, "params": params}, timeout=10)
            msg = r.get("result", r.get("error", ""))
            self.root.after(0, self._set_status, f"⚡ {msg}", TEXT_SEC)
            self.root.after(0, self._toast, f"Launched {cmd}", GREEN)
        threading.Thread(target=_do, daemon=True).start()

    def _set_ar(self, t):
        self.actions_result.configure(state=tk.NORMAL)
        self.actions_result.delete("1.0", tk.END)
        self.actions_result.insert("1.0", t)
        self.actions_result.configure(state=tk.DISABLED)

    def _cmd_open_url(self):
        url = self.url_entry.get().strip()
        self._run_command("open_url", {"url": url})

    def _cmd_google_search(self):
        q = self.google_entry.get().strip()
        self._run_command("search_google", {"query": q})

    def _cmd_discord_send(self):
        m = self.discord_entry.get("1.0", tk.END).strip()
        if m:
            self.discord_entry.delete("1.0", tk.END)
            self._run_command("discord_send", {"message": m})
            self._toast("Message typed to Discord", GREEN)

    def _open_settings(self):
        d = tk.Toplevel(self.root)
        d.title("Settings")
        d.geometry("460x300")
        d.configure(bg=BG_DARK)
        d.transient(self.root)
        d.grab_set()
        sw, sh = get_screen_size()
        d.geometry(f"+{(sw-460)//2}+{(sh-300)//2}")
        
        tk.Label(d, text="Settings", bg=ACCENT_DARK, fg=TEXT_PRIMARY, font=(FONT_BOLD, 12, "bold"), pady=8).pack(fill=tk.X)
        body = tk.Frame(d, bg=BG_DARK, padx=20, pady=20)
        body.pack(fill=tk.BOTH, expand=True)

        tk.Label(body, text="🔑  OpenRouter API Key", fg=TEXT_PRIMARY, bg=BG_DARK, font=(FONT, 11, "bold")).pack(anchor=tk.W)
        tk.Label(body, text="Get key: openrouter.ai/keys (Free or Paid)", fg=TEXT_SEC, bg=BG_DARK, font=(FONT, 9)).pack(anchor=tk.W)
        tk.Label(body, text="Format: sk-or-v1-...", fg=TEXT_MUTED, bg=BG_DARK, font=(FONT, 8)).pack(anchor=tk.W, pady=(0, 8))

        e_border = tk.Frame(body, bg=BORDER_GLOW, padx=1, pady=1)
        e_border.pack(fill=tk.X)
        key_entry = tk.Entry(e_border, bg=BG_INPUT, fg=TEXT_PRIMARY, font=(FONT, 10), relief=tk.FLAT, bd=0, insertbackground=TEXT_PRIMARY)
        key_entry.pack(fill=tk.X, ipady=8, padx=12)

        result_lbl = tk.Label(body, text="", bg=BG_DARK, font=(FONT, 9), wraplength=380, justify=tk.LEFT)
        result_lbl.pack(anchor=tk.W)

        save_btn = tk.Button(body, text="Save API Key", bg=ACCENT, fg="white", font=(FONT_BOLD, 10, "bold"), relief=tk.FLAT, bd=0, padx=20, pady=9, cursor="hand2")
        save_btn.pack(pady=12)

        def do_save():
            key = key_entry.get().strip()
            if not key:
                self.root.after(0, result_lbl.configure, {"text": "Please enter an API key", "fg": RED})
                self.root.after(0, save_btn.configure, {"state": tk.NORMAL, "text": "Save API Key"})
                return
            res = api_post("api/key", {"api_key": key}, timeout=30)
            detail = res.get("detail", res.get("error", ""))
            quota_hit = any(x in detail for x in ["quota", "429", "RESOURCE_EXHAUSTED", "exhausted"])
            if quota_hit:
                def _on_quota():
                    result_lbl.configure(text=self._tr("quota_warn"), fg=ORANGE)
                    self.api_key_configured = True
                    self.api_warning.pack_forget()
                    self._set_status(self._tr("quota_warn"), ORANGE)
                    save_btn.configure(state=tk.NORMAL, text="Save API Key")
                    self.root.after(2000, lambda: d.destroy() if d.winfo_exists() else None)
                self.root.after(0, _on_quota)
            elif "detail" in res or "error" in res:
                def _on_err():
                    result_lbl.configure(text=f"❌  {detail}", fg=RED)
                    save_btn.configure(state=tk.NORMAL, text="Save API Key")
                self.root.after(0, _on_err)
            else:
                def _on_ok():
                    result_lbl.configure(text="✅  Key verified and saved!", fg=GREEN)
                    self.api_key_configured = True
                    self.api_warning.pack_forget()
                    self._set_status("✅  AI ready", GREEN)
                    save_btn.configure(state=tk.NORMAL, text="Save API Key")
                    self.root.after(800, lambda: d.destroy() if d.winfo_exists() else None)
                self.root.after(0, _on_ok)

        def save():
            key = key_entry.get().strip()
            if not key:
                result_lbl.configure(text="Please enter an API key", fg=RED)
                return
            result_lbl.configure(text="⏳ Verifying key...", fg=YELLOW)
            save_btn.configure(state=tk.DISABLED, text="Saving...")
            threading.Thread(target=do_save, daemon=True).start()
        save_btn.configure(command=save)

    def _start_wake_word(self):
        if not WAKE_WORD_AVAILABLE or self._wake_detector: return
        self._wake_word_enabled = True
        self._wake_detector = WakeWordDetector(on_wake_word=self._on_wake_detected)
        self._wake_detector.start()
        self._set_status("🚨  Wake word active — say 'Hey Aura'", ACCENT_LIGHT)

    def _stop_wake_word(self):
        if self._wake_detector:
            self._wake_detector.stop()
            self._wake_detector = None
        self._wake_word_enabled = False

    def _on_wake_detected(self):
        if self._mic_listening: return
        self.root.after(0, self._handle_wake_word)

    def _handle_wake_word(self):
        if self.root.state() == "withdrawn":
            self.root.deiconify()
        self.root.lift()
        self._toast("🚨 Hey Aura! Listening...", ACCENT_LIGHT)
        self._set_status("🚨  Wake word detected!", ACCENT_LIGHT)
        self.root.after(400, self._activate_siri_mode)

    def _apply_stealth(self):
        """Apply screen-capture exclusion + taskbar hiding. Must be called AFTER the window is visible."""
        def _do():
            # 1. Exclude window content from screen-capture (Discord, OBS, Teams, etc.)
            success = apply_stealth(title="Aura AI")
            # 2. Remove taskbar button so the icon doesn't appear in the nav bar
            hide_from_taskbar(title="Aura AI")
            msg = (self._tr("stealth_active"), GREEN) if success else ("⚠️  Stealth requires Windows 10 v2004+", ORANGE)
            self.root.after(0, lambda: self._set_status(*msg))
        threading.Thread(target=_do, daemon=True).start()

    def _check_backend(self):
        def check():
            for _ in range(20):
                try:
                    r = requests.get(f"{BACKEND}/", timeout=2)
                    data = r.json()
                    self.api_key_configured = data.get("api_key_set", False)
                    self.root.after(0, self._on_backend_ready)
                    return
                except Exception:
                    time.sleep(0.5)
            self.root.after(0, lambda: self._set_status("❌ Backend unreachable", RED))
        threading.Thread(target=check, daemon=True).start()

    def _on_backend_ready(self):
        self._set_status(self._tr("backend_connected"), GREEN)
        status = api_get("api/key/status")
        if status.get("configured"):
            self.api_key_configured = True
            self.api_warning.pack_forget()
        self.root.after(500, self._check_tts_on_start)

    def _connect_websocket(self):
        def run():
            while True:
                try:
                    ws = websocket.WebSocketApp(WS_URL, on_message=self._on_ws_message, on_error=lambda ws, e: None, on_close=lambda ws, c, m: None)
                    ws.run_forever(ping_interval=20, ping_timeout=10)
                except Exception:
                    pass
                time.sleep(3)
        threading.Thread(target=run, daemon=True).start()

    def _on_ws_message(self, ws, message):
        try:
            msg = json.loads(message)
            t = msg.get("type")
            if t == "transcript":
                self.root.after(0, self._add_transcript_line, msg.get("text", ""))
            elif t == "meeting_detected":
                self.root.after(0, self._set_status, f"📹 {msg.get('platform','')} · {msg.get('title','')}", ACCENT)
            elif t == "error":
                self.root.after(0, self._set_status, f"⚠️ {msg.get('text','')}", ORANGE)
            elif t == "action_result":
                color = GREEN if msg.get("success", True) else RED
                self.root.after(0, self._toast, msg.get("text", ""), color)
            elif t == "voice_response":
                q = msg.get("question", "")
                ans = msg.get("text", "")
                if q: self.root.after(0, self._show_voice_exchange, q, ans)
            elif t == "connected":
                tts_ok = msg.get("tts_available", False)
                if tts_ok:
                    self.root.after(0, self._set_status, self._tr("ai_ready_tts"), GREEN)
        except Exception:
            pass

    def _show_voice_exchange(self, question: str, answer: str):
        self._append_chat("You 🎤", question, "user_label", "user_msg")
        self._replace_thinking(answer) if "Thinking..." in self.chat_display.get("1.0", tk.END) else self._append_chat("Aura", answer, "ai_label", "ai_msg")

    def _toast(self, message, color=None):
        color = color or GREEN
        t = tk.Toplevel(self.root)
        t.overrideredirect(True)
        t.configure(bg=BORDER_GLOW)
        t.attributes("-topmost", True)
        f = tk.Frame(t, bg=BG_CARD, padx=16, pady=8)
        f.pack(padx=1, pady=1)
        tk.Label(f, text=message, fg=color, bg=BG_CARD, font=(FONT_BOLD, 9, "bold")).pack()
        sw, sh = get_screen_size()
        t.update_idletasks()
        w, h = t.winfo_width(), t.winfo_height()
        t.geometry(f"{w}x{h}+{sw//2 - w//2}+{sh - 120}")
        apply_stealth(t.winfo_id())
        self.root.after(3000, t.destroy)

    def _on_close(self):
        """Called when the user clicks the X button."""
        self._pulse_running = False
        self._stop_wake_word()
        # Kill the backend server gracefully
        threading.Thread(target=lambda: api_post("api/shutdown", timeout=3), daemon=True).start()
        # Let the thread fire the shutdown request, then destroy UI
        self.root.after(200, self.root.destroy)
        self.root.after(300, lambda: sys.exit(0))


    def _toggle_visibility(self, event=None):
        """Toggle screen-share invisibility.
        The window always stays visible to the local user.
        When stealth is ON  → viewers on screen share see nothing (black).
        When stealth is OFF → viewers see the window normally.
        Uses FindWindowW internally to get the real Win32 HWND.
        """
        if self._stealth_on:
            # Disable exclusion — window becomes visible to screen share
            self._stealth_on = False
            def _off():
                remove_stealth(title="Aura AI")
            threading.Thread(target=_off, daemon=True).start()
            self._toast("👁  Screen-share visible — they can see you!", RED)
            self._set_status("👁  Screen-share: VISIBLE", RED)
            try:
                self._hint_label.configure(text="Ctrl+Shift+Space: Shield OFF  |  Alt+Space: Voice")
            except Exception:
                pass
        else:
            # Re-enable exclusion — window hidden from screen share
            self._stealth_on = True
            def _on():
                apply_stealth(title="Aura AI")
            threading.Thread(target=_on, daemon=True).start()
            self._toast("🛡️  Screen-share hidden — you are invisible!", CYAN)
            self._set_status("🛡️  Screen-share: HIDDEN", CYAN)
            try:
                self._hint_label.configure(text="Ctrl+Shift+Space: Shield ON  |  Alt+Space: Voice")
            except Exception:
                pass

    def run(self):
        self.root.mainloop()

    def _check_tts_on_start(self):
        def check():
            try:
                r = api_get("api/tts/status")
                enabled = r.get("enabled", True)
                avail = r.get("available", False)
                self._tts_enabled = enabled
                if not avail:
                    self.root.after(0, lambda: self._set_status("⚠️  TTS unavailable — install pyttsx3", ORANGE))
            except Exception:
                pass
        threading.Thread(target=check, daemon=True).start()

if __name__ == "__main__":
    AIAssistantHUD().run()
