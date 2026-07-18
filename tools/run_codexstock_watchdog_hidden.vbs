Option Explicit

Dim shell, fso, scriptDir, watchdog, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
watchdog = fso.BuildPath(scriptDir, "codexstock_watchdog.ps1")
command = "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File """ & watchdog & """"

' Window style 0 keeps the watchdog completely invisible; False does not block Task Scheduler.
shell.Run command, 0, False
