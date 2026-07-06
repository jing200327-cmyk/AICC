' GLM Proxy — silent background launcher for Windows
' Double-click this file to start the proxy without a visible console window.
' To stop: open Task Manager and end "python.exe" processes running server.py

Set objShell = CreateObject("WScript.Shell")
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' Run the batch file hidden
objShell.Run "cmd /c cd /d """ & scriptDir & """ && start.bat", 0, False

WScript.Quit 0
