; Inno Setup script for FocusLock on Windows.
; Build after PyInstaller, from the repo root:
;   ISCC.exe /DAppVersion=1.2.3 packaging\windows\installer.iss
; FocusLock must live in Program Files: its SYSTEM tasks run FocusLock.exe,
; so it has to be somewhere ordinary users can't change (focuslock_win
; refuses to start a lock from anywhere else). Hence no folder choice.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F1C2B7E-4D1A-4C55-9A3E-2B8E5F0C7D41}
AppName=FocusLock
AppVersion={#AppVersion}
AppPublisher=FocusLock
AppPublisherURL=https://github.com/hackerman-x/FocusLock
DefaultDirName={autopf}\FocusLock
DisableDirPage=yes
DefaultGroupName=FocusLock
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=FocusLock-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\FocusLock.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\..\dist\FocusLock\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\FocusLock"; Filename: "{app}\FocusLock.exe"
Name: "{autodesktop}\FocusLock"; Filename: "{app}\FocusLock.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FocusLock.exe"; Description: "Open FocusLock"; Flags: nowait postinstall skipifsilent

[Code]
function LockActive(): Boolean;
begin
  Result := FileExists(ExpandConstant('{commonappdata}\FocusLock\unlock_at'));
end;

// Updating or removing FocusLock mid-lock would pull the program out from
// under the guard and unlock tasks, so both wait until the lock ends.
function InitializeSetup(): Boolean;
begin
  Result := not LockActive();
  if not Result then
    SuppressibleMsgBox('A FocusLock lock is active. Update FocusLock after it ends.', mbError, MB_OK, IDOK);
end;

function InitializeUninstall(): Boolean;
begin
  Result := not LockActive();
  if not Result then
    MsgBox('A FocusLock lock is active. FocusLock can be removed after it ends.', mbError, MB_OK);
end;
