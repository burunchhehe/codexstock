Option Explicit

Dim shell, fso, scriptDir, runner, powershell, command, exitCode
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
runner = fso.BuildPath(scriptDir, "run_internal_developer.ps1")
powershell = shell.ExpandEnvironmentStrings("%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe")
If Not fso.FileExists(runner) Or Not fso.FileExists(powershell) Then
    WScript.Quit 3
End If
command = """" & powershell & """ -NoProfile -NonInteractive -ExecutionPolicy Bypass -File """ & runner & """"

' Waiting keeps Task Scheduler's IgnoreNew policy effective for the full cycle.
exitCode = shell.Run(command, 0, True)
WScript.Quit exitCode
