Option Explicit
Dim objShell, objShellApp, fso, scriptPath, scriptDir
Dim exePath, venvPythonw, installerPath, dllPath
Dim msg, launchOK

Set objShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptPath = WScript.ScriptFullName
scriptDir = fso.GetParentFolderName(scriptPath)

exePath = scriptDir & "\RocoKingdom_Clicker.exe"
venvPythonw = scriptDir & "\.venv\Scripts\pythonw.exe"
installerPath = scriptDir & "\driver_installer\install-interception.exe"
dllPath = scriptDir & "\interception.dll"

If Not fso.FileExists(installerPath) Then
    Dim fallbackInstaller
    fallbackInstaller = scriptDir & "\third\Interception\command line installer\install-interception.exe"
    If fso.FileExists(fallbackInstaller) Then installerPath = fallbackInstaller
End If
If Not fso.FileExists(dllPath) Then
    Dim fallbackDll
    fallbackDll = scriptDir & "\third\Interception\library\x64\interception.dll"
    If fso.FileExists(fallbackDll) Then dllPath = fallbackDll
End If

If Not fso.FileExists(dllPath) Then
    msg = "interception.dll not found." & vbCrLf & _
          "Please ensure the DLL is in the program directory." & vbCrLf & vbCrLf & _
          "Searched: " & vbCrLf & scriptDir & "\interception.dll"
    objShell.Popup msg, 0, "Missing DLL - RocoKingdom Clicker", 16
    WScript.Quit 1
End If

If Not fso.FileExists(installerPath) Then
    msg = "Driver installer not found (driver_installer\install-interception.exe)." & vbCrLf & _
          "The program will still try to start, but may show another prompt if driver is not installed."
    objShell.Popup msg, 0, "Notice - RocoKingdom Clicker", 48
End If

Set objShellApp = CreateObject("Shell.Application")

launchOK = False

If fso.FileExists(exePath) Then
    objShellApp.ShellExecute exePath, "--gui", scriptDir, "runas", 1
    launchOK = True
ElseIf fso.FileExists(venvPythonw) Then
    objShellApp.ShellExecute venvPythonw, "Clicker.py --gui", scriptDir, "runas", 1
    launchOK = True
Else
    objShellApp.ShellExecute "pythonw.exe", "Clicker.py --gui", scriptDir, "runas", 1
    launchOK = True
End If

If Not launchOK Then
    objShell.Popup "Failed to launch the program. Please check Python or redownload.", 0, "Launch Failed - RocoKingdom Clicker", 16
    WScript.Quit 2
End If
