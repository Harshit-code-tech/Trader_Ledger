; ============================================================
; Trader Ledger - Inno Setup Installer Script
; ============================================================
; This is an ISS file (Inno Setup Script)
; ISS = Simple scripting language for creating Windows installers
; Inno Setup reads this file and creates: TraderLedger_Setup.exe
;
; What this does:
; - Packages your .exe into a professional installer
; - Creates desktop shortcuts
; - Adds to Start Menu
; - Handles installation/uninstallation
; - Like how Chrome, VLC, etc. are installed
; ============================================================

; Variables (like constants in programming)
#define MyAppName "Trader Ledger"
#define MyAppVersion "1.4.3"
#define MyAppPublisher "Baba's Trading App"
#define MyAppExeName "TraderLedger.exe"

[Setup]
; AppId = Unique identifier for Windows (like a serial number)
; This GUID tells Windows: "This is Trader Ledger, not some other app"
; Generated randomly - keep this same for updates
AppId={{F7E8D9C0-B1A2-4563-8970-1A2B3C4D5E6F}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=TraderLedger_Setup_v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=lowest

; Language for installer (English)
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; Ask user if they want desktop shortcut (checkbox during install)
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Clean up the old _internal folder so unused libraries from previous versions are deleted
Type: filesandordirs; Name: "{app}\_internal"

; What files to copy to user's computer
[Files]
Source: "dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "QUICKSTART.md"; DestDir: "{app}"; Flags: ignoreversion

; Create folders in user's AppData (for database, exports, backups)
; {userappdata} = C:\Users\[Name]\AppData\Roaming\
; This is where user data lives (survives updates!)
[Dirs]
Name: "{userappdata}\TraderLedger"; Permissions: users-full
Name: "{userappdata}\TraderLedger\data"; Permissions: users-full
Name: "{userappdata}\TraderLedger\data\exports"; Permissions: users-full
Name: "{userappdata}\TraderLedger\data\backups"; Permissions: users-full
Name: "{userappdata}\TraderLedger\logs"; Permissions: users-full

; Create shortcuts (desktop, start menu)
[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Quick Start Guide"; Filename: "{app}\QUICKSTART.md"
Name: "{group}\Sample CSV Format"; Filename: "{userappdata}\TraderLedger\data\sample_import.csv"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Flags: nowait postinstall skipifsilent; Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"

; Custom code (written in Pascal language)
; Runs during installation to do special tasks
[Code]
procedure InitializeWizard();
begin
  // Runs when installer window opens
end;

function InitializeSetup(): Boolean;
begin
  // Runs before installation starts
  Result := True;  // True = continue installation
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  SampleCSV: string;
begin
  // Runs after installation completes
  if CurStep = ssPostInstall then
  begin
    // Create sample CSV template for Baba to use
    SampleCSV := ExpandConstant('{userappdata}\TraderLedger\data\sample_import.csv');
    if not FileExists(SampleCSV) then
    begin
      SaveStringToFile(SampleCSV, 'Date,Stock,Type,Qty,Price,Brokerage,Notes' + #13#10, False);
    end;
  end;
end;
