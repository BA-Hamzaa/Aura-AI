"""
Quick test — opens a small window and applies stealth immediately.
Share your screen in Discord, Teams, etc. and verify it's invisible.
Press Q to quit.
"""
import tkinter as tk
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "overlay"))
from stealth import apply_stealth, remove_stealth, _get_real_hwnd

root = tk.Tk()
root.title("Aura AI")
root.geometry("400x200+100+100")
root.configure(bg="#0b0e18")

lbl = tk.Label(root, text="🛡  STEALTH TEST\nShare this screen — can your friend see this?",
               fg="white", bg="#0b0e18", font=("Segoe UI", 14, "bold"))
lbl.pack(expand=True)

status = tk.Label(root, text="Applying stealth...", fg="#00e5c0", bg="#0b0e18", font=("Segoe UI", 10))
status.pack(pady=10)

def after_show():
    hwnd = _get_real_hwnd("Aura AI")
    print(f"[test] Real HWND found: {hwnd}")
    ok = apply_stealth(title="Aura AI")
    if ok:
        status.config(text=f"✅  Stealth ON — HWND {hwnd}\nYou see this; your friend should NOT.", fg="#00e5c0")
    else:
        status.config(text=f"❌  Stealth FAILED — HWND {hwnd}", fg="#ff5f5f")

root.after(600, after_show)
root.mainloop()
