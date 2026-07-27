"""
stealth.py — Makes the overlay window invisible to all screen capture APIs.

Uses Windows SetWindowDisplayAffinity with WDA_EXCLUDEFROMCAPTURE flag.
The window appears normally on the physical monitor but shows as BLACK
in all capture tools: OBS, Zoom share, Teams share, Google Meet, Discord, etc.

IMPORTANT: SetWindowDisplayAffinity must be applied to the TRUE Win32
top-level HWND (the one that owns the title bar / non-client area).
tkinter's winfo_id() returns the handle of an internal child frame, which
makes the call silently fail.  We resolve the real HWND with FindWindowW.
"""

import ctypes
import ctypes.wintypes
import sys
import time

# Windows API constants
WDA_NONE             = 0x00000000
WDA_MONITOR          = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000011  # Windows 10 Build 19041+

# GA_ROOT — walk up the parent chain to the top-level window
GA_ROOT = 2

# Extended window style constants for taskbar hiding
GWL_EXSTYLE      = -20
WS_EX_APPWINDOW  = 0x00040000   # forces taskbar button
WS_EX_TOOLWINDOW = 0x00000080   # hides from taskbar & Alt+Tab

user32 = ctypes.windll.user32
user32.GetWindowLongW.restype  = ctypes.c_long
user32.SetWindowLongW.restype  = ctypes.c_long


def _get_real_hwnd(title: str = "Aura AI") -> int:
    """
    Find the actual Win32 top-level HWND for our window.

    Strategy 1 — FindWindowW by title (most reliable for tkinter).
    Strategy 2 — EnumWindows scan as fallback.
    Returns 0 if not found.
    """
    # Strategy 1: direct title lookup
    hwnd = user32.FindWindowW(None, title)
    if hwnd:
        return hwnd

    # Strategy 2: enumerate all top-level windows, match by title substring
    found = ctypes.c_int(0)

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    def _cb(h, _):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, buf, 256)
        if title in buf.value:
            found.value = h
            return False   # stop enumeration
        return True

    user32.EnumWindows(_cb, 0)
    return found.value


def apply_stealth(hwnd_hint: int = 0, title: str = "Aura AI") -> bool:
    """
    Exclude the window from all screen-capture APIs.

    Args:
        hwnd_hint : The HWND from winfo_id() — used only if FindWindowW fails.
        title     : Window title used to locate the real top-level HWND.

    Returns:
        True if successfully applied.
    """
    if sys.platform != "win32":
        return False

    # Always prefer the real top-level HWND
    hwnd = _get_real_hwnd(title)
    if not hwnd and hwnd_hint:
        # Last resort: walk up to the ancestor from the child handle
        hwnd = user32.GetAncestor(hwnd_hint, GA_ROOT) or hwnd_hint

    if not hwnd:
        return False

    try:
        result = user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        if result:
            return True
        # Fallback for older Windows (hides from BitBlt-based captures)
        result2 = user32.SetWindowDisplayAffinity(hwnd, WDA_MONITOR)
        return bool(result2)
    except Exception:
        return False


def remove_stealth(hwnd_hint: int = 0, title: str = "Aura AI") -> bool:
    """
    Remove screen-capture exclusion — window becomes visible to screen share.
    """
    if sys.platform != "win32":
        return False

    hwnd = _get_real_hwnd(title)
    if not hwnd and hwnd_hint:
        hwnd = user32.GetAncestor(hwnd_hint, GA_ROOT) or hwnd_hint

    if not hwnd:
        return False

    try:
        return bool(user32.SetWindowDisplayAffinity(hwnd, WDA_NONE))
    except Exception:
        return False


def get_window_hwnd(tk_window) -> int:
    """Return the child HWND from tkinter (used as a hint only)."""
    return tk_window.winfo_id()


def set_always_on_top(hwnd: int):
    """Make window stay above all other windows."""
    HWND_TOPMOST = -1
    SWP_NOMOVE    = 0x0002
    SWP_NOSIZE    = 0x0001
    SWP_NOACTIVATE = 0x0010
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def get_screen_size():
    """Return (width, height) of the primary monitor."""
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def _apply_toolwindow_style(hwnd: int) -> bool:
    """
    Core helper: apply WS_EX_TOOLWINDOW (hides taskbar button) to a given HWND.
    The HWND must be the real Win32 top-level handle.
    """
    try:
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex = (ex & ~WS_EX_APPWINDOW) | WS_EX_TOOLWINDOW
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)

        # Tell the Shell to refresh the taskbar state immediately
        SWP_NOMOVE       = 0x0002
        SWP_NOSIZE       = 0x0001
        SWP_NOACTIVATE   = 0x0010
        SWP_FRAMECHANGED = 0x0020
        HWND_TOPMOST     = -1
        user32.SetWindowPos(
            hwnd, HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED
        )
        return True
    except Exception:
        return False


def hide_from_taskbar_early(child_hwnd: int) -> bool:
    """
    Hide the window from the taskbar BEFORE it is shown (no FindWindowW needed).

    Call this while the window is still withdrawn, passing tkinter's winfo_id().
    We walk up to the real top-level HWND with GetAncestor(GA_ROOT) so
    SetWindowLongW targets the correct handle.

    This eliminates the 1-second taskbar-flash on startup.
    """
    if sys.platform != "win32" or not child_hwnd:
        return False

    # Walk from the tkinter child frame up to the actual top-level window
    real_hwnd = user32.GetAncestor(child_hwnd, GA_ROOT)
    if not real_hwnd:
        real_hwnd = child_hwnd  # last resort

    return _apply_toolwindow_style(real_hwnd)


def hide_from_taskbar(title: str = "Aura AI") -> bool:
    """
    Hide the window from the taskbar by locating it via its title.
    Use this AFTER the window is visible (FindWindowW works on visible windows).

    Combines WS_EX_TOOLWINDOW style-change with a Shell refresh.
    """
    if sys.platform != "win32":
        return False

    hwnd = _get_real_hwnd(title)
    if not hwnd:
        return False

    return _apply_toolwindow_style(hwnd)
