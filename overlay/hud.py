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

# ── Tell Windows this is its own app (taskbar icon fix) ──────────────────────
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        u'AuraAI.HUD.1'
    )
except Exception:
    pass

sys.stdout = open(os.devnull, "w")
sys.stderr = open(os.devnull, "w")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stealth import apply_stealth, get_window_hwnd, get_screen_size

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

BACKEND = "http://localhost:8000"
WS_URL  = "ws://localhost:8000/ws"

# ─── Premium Color Palette ────────────────────────────────────────────────────
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


def api_post(endpoint, payload=None, timeout=15):
    try:
        r = requests.post(f"{BACKEND}/{endpoint}", json=payload or {}, timeout=timeout)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def api_get(endpoint, timeout=5):
    try:
        r = requests.get(f"{BACKEND}/{endpoint}", timeout=timeout)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ─── Rounded Rectangle Canvas Helper ─────────────────────────────────────────
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
        # Start at a comfortable window size, centered on screen
        w, h = 750, 580
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.withdraw()  # hide until setup done

        self.root.overrideredirect(False)
        self.root.attributes("-topmost", False)  # start behind other windows
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

        self._load_icon()
        self._build_ui()
        self._apply_stealth()
        self._check_backend()
        self._connect_websocket()
        self._start_pulse()

        self.root.bind("<Control-Shift-space>", self._toggle_visibility)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.deiconify()

    # ─── Icon Loading ─────────────────────────────────────────────────────────
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
            # Cache a tiny 14×14 copy for the status bar (reuse already-loaded img)
            self._status_icon = ImageTk.PhotoImage(img.resize((14, 14), Image.LANCZOS))
        except Exception:
            pass

    # ─── Pulse Animation ──────────────────────────────────────────────────────
    def _start_pulse(self):
        self._pulse_running = True
        self._animate_pulse()

    def _animate_pulse(self):
        if not self._pulse_running:
            return
        self._pulse_phase = (self._pulse_phase + 0.08) % (2 * math.pi)
        alpha = int(160 + 95 * math.sin(self._pulse_phase))
        color = f"#{alpha:02x}e5c0" if self.transcription_active else f"#{alpha//3:02x}{alpha//3:02x}{alpha//2:02x}"
        try:
            self.pulse_dot.configure(fg=color)
        except Exception:
            pass
        self.root.after(50, self._animate_pulse)

    # ─── Main UI Build ────────────────────────────────────────────────────────
    def _build_ui(self):
        self.main = tk.Frame(self.root, bg=BG_ROOT)
        self.main.pack(fill=tk.BOTH, expand=True)
        self._build_header()
        self._build_tab_bar()
        self._build_content()
        self._build_status_bar()

    # ─── Header ───────────────────────────────────────────────────────────────
    def _build_header(self):
        # Top gradient accent bar (simulated with 3 thin lines)
        for color, h in [(ACCENT_DARK, 1), (ACCENT, 2), (ACCENT_LIGHT, 1)]:
            tk.Frame(self.main, bg=color, height=h).pack(fill=tk.X)

        hdr = tk.Frame(self.main, bg=BG_PANEL, pady=14)
        hdr.pack(fill=tk.X)
        hdr.bind("<Button-1>", self._start_drag)
        hdr.bind("<B1-Motion>", self._do_drag)

        # Left: brain icon + title block
        left = tk.Frame(hdr, bg=BG_PANEL)
        left.pack(side=tk.LEFT, padx=16)
        left.bind("<Button-1>", self._start_drag)
        left.bind("<B1-Motion>", self._do_drag)

        if self._icon_small:
            # Icon with subtle glow ring (canvas)
            icon_canvas = tk.Canvas(left, width=44, height=44,
                                    bg=BG_PANEL, highlightthickness=0)
            icon_canvas.pack(side=tk.LEFT, padx=(0, 12))
            icon_canvas.create_oval(2, 2, 42, 42, outline=ACCENT_DARK, width=1)
            icon_canvas.create_image(22, 22, image=self._icon_small)
            icon_canvas.bind("<Button-1>", self._start_drag)
            icon_canvas.bind("<B1-Motion>", self._do_drag)
        else:
            tk.Label(left, text="🧠", bg=BG_PANEL,
                     font=(FONT, 22)).pack(side=tk.LEFT, padx=(0, 12))

        title_col = tk.Frame(left, bg=BG_PANEL)
        title_col.pack(side=tk.LEFT)
        title_col.bind("<Button-1>", self._start_drag)
        title_col.bind("<B1-Motion>", self._do_drag)

        tk.Label(title_col, text="Aura AI",
                 fg=TEXT_PRIMARY, bg=BG_PANEL,
                 font=(FONT_BOLD, 16, "bold")).pack(anchor=tk.W)

        sub_row = tk.Frame(title_col, bg=BG_PANEL)
        sub_row.pack(anchor=tk.W)
        self.pulse_dot = tk.Label(sub_row, text="●",
                                   fg=TEXT_MUTED, bg=BG_PANEL,
                                   font=(FONT, 9))
        self.pulse_dot.pack(side=tk.LEFT)
        tk.Label(sub_row, text="  AI · Stealth · Always On",
                 fg=TEXT_SEC, bg=BG_PANEL,
                 font=(FONT, 9)).pack(side=tk.LEFT)

        # Right: stealth badge + controls
        right = tk.Frame(hdr, bg=BG_PANEL)
        right.pack(side=tk.RIGHT, padx=12)

        # Stealth pill
        pill = tk.Frame(right, bg="#0a2018", padx=10, pady=4)
        pill.pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(pill, text="🛡  STEALTH",
                 fg=CYAN, bg="#0a2018",
                 font=(FONT, 8, "bold")).pack()

        self._make_ctrl_btn(right, "⚙", self._open_settings, TEXT_SEC).pack(side=tk.LEFT, padx=2)
        self._make_ctrl_btn(right, "✕", self._on_close, RED).pack(side=tk.LEFT, padx=2)

        # Bottom border
        tk.Frame(self.main, bg=BORDER, height=1).pack(fill=tk.X)

    # ─── Tab Bar ──────────────────────────────────────────────────────────────
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

            btn = tk.Button(
                col, text=label,
                bg=ACCENT if key == "chat" else BG_PANEL,
                fg=TEXT_PRIMARY if key == "chat" else TEXT_SEC,
                font=(FONT, 10, "bold"),
                relief=tk.FLAT, bd=0, padx=14, pady=6,
                cursor="hand2",
                command=lambda k=key: self._switch_tab(k)
            )
            btn.pack()

            # Active underline indicator
            indicator = tk.Frame(col, bg=ACCENT if key == "chat" else BG_PANEL, height=2)
            indicator.pack(fill=tk.X, padx=4)

            self.tab_buttons[key] = btn
            self._tab_indicators[key] = indicator

            if key != "chat":
                self._hover(btn, BG_CARD, BG_PANEL, TEXT_PRIMARY, TEXT_SEC)

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

    # ─── Content Area ─────────────────────────────────────────────────────────
    def _build_content(self):
        self.content = tk.Frame(self.main, bg=BG_DARK)
        self.content.pack(fill=tk.BOTH, expand=True)
        self._build_chat_tab()
        self._build_transcript_tab()
        self._build_actions_tab()
        self._switch_tab("chat")

    # ─── Chat Tab ─────────────────────────────────────────────────────────────
    def _build_chat_tab(self):
        frame = tk.Frame(self.content, bg=BG_DARK)
        self.tab_frames["chat"] = frame

        # API warning card (top)
        self.api_warning = tk.Frame(frame, bg="#1a1000", pady=6, padx=12)
        self.api_warning.pack(fill=tk.X, padx=12, pady=(10, 0))
        tk.Label(self.api_warning,
                 text="⚠️  No API key — click ⚙ to add your free Gemini key",
                 fg=ORANGE, bg="#1a1000",
                 font=(FONT, 10)).pack()

        # ── Pack bottom elements FIRST so they always stay visible ──

        # Input panel (bottom)
        input_panel = tk.Frame(frame, bg=BG_CARD, pady=10, padx=12)
        input_panel.pack(fill=tk.X, side=tk.BOTTOM, padx=12, pady=(0, 6))

        # Input field with focus glow
        input_border = tk.Frame(input_panel, bg=BORDER_GLOW, padx=1, pady=1)
        input_border.pack(fill=tk.X)

        self.chat_input = tk.Text(
            input_border,
            bg=BG_INPUT, fg=TEXT_PRIMARY,
            font=(FONT, 11),
            relief=tk.FLAT, bd=0,
            height=2, wrap=tk.WORD,
            insertbackground=ACCENT_LIGHT,
            padx=12, pady=8
        )
        self.chat_input.pack(fill=tk.X)
        self.chat_input.insert("1.0", "Ask anything...")
        self.chat_input.configure(fg=TEXT_MUTED)
        self.chat_input.bind("<FocusIn>", self._inp_focus_in)
        self.chat_input.bind("<FocusOut>", self._inp_focus_out)
        self.chat_input.bind("<Return>", self._on_enter)
        self.chat_input.bind("<Shift-Return>", lambda e: None)
        self._input_border = input_border

        # Send button row
        btn_row = tk.Frame(input_panel, bg=BG_CARD)
        btn_row.pack(fill=tk.X, pady=(8, 0))

        hint = tk.Label(btn_row, text="Enter to send · Shift+Enter for newline",
                        fg=TEXT_MUTED, bg=BG_CARD, font=(FONT, 8))
        hint.pack(side=tk.LEFT)

        send_btn = tk.Button(
            btn_row, text="Send  ↵",
            bg=ACCENT, fg="white",
            font=(FONT_BOLD, 9, "bold"),
            relief=tk.FLAT, bd=0, padx=18, pady=7,
            cursor="hand2", activebackground=ACCENT_HOVER,
            activeforeground="white",
            command=self._send_chat
        )
        send_btn.pack(side=tk.RIGHT)
        self._hover(send_btn, ACCENT_HOVER, ACCENT)

        # Quick prompt chips (above input)
        chips_frame = tk.Frame(frame, bg=BG_DARK)
        chips_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=12, pady=(0, 4))

        prompts = [
            ("📝  Summarize", "Summarize the meeting so far"),
            ("✅  Action Items", "What are the action items?"),
            ("❓  Explain", "Explain the last topic discussed"),
        ]
        for label, prompt in prompts:
            chip = tk.Button(
                chips_frame, text=label,
                bg=BG_CARD2, fg=TEXT_SEC,
                font=(FONT, 9), relief=tk.FLAT, bd=0,
                padx=10, pady=5, cursor="hand2",
                command=lambda p=prompt: self._quick_ask(p)
            )
            chip.pack(side=tk.LEFT, padx=2)
            self._hover(chip, BG_INPUT, BG_CARD2, TEXT_ACCENT, TEXT_SEC)

        # ── Chat display fills remaining space ──
        chat_outer = tk.Frame(frame, bg=BORDER, bd=0)
        chat_outer.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        self.chat_display = tk.Text(
            chat_outer,
            bg=BG_CARD, fg=TEXT_PRIMARY,
            font=(FONT, 11),
            relief=tk.FLAT, bd=0,
            wrap=tk.WORD,
            state=tk.DISABLED,
            insertbackground=ACCENT,
            selectbackground=ACCENT_DARK,
            selectforeground=TEXT_PRIMARY,
            padx=14, pady=12,
            spacing1=3, spacing2=2, spacing3=5
        )
        scroll = tk.Scrollbar(chat_outer, command=self.chat_display.yview,
                              bg=BG_CARD, troughcolor=BG_CARD2,
                              activebackground=ACCENT_DARK, width=6,
                              relief=tk.FLAT, bd=0)
        self.chat_display.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Tags for beautiful message styling
        self.chat_display.tag_configure("user_label",
            foreground=ACCENT_LIGHT, font=(FONT_BOLD, 10, "bold"))
        self.chat_display.tag_configure("user_msg",
            foreground=TEXT_PRIMARY, font=(FONT, 11),
            lmargin1=12, lmargin2=12)
        self.chat_display.tag_configure("ai_label",
            foreground=CYAN, font=(FONT_BOLD, 10, "bold"))
        self.chat_display.tag_configure("ai_msg",
            foreground="#e8ecff", font=(FONT, 11),
            lmargin1=12, lmargin2=12)
        self.chat_display.tag_configure("thinking",
            foreground=TEXT_SEC, font=(FONT, 10, "italic"),
            lmargin1=12)
        self.chat_display.tag_configure("divider",
            foreground=BORDER_GLOW, font=(FONT, 7))

    def _inp_focus_in(self, event):
        self._input_border.configure(bg=ACCENT_DARK)
        if self.chat_input.get("1.0", tk.END).strip() == "Ask anything...":
            self.chat_input.delete("1.0", tk.END)
            self.chat_input.configure(fg=TEXT_PRIMARY)

    def _inp_focus_out(self, event):
        self._input_border.configure(bg=BORDER_GLOW)
        if not self.chat_input.get("1.0", tk.END).strip():
            self.chat_input.insert("1.0", "Ask anything...")
            self.chat_input.configure(fg=TEXT_MUTED)

    # ─── Transcript Tab ───────────────────────────────────────────────────────
    def _build_transcript_tab(self):
        frame = tk.Frame(self.content, bg=BG_DARK)
        self.tab_frames["transcript"] = frame

        ctrl = tk.Frame(frame, bg=BG_DARK)
        ctrl.pack(fill=tk.X, padx=12, pady=12)

        self.mic_btn = tk.Button(
            ctrl, text="🎙  Start Listening",
            bg=CYAN, fg=BG_ROOT,
            font=(FONT_BOLD, 9, "bold"),
            relief=tk.FLAT, bd=0, padx=16, pady=8,
            cursor="hand2",
            command=self._toggle_transcription
        )
        self.mic_btn.pack(side=tk.LEFT)

        clear_btn = tk.Button(
            ctrl, text="🗑  Clear",
            bg=BG_CARD2, fg=TEXT_SEC,
            font=(FONT, 9), relief=tk.FLAT, bd=0,
            padx=12, pady=8, cursor="hand2",
            command=self._clear_transcript
        )
        clear_btn.pack(side=tk.LEFT, padx=8)
        self._hover(clear_btn, BG_INPUT, BG_CARD2)

        # Live indicator with pulse dot
        live_frame = tk.Frame(ctrl, bg=BG_DARK)
        live_frame.pack(side=tk.RIGHT)
        self.live_dot = tk.Label(live_frame, text="●", fg=TEXT_MUTED,
                                  bg=BG_DARK, font=(FONT, 10))
        self.live_dot.pack(side=tk.LEFT)
        self.live_label = tk.Label(live_frame, text=" IDLE", fg=TEXT_MUTED,
                                    bg=BG_DARK, font=(FONT, 8, "bold"))
        self.live_label.pack(side=tk.LEFT)

        # Transcript display
        t_outer = tk.Frame(frame, bg=BORDER)
        t_outer.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self.transcript_display = tk.Text(
            t_outer,
            bg=BG_CARD, fg=TEXT_PRIMARY,
            font=(FONT_MONO, 11),
            relief=tk.FLAT, bd=0,
            wrap=tk.WORD,
            state=tk.DISABLED,
            padx=12, pady=12,
            spacing1=3, spacing2=2, spacing3=5
        )
        ts_scroll = tk.Scrollbar(t_outer, command=self.transcript_display.yview,
                                  bg=BG_CARD, troughcolor=BG_CARD2,
                                  width=6, relief=tk.FLAT, bd=0)
        self.transcript_display.configure(yscrollcommand=ts_scroll.set)
        ts_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.transcript_display.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.transcript_display.tag_configure("ts", foreground=TEXT_SEC,
                                               font=(FONT_MONO, 9))
        self.transcript_display.tag_configure("line", foreground=TEXT_PRIMARY,
                                               font=(FONT_MONO, 11))

    # ─── Actions Tab ──────────────────────────────────────────────────────────
    def _build_actions_tab(self):
        frame = tk.Frame(self.content, bg=BG_DARK)
        self.tab_frames["actions"] = frame

        canvas = tk.Canvas(frame, bg=BG_DARK, highlightthickness=0)
        sb = tk.Scrollbar(frame, orient="vertical", command=canvas.yview,
                          bg=BG_DARK, troughcolor=BG_CARD, width=6,
                          relief=tk.FLAT, bd=0)
        sf = tk.Frame(canvas, bg=BG_DARK)
        sf.bind("<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sf, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        def _sec(title, icon=""):
            row = tk.Frame(sf, bg=BG_DARK)
            row.pack(fill=tk.X, padx=12, pady=(16, 0))
            tk.Label(row, text=f"{icon}  {title}",
                     fg=ACCENT_LIGHT, bg=BG_DARK,
                     font=(FONT_BOLD, 11, "bold")).pack(side=tk.LEFT)
            tk.Frame(sf, bg=BORDER_GLOW, height=1).pack(
                fill=tk.X, padx=12, pady=(4, 8))

        def _card():
            c = tk.Frame(sf, bg=BG_CARD, padx=10, pady=8)
            c.pack(fill=tk.X, padx=12, pady=(0, 4))
            return c

        # ── Open URL ──────────────────────────────────────────────────────────
        _sec("Open URL", "🌐")
        c = _card()
        self.url_entry = tk.Entry(c, bg=BG_INPUT, fg=TEXT_PRIMARY,
                                   font=(FONT, 10), relief=tk.FLAT, bd=0,
                                   insertbackground=TEXT_PRIMARY)
        self.url_entry.insert(0, "https://")
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 8))
        self._pill_btn(c, "Open", ACCENT, self._cmd_open_url).pack(side=tk.RIGHT)

        # ── Google Search ─────────────────────────────────────────────────────
        _sec("Google Search", "🔍")
        c = _card()
        self.google_entry = tk.Entry(c, bg=BG_INPUT, fg=TEXT_PRIMARY,
                                      font=(FONT, 10), relief=tk.FLAT, bd=0,
                                      insertbackground=TEXT_PRIMARY)
        self.google_entry.insert(0, "Search...")
        self.google_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 8))
        self._pill_btn(c, "Search", "#34a853", self._cmd_google_search).pack(side=tk.RIGHT)

        # ── Discord ───────────────────────────────────────────────────────────
        _sec("Discord Message", "💬")
        tk.Label(sf, text="  Discord must be open on a text channel",
                 fg=TEXT_SEC, bg=BG_DARK, font=(FONT, 8)
                 ).pack(padx=12, anchor=tk.W, pady=(0, 4))
        self.discord_entry = tk.Text(sf, bg=BG_INPUT, fg=TEXT_PRIMARY,
                                      font=(FONT, 10), relief=tk.FLAT, bd=0,
                                      height=2, wrap=tk.WORD,
                                      insertbackground=TEXT_PRIMARY,
                                      padx=10, pady=8)
        self.discord_entry.pack(fill=tk.X, padx=12, pady=(0, 6))
        dr = tk.Frame(sf, bg=BG_DARK)
        dr.pack(fill=tk.X, padx=12, pady=(0, 4))
        self._pill_btn(dr, "📨  Send", "#5865F2",
                       self._cmd_discord_send).pack(side=tk.LEFT)
        self._pill_btn(dr, "Open Discord", BG_CARD,
                       lambda: self._run_command("open_app", {"app": "discord"}),
                       fg_color="#5865F2").pack(side=tk.LEFT, padx=6)

        # ── Launch Apps ───────────────────────────────────────────────────────
        _sec("Launch Apps", "🚀")
        grid = tk.Frame(sf, bg=BG_DARK)
        grid.pack(fill=tk.X, padx=12)
        apps = [
            ("🌐 Chrome", "chrome", "#EA4335"),
            ("🎵 Spotify", "spotify", "#1DB954"),
            ("💻 VS Code", "code", ACCENT),
            ("📝 Notepad", "notepad", ORANGE),
            ("🧮 Calc", "calc", CYAN),
            ("🗂 Explorer", "explorer", TEXT_SEC),
            ("💬 Discord", "discord", "#5865F2"),
            ("🎬 VLC", "vlc", "#FF8800"),
        ]
        for i, (label, app, color) in enumerate(apps):
            btn = tk.Button(grid, text=label, bg=BG_CARD2, fg=color,
                            font=(FONT, 9, "bold"), relief=tk.FLAT, bd=0,
                            padx=6, pady=10, cursor="hand2",
                            command=lambda a=app: self._run_command("open_app", {"app": a}))
            btn.grid(row=i//2, column=i%2, padx=3, pady=3, sticky="ew")
            self._hover(btn, BG_INPUT, BG_CARD2)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        # ── System Controls ───────────────────────────────────────────────────
        _sec("System", "🖥️")
        sc = tk.Frame(sf, bg=BG_DARK)
        sc.pack(fill=tk.X, padx=12)
        self._pill_btn(sc, "📸  Screenshot", CYAN_DARK,
                       lambda: self._run_command("screenshot", {}),
                       fg_color=BG_ROOT).pack(side=tk.LEFT)

        vf = tk.Frame(sf, bg=BG_DARK)
        vf.pack(fill=tk.X, padx=12, pady=(8, 4))
        tk.Label(vf, text="🔊", fg=TEXT_SEC, bg=BG_DARK,
                 font=(FONT, 10)).pack(side=tk.LEFT)
        self.vol_slider = tk.Scale(vf, from_=0, to=100, orient=tk.HORIZONTAL,
                                    bg=BG_DARK, fg=TEXT_PRIMARY,
                                    highlightthickness=0,
                                    troughcolor=BG_INPUT,
                                    activebackground=ACCENT,
                                    sliderrelief=tk.FLAT,
                                    length=160, showvalue=True,
                                    font=(FONT, 7))
        self.vol_slider.set(50)
        self.vol_slider.pack(side=tk.LEFT, padx=8)
        self._pill_btn(vf, "Set", ACCENT,
                       lambda: self._run_command("volume", {"level": self.vol_slider.get()})
                       ).pack(side=tk.LEFT)

        # ── Meeting Actions ───────────────────────────────────────────────────
        _sec("Meeting", "📋")
        for label, color, cmd in [
            ("📋  Summarize Meeting", ACCENT, self._action_summarize),
            ("✅  Extract Action Items", CYAN, self._action_items),
            ("🔄  Reset Session", ORANGE, self._action_reset),
        ]:
            btn = tk.Button(sf, text=label, bg=BG_CARD2, fg=color,
                            font=(FONT, 10, "bold"), relief=tk.FLAT, bd=0,
                            padx=16, pady=11, anchor=tk.W, cursor="hand2",
                            command=cmd)
            btn.pack(fill=tk.X, padx=12, pady=2)
            self._hover(btn, BG_INPUT, BG_CARD2)

        # ── Rephrase ─────────────────────────────────────────────────────────
        _sec("Rephrase Tool", "✍️")
        self.rephrase_input = tk.Text(sf, bg=BG_INPUT, fg=TEXT_PRIMARY,
                                       font=(FONT, 10), relief=tk.FLAT, bd=0,
                                       height=3, wrap=tk.WORD,
                                       insertbackground=TEXT_PRIMARY,
                                       padx=10, pady=8)
        self.rephrase_input.pack(fill=tk.X, padx=12, pady=(0, 6))
        self._pill_btn(sf, "✨  Rephrase Professionally", PINK,
                       self._action_rephrase, fg_color=BG_ROOT,
                       padx=14, pady=8
                       ).pack(padx=12, anchor=tk.W, pady=(0, 6))

        result_outer = tk.Frame(sf, bg=BORDER)
        result_outer.pack(fill=tk.X, padx=12, pady=(0, 16))
        self.actions_result = tk.Text(
            result_outer, bg=BG_CARD, fg=TEXT_PRIMARY,
            font=(FONT, 10), relief=tk.FLAT, bd=0,
            height=5, wrap=tk.WORD, state=tk.DISABLED,
            padx=12, pady=10)
        self.actions_result.pack(fill=tk.X)

    # ─── Status Bar ───────────────────────────────────────────────────────────
    def _build_status_bar(self):
        tk.Frame(self.main, bg=BORDER, height=1).pack(fill=tk.X)
        bar = tk.Frame(self.main, bg=BG_PANEL, pady=5)
        bar.pack(fill=tk.X, side=tk.BOTTOM)

        left_bar = tk.Frame(bar, bg=BG_PANEL)
        left_bar.pack(side=tk.LEFT, padx=10)

        # Reuse the cached status icon loaded in _load_icon (no extra disk read)
        if self._status_icon:
            tk.Label(left_bar, image=self._status_icon,
                     bg=BG_PANEL).pack(side=tk.LEFT, padx=(0, 6))

        self.status_label = tk.Label(
            left_bar, text="Connecting...",
            fg=TEXT_SEC, bg=BG_PANEL, font=(FONT, 8))
        self.status_label.pack(side=tk.LEFT)

        tk.Label(bar, text="Ctrl+Shift+Space: Hide",
                 fg=TEXT_SEC, bg=BG_PANEL,
                 font=(FONT, 8)).pack(side=tk.RIGHT, padx=10)

    # ─── Widget Helpers ───────────────────────────────────────────────────────
    def _make_ctrl_btn(self, parent, text, cmd, color):
        btn = tk.Button(parent, text=text, bg=BG_PANEL, fg=color,
                        font=(FONT, 11), relief=tk.FLAT, bd=0,
                        padx=5, pady=3, cursor="hand2", command=cmd,
                        activebackground=BG_CARD, activeforeground=color)
        btn.bind("<Enter>", lambda e: btn.configure(bg=BG_CARD))
        btn.bind("<Leave>", lambda e: btn.configure(bg=BG_PANEL))
        return btn

    def _pill_btn(self, parent, text, bg_color, cmd, fg_color="white",
                  padx=12, pady=6):
        btn = tk.Button(parent, text=text, bg=bg_color, fg=fg_color,
                        font=(FONT, 10, "bold"), relief=tk.FLAT, bd=0,
                        padx=padx, pady=pady, cursor="hand2", command=cmd,
                        activebackground=bg_color, activeforeground=fg_color)
        return btn

    def _hover(self, w, hc, nc, hfg=None, nfg=None):
        w.bind("<Enter>", lambda e: w.configure(bg=hc, **({"fg": hfg} if hfg else {})))
        w.bind("<Leave>", lambda e: w.configure(bg=nc, **({"fg": nfg} if nfg else {})))

    def _set_status(self, msg, color=TEXT_MUTED):
        self.status_label.configure(text=msg, fg=color)

    # ─── Drag ─────────────────────────────────────────────────────────────────
    def _start_drag(self, e):
        self._drag_x = e.x_root - self.root.winfo_x()
        self._drag_y = e.y_root - self.root.winfo_y()

    def _do_drag(self, e):
        self.root.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")

    # ─── Chat ─────────────────────────────────────────────────────────────────
    def _on_enter(self, event):
        if not event.state & 0x1:
            self._send_chat()
            return "break"

    def _send_chat(self):
        q = self.chat_input.get("1.0", tk.END).strip()
        if not q or q == "Ask anything...":
            return
        self.chat_input.delete("1.0", tk.END)
        self._append_chat("You", q, "user_label", "user_msg")
        self._append_chat("AI", "Thinking...", "ai_label", "thinking")
        threading.Thread(target=self._fetch_ai_response, args=(q,), daemon=True).start()

    def _quick_ask(self, prompt):
        self._append_chat("You", prompt, "user_label", "user_msg")
        self._append_chat("AI", "Thinking...", "ai_label", "thinking")
        threading.Thread(target=self._fetch_ai_response, args=(prompt,), daemon=True).start()

    def _fetch_ai_response(self, q):
        result = api_post("api/ask", {"question": q}, timeout=30)
        answer = result.get("answer", result.get("error", "No response"))
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
            start = f"1.0 + {idx} chars"
            end = f"1.0 + {idx + len('Thinking...')} chars"
            self.chat_display.delete(start, end)
            self.chat_display.insert(start, answer, "ai_msg")
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    # ─── Transcript ───────────────────────────────────────────────────────────
    def _toggle_transcription(self):
        if self.transcription_active:
            api_post("api/transcription/stop")
            self.transcription_active = False
            self.mic_btn.configure(text="🎙  Start Listening", bg=CYAN)
            self.live_dot.configure(fg=TEXT_MUTED)
            self.live_label.configure(text=" IDLE", fg=TEXT_MUTED)
            self._set_status("Transcription stopped", TEXT_MUTED)
        else:
            api_post("api/transcription/start")
            self.transcription_active = True
            self.mic_btn.configure(text="⏹  Stop Listening", bg=RED)
            self.live_dot.configure(fg=RED)
            self.live_label.configure(text=" LIVE", fg=GREEN)
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

    # ─── Actions ──────────────────────────────────────────────────────────────
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

    def _action_rephrase(self):
        text = self.rephrase_input.get("1.0", tk.END).strip()
        if not text:
            return
        self._set_ar("⏳ Rephrasing...")
        def run():
            result = api_post("api/rephrase", {"text": text}, timeout=20)
            self.root.after(0, self._set_ar, result.get("rephrased", result.get("error", "")))
        threading.Thread(target=run, daemon=True).start()

    def _run_action(self, endpoint, key):
        result = api_post(endpoint, timeout=30)
        self.root.after(0, self._set_ar, result.get(key, result.get("error", "No result")))

    def _set_ar(self, text):
        self.actions_result.configure(state=tk.NORMAL)
        self.actions_result.delete("1.0", tk.END)
        self.actions_result.insert("1.0", text)
        self.actions_result.configure(state=tk.DISABLED)

    # ─── Automation ───────────────────────────────────────────────────────────
    def _run_command(self, command, params):
        def run():
            try:
                r = requests.post(f"{BACKEND}/api/command",
                                  json={"command": command, "params": params}, timeout=10)
                data = r.json()
                color = GREEN if data.get("success", True) else RED
                self.root.after(0, self._toast, data.get("message", "Done"), color)
            except Exception as e:
                self.root.after(0, self._toast, f"Error: {e}", RED)
        threading.Thread(target=run, daemon=True).start()

    def _cmd_open_url(self):
        url = self.url_entry.get().strip()
        if url and url != "https://":
            self._run_command("open_url", {"url": url})

    def _cmd_google_search(self):
        q = self.google_entry.get().strip()
        if q and q != "Search...":
            self._run_command("search_google", {"query": q})

    def _cmd_discord_send(self):
        msg = self.discord_entry.get("1.0", tk.END).strip()
        if msg:
            self._run_command("discord_send", {"message": msg})
            self.discord_entry.delete("1.0", tk.END)

    # ─── Settings ─────────────────────────────────────────────────────────────
    def _open_settings(self):
        d = tk.Toplevel(self.root)
        d.title("Settings")
        d.configure(bg=BG_DARK)
        d.geometry("420x330")
        d.attributes("-topmost", True)
        d.grab_set()

        # Accent line
        tk.Frame(d, bg=ACCENT, height=3).pack(fill=tk.X)

        # Header
        hdr = tk.Frame(d, bg=BG_PANEL, pady=14)
        hdr.pack(fill=tk.X)
        if self._icon_small:
            tk.Label(hdr, image=self._icon_small, bg=BG_PANEL).pack(side=tk.LEFT, padx=14)
        tk.Label(hdr, text="Settings", fg=TEXT_PRIMARY, bg=BG_PANEL,
                 font=(FONT_BOLD, 13, "bold")).pack(side=tk.LEFT)
        tk.Frame(d, bg=BORDER, height=1).pack(fill=tk.X)

        body = tk.Frame(d, bg=BG_DARK)
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        tk.Label(body, text="🔑  Gemini API Key", fg=TEXT_PRIMARY, bg=BG_DARK,
                 font=(FONT, 11, "bold")).pack(anchor=tk.W)
        tk.Label(body, text="Get FREE key: aistudio.google.com → Get API Key",
                 fg=TEXT_SEC, bg=BG_DARK, font=(FONT, 9)).pack(anchor=tk.W, pady=(2, 8))

        e_border = tk.Frame(body, bg=BORDER_GLOW, padx=1, pady=1)
        e_border.pack(fill=tk.X)
        key_entry = tk.Entry(e_border, bg=BG_INPUT, fg=TEXT_PRIMARY,
                             font=(FONT, 10), relief=tk.FLAT, bd=0,
                             show="•", insertbackground=TEXT_PRIMARY)
        key_entry.pack(fill=tk.X, ipady=8, padx=4)
        key_entry.bind("<FocusIn>", lambda e: e_border.configure(bg=ACCENT_DARK))
        key_entry.bind("<FocusOut>", lambda e: e_border.configure(bg=BORDER_GLOW))

        sv = tk.BooleanVar()
        tk.Checkbutton(body, text="Show key", variable=sv,
                       command=lambda: key_entry.configure(show="" if sv.get() else "•"),
                       bg=BG_DARK, fg=TEXT_SEC, selectcolor=BG_INPUT,
                       font=(FONT, 8), activebackground=BG_DARK).pack(anchor=tk.W, pady=6)

        result_lbl = tk.Label(body, text="", fg=GREEN, bg=BG_DARK, font=(FONT, 8))
        result_lbl.pack()

        def save():
            key = key_entry.get().strip()
            if not key:
                result_lbl.configure(text="Please enter an API key", fg=RED)
                return
            res = api_post("api/key", {"api_key": key})
            if "error" in res:
                result_lbl.configure(text=f"Error: {res['error']}", fg=RED)
            else:
                result_lbl.configure(text="✅  API key saved!", fg=GREEN)
                self.api_key_configured = True
                self.api_warning.pack_forget()
                self._set_status("✅  AI ready", GREEN)
                # Auto-close settings dialog after short delay
                self.root.after(800, lambda: d.destroy())

        tk.Button(body, text="Save API Key", bg=ACCENT, fg="white",
                  font=(FONT_BOLD, 10, "bold"), relief=tk.FLAT, bd=0,
                  padx=20, pady=9, cursor="hand2", command=save).pack(pady=12)

    # ─── Stealth ──────────────────────────────────────────────────────────────
    def _apply_stealth(self):
        # Run off the UI thread so the window appears instantly
        hwnd = self.root.winfo_id()
        def _do():
            success = apply_stealth(hwnd)
            msg = ("🛡️  Stealth active", GREEN) if success else ("⚠️  Stealth requires Windows 10 v2004+", ORANGE)
            self.root.after(0, lambda: self._set_status(*msg))
        threading.Thread(target=_do, daemon=True).start()

    # ─── Backend ──────────────────────────────────────────────────────────────
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
        self._set_status("✅  Backend connected", GREEN)
        status = api_get("api/key/status")
        if status.get("configured"):
            self.api_key_configured = True
            self.api_warning.pack_forget()

    # ─── WebSocket ────────────────────────────────────────────────────────────
    def _connect_websocket(self):
        def run():
            while True:
                try:
                    ws = websocket.WebSocketApp(
                        WS_URL,
                        on_message=self._on_ws_message,
                        on_error=lambda ws, e: None,
                        on_close=lambda ws, c, m: None
                    )
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
                self.root.after(0, self._set_status,
                                f"📹 {msg.get('platform','')} · {msg.get('title','')}", ACCENT)
            elif t == "error":
                self.root.after(0, self._set_status, f"⚠️ {msg.get('text','')}", ORANGE)
            elif t == "action_result":
                color = GREEN if msg.get("success", True) else RED
                self.root.after(0, self._toast, msg.get("text", ""), color)
        except Exception:
            pass

    # ─── Toast ────────────────────────────────────────────────────────────────
    def _toast(self, message, color=None):
        color = color or GREEN
        t = tk.Toplevel(self.root)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        t.attributes("-alpha", 0.0)
        t.configure(bg=BG_CARD2)

        # Accent line on bottom of toast
        tk.Frame(t, bg=color, height=2).pack(fill=tk.X, side=tk.BOTTOM)

        tk.Label(t, text=message, fg=color, bg=BG_CARD2,
                 font=(FONT_BOLD, 9, "bold"), padx=20, pady=12).pack()

        self.root.update_idletasks()
        rx, ry = self.root.winfo_x(), self.root.winfo_y() + self.root.winfo_height() - 50
        t.geometry(f"+{rx}+{ry}")

        def fin(a=0.0):
            a = min(a + 0.1, 0.95)
            try: t.attributes("-alpha", a)
            except: return
            if a < 0.95: self.root.after(18, fin, a)
            else: self.root.after(2500, fout, 0.95)

        def fout(a=0.95):
            a = max(a - 0.1, 0.0)
            try: t.attributes("-alpha", a)
            except: return
            if a > 0: self.root.after(18, fout, a)
            else:
                try: t.destroy()
                except: pass
        fin()

    # ─── Visibility ───────────────────────────────────────────────────────────
    def _toggle_visibility(self, event=None):
        if self.root.state() == "withdrawn":
            self.root.deiconify()
        else:
            self.root.withdraw()

    def _on_close(self):
        self._pulse_running = False
        self.root.destroy()  # Close window immediately — no waiting
        # Fire cleanup in background so the user doesn't wait at all
        def _cleanup():
            try:
                if self.transcription_active:
                    requests.post(f"{BACKEND}/api/transcription/stop", timeout=1)
            except Exception:
                pass
            try:
                requests.post(f"{BACKEND}/api/shutdown", timeout=1)
            except Exception:
                pass
        threading.Thread(target=_cleanup, daemon=True).start()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    AIAssistantHUD().run()
