; CorePulse - instalador por usuario, version inyectada por build_installer.bat
#ifndef MyAppVersion
  #error MyAppVersion requerida: ejecutar build_installer.bat
#endif
#ifndef MyVersionInfo
  #error MyVersionInfo requerida: ejecutar build_installer.bat
#endif
#define MyAppName "CorePulse"
#define MyAppPublisher "CorePulse"
#define MyAppExeName "CorePulse.exe"

[Setup]
AppId={{C2F20D38-5AD8-4D04-A4CE-024200000001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\CorePulse
DefaultGroupName=CorePulse
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=CorePulse_Setup_V{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\assets\app_icon.ico
UninstallDisplayIcon={app}\CorePulse.exe
VersionInfoVersion={#MyVersionInfo}
VersionInfoProductName=CorePulse
VersionInfoProductVersion={#MyAppVersion}
CloseApplications=yes
RestartApplications=no

[Files]
Source: "..\dist\CorePulse\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\CorePulse"; Filename: "{app}\CorePulse.exe"
Name: "{autodesktop}\CorePulse"; Filename: "{app}\CorePulse.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Run]
Filename: "{app}\CorePulse.exe"; Description: "Abrir CorePulse"; Flags: nowait postinstall skipifsilent
