import tkinter as tk
import time
import sys

from overlay.stealth import apply_stealth

root = tk.Tk()
root.title("Aura AI Test")
root.geometry("400x400")
root.withdraw()
root.update_idletasks()

print("Applying stealth...")
res = apply_stealth(title="Aura AI Test")
print("res:", res)

print("Deiconifying...")
root.deiconify()
root.update_idletasks()

print("Visible now.")
tk.Label(root, text="TESTING STEALTH", font=("Arial", 20)).pack(pady=50)

root.after(2000, root.destroy)
root.mainloop()
