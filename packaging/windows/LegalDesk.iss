#define MyAppName "LegalDesk"
#ifndef MyAppVersion
  #define MyAppVersion "4.0.0"
#endif
#define MyAppPublisher "LegalDesk"
#define MyAppExeName "LegalDesk.exe"
#define MyAppStopExeName "LegalDesk-Stop.exe"

[Setup]
AppId={{8F7A29DE-9A0A-4D8A-92E2-EC8D0E4F2F35}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\..\dist-installer
OutputBaseFilename=LegalDesk-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Ярлыки:"; Flags: unchecked
Name: "autorun"; Description: "Запускать LegalDesk автоматически при входе в систему"; GroupDescription: "Автозапуск:"; Flags: unchecked

[Files]
Source: "..\..\dist\LegalDesk\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\LegalDesk"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Остановить LegalDesk"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--stop"; WorkingDir: "{app}"
Name: "{autodesktop}\LegalDesk"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "LegalDesk"; ValueData: """{app}\{#MyAppExeName}"" --no-browser"; Tasks: autorun

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить LegalDesk"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--stop"; Flags: runhidden; RunOnceId: "StopLegalDeskServer"
