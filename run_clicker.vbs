Option Explicit
Dim objShell, fso, scriptPath, scriptDir, exePath, venvPythonw, cmd
Set objShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptPath = WScript.ScriptFullName
scriptDir = fso.GetParentFolderName(scriptPath)
exePath = scriptDir & "\RocoKingdom_Clicker.exe"
venvPythonw = scriptDir & "\.venv\Scripts\pythonw.exe"

If fso.FileExists(exePath) Then
    ' If bundled exe exists, request elevation and run it
    Dim objShellApp
    Set objShellApp = CreateObject("Shell.Application")
    objShellApp.ShellExecute exePath, "--gui", scriptDir, "runas", 1
ElseIf fso.FileExists(venvPythonw) Then
    Dim objShellApp2
    Set objShellApp2 = CreateObject("Shell.Application")
    objShellApp2.ShellExecute venvPythonw, "Clicker.py --gui", scriptDir, "runas", 1
Else
    ' Fallback to system pythonw (assumes on PATH) and request elevation
    Dim objShellApp3
    Set objShellApp3 = CreateObject("Shell.Application")
    objShellApp3.ShellExecute "pythonw.exe", "Clicker.py --gui", scriptDir, "runas", 1
End If

WScript.Quit
