#define MyAppName       "LDOCE5 Viewer"
#define MyAppVersion    "2013.03.24"
#define MyAppPublisher  "hakidame.net"
#define MyAppURL        "http://hakidame.net/ldoce5viewer/"
#define MyAppExeName    "ldoce5viewer.exe"


[Setup]
AppId={{69AF89EB-727E-4F9E-ADCA-87102CBAC142}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={pf32}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=wininst
OutputBaseFilename=ldoce5viewer-setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\ldoce5viewer.exe


[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"


[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags:
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 0,6.1


[Files]
Source: "exedist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "msvcx90\*"; DestDir: "{app}\"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "msvcx90\*"; DestDir: "{app}\imageformats"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "msvcx90\*"; DestDir: "{app}\phonon_backend"; Flags: ignoreversion recursesubdirs createallsubdirs


[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon


[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent


[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\LDOCE5Viewer\*";
Type: dirifempty; Name: "{userappdata}\LDOCE5Viewer";
Type: filesandordirs; Name: "{localappdata}\LDOCE5Viewer\*";
Type: dirifempty; Name: "{localappdata}\LDOCE5Viewer";

