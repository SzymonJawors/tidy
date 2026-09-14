Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("Wscript.Shell")
sh.CurrentDirectory = folder

exe = folder & "\Tidy.exe"
If Not fso.FileExists(exe) Then exe = folder & "\dist\Tidy.exe"
If Not fso.FileExists(exe) Then exe = folder & "\Porzadek.exe"
If Not fso.FileExists(exe) Then exe = folder & "\dist\Porzadek.exe"

If fso.FileExists(exe) Then
  sh.Run """" & exe & """", 1, False
  WScript.Quit
End If

pythonw = "pythonw.exe"
sh.Run pythonw & " """ & folder & "\app.py""", 0, False
