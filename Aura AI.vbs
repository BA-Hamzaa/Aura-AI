Set WshShell = CreateObject("WScript.Shell")
base = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))

' Launch backend silently (pythonw = no console)
WshShell.Run "pythonw """ & base & "backend\main.py""", 0, False

' Give the backend ~1.5 s to start before opening the HUD
WScript.Sleep 1500

' Launch overlay silently (pythonw = no console)
WshShell.Run "pythonw """ & base & "overlay\hud.py""", 0, False

Set WshShell = Nothing
