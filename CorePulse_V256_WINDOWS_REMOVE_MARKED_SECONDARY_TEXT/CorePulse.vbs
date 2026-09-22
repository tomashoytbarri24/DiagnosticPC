Option Explicit
Dim fso, shell, root, launcher, localVenv, runtimeRoot, folder, candidate, chosen, newestDate
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)
launcher = fso.BuildPath(root, "corepulse_launcher.py")

If Not fso.FileExists(launcher) Then
    MsgBox "No se encontró corepulse_launcher.py en la carpeta de CorePulse.", vbCritical, "CorePulse"
    WScript.Quit 1
End If

shell.CurrentDirectory = root
chosen = ""

' 1) Entorno local del proyecto, si el desarrollador ya lo creó.
localVenv = fso.BuildPath(root, ".venv\Scripts\pythonw.exe")
If fso.FileExists(localVenv) Then
    chosen = localVenv
End If

' 2) Runtime existente de CorePulse, si ya fue preparado anteriormente en este PC.
If chosen = "" Then
    runtimeRoot = shell.ExpandEnvironmentStrings("%USERPROFILE%") & "\.corepulse\runtime"
    If fso.FolderExists(runtimeRoot) Then
        newestDate = #1/1/1970#
        For Each folder In fso.GetFolder(runtimeRoot).SubFolders
            candidate = fso.BuildPath(folder.Path, "Scripts\pythonw.exe")
            If fso.FileExists(candidate) Then
                If folder.DateLastModified >= newestDate Then
                    newestDate = folder.DateLastModified
                    chosen = candidate
                End If
            End If
        Next
    End If
End If

If chosen <> "" Then
    shell.Run """" & chosen & """ """ & launcher & """", 0, False
    WScript.Quit 0
End If

' 3) Fallback a un Python ya instalado/configurado. No instala ni repara nada.
On Error Resume Next
Err.Clear
shell.Run "pyw.exe -3.12 """ & launcher & """", 0, False
If Err.Number = 0 Then WScript.Quit 0

Err.Clear
shell.Run "pythonw.exe """ & launcher & """", 0, False
If Err.Number = 0 Then WScript.Quit 0
On Error GoTo 0

MsgBox "CorePulse no encontró un intérprete Python ya preparado para ejecutar el proyecto fuente.", vbCritical, "CorePulse"
WScript.Quit 2
