' Start.vbs - ComfyUI XMP Tagger
' Runs Start.bat completely hidden (no console window visible to the user).
' The app will appear directly without any intermediate console flash.

Dim objShell
Set objShell = CreateObject("WScript.Shell")

' Build the path to Start.bat relative to this script's location
Dim scriptDir
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

Dim batPath
batPath = scriptDir & "\Start.bat"

' 0 = hidden window, False = don't wait for it to finish
objShell.Run "cmd /c """ & batPath & """", 0, False

Set objShell = Nothing
