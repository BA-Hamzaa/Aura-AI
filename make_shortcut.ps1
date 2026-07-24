$desktop = [Environment]::GetFolderPath('Desktop')
$WshShell = New-Object -ComObject WScript.Shell
$lnk = $desktop + '\Aura AI.lnk'
$Shortcut = $WshShell.CreateShortcut($lnk)
$Shortcut.TargetPath = 'C:\Users\Hamza\OneDrive\Desktop\project ai\Aura AI.vbs'
$Shortcut.IconLocation = 'C:\Users\Hamza\OneDrive\Desktop\project ai\overlay\brain_icon.ico'
$Shortcut.Description = 'Aura AI'
$Shortcut.WorkingDirectory = 'C:\Users\Hamza\OneDrive\Desktop\project ai'
$Shortcut.Save()
Write-Host 'Shortcut created successfully'
