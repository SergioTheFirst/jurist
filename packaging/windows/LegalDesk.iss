#define MyAppName "LegalDesk"
#ifndef MyAppVersion
  #define MyAppVersion "4.0.0"
#endif
#define MyAppPublisher "LegalDesk"
#define MyAppExeName "LegalDesk.exe"

[Setup]
AppId={{8F7A29DE-9A0A-4D8A-92E2-EC8D0E4F2F35}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\..\dist-installer
OutputBaseFilename=LegalDesk-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\..\dist\LegalDesk\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\LegalDesk"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\LegalDesk"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch LegalDesk"; Flags: nowait postinstall skipifsilent
