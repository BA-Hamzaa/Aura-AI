"""
stealth.py — Makes the overlay window invisible to all screen capture APIs.

Uses Windows SetWindowDisplayAffinity with WDA_EXCLUDEFROMCAPTURE flag.
The window appears normally on the physical monitor but shows as BLACK
in all capture tools: OBS, Zoom share, Teams share, Google Meet, Discord, etc.

This is the same mechanism used by:
- NVIDIA ShadowPlay overlay
- Xbox Game Bar
- Password managers auto-fill overlays
"""

import ctypes
import ctypes.wintypes
import sys

# Windows API constants
WDA_NONE = 0x00000000
WDA_MONITOR = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000011  # Windows 10 2004+ (Build 19041+)

user32 = ctypes.windll.user32


def apply_stealth(hwnd: int) -> bool:
    """
    Apply screen-capture exclusion to a window handle.
    
    Args:
        hwnd: The Windows HWND handle of the window to hide from capture.
    
    Returns:
        True if successful, False otherwise.
    """
    if sys.platform != "win32":
        print("[Stealth] Not on Windows — skipping screen capture exclusion")
        return False

    try:
        result = user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        if result:
            print("[Stealth] [OK] Window excluded from screen capture")
            return True
        else:
            error = ctypes.get_last_error()
            # Fallback to WDA_MONITOR for older Windows
            result2 = user32.SetWindowDisplayAffinity(hwnd, WDA_MONITOR)
            if result2:
                print("[Stealth] [OK] Window set to monitor-only (WDA_MONITOR fallback)")
                return True
            print(f"[Stealth] [WARN] Could not apply stealth (Error: {error}). "
                  "Requires Windows 10 version 2004 or newer.")
            return False
    except Exception as e:
        print(f"[Stealth] Error: {e}")
        return False


def get_window_hwnd(tk_window) -> int:
    """Extract the Win32 HWND from a tkinter window."""
    return tk_window.winfo_id()


def set_always_on_top(hwnd: int):
    """Make window stay above all other windows."""
    HWND_TOPMOST = -1
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def get_screen_size():
    """Return (width, height) of the primary monitor."""
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
