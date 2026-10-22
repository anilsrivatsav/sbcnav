#ifndef BuildDir
  #error BuildDir must point to the PyInstaller SBCNAVUpdater directory
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif
#define AppVersion "2.1.0"

[Setup]
AppId={{9E2CAB45-43B1-492E-82D4-D5C13A68BE32}
AppName=SBC NAV Updater
AppVersion={#AppVersion}
AppPublisher=SBC NAV
AppSupportURL=https://sbcnav-38t2.vercel.app/?view=mcdo
DefaultDirName={localappdata}\Programs\SBC NAV Updater
DefaultGroupName=SBC NAV
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableProgramGroupPage=yes
DisableDirPage=yes
WizardStyle=modern
SetupLogging=yes
OutputDir={#OutputDir}
OutputBaseFilename=SBC-NAV-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
CloseApplicationsFilter=SBCNAVUpdater.exe
RestartApplications=no
UninstallDisplayIcon={app}\SBCNAVUpdater.exe
CreateUninstallRegKey=not IsTestInstall
UsePreviousAppDir=not IsTestInstall
InfoBeforeFile=installer-note.txt

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: checkedonce; Check: Integrate
Name: startup; Description: "Keep the desktop connection ready when I sign in to Windows"; Flags: checkedonce; Check: Integrate

[Files]
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{src}\SBC NAV Connection.sbcnav"; DestDir: "{localappdata}\IREPS Earnings Updater\Web companion"; DestName: "pending.sbcnav"; Flags: external skipifsourcedoesntexist uninsneveruninstall; Check: Integrate

[Icons]
Name: "{autodesktop}\SBC NAV Updater"; Filename: "{app}\SBCNAVUpdater.exe"; Tasks: desktopicon; Check: Integrate
Name: "{group}\SBC NAV Updater"; Filename: "{app}\SBCNAVUpdater.exe"; Check: Integrate
Name: "{group}\Set up this PC"; Filename: "{app}\SBCNAVUpdater.exe"; Parameters: "--setup"; Check: Integrate
Name: "{group}\Quick start"; Filename: "{app}\_internal\QUICK START.html"; Check: Integrate
Name: "{userstartup}\SBC NAV Updater"; Filename: "{app}\SBCNAVUpdater.exe"; Parameters: "--background"; Tasks: startup; Check: Integrate

[Registry]
Root: HKCU; Subkey: "Software\Classes\sbcnav-updater"; ValueType: string; ValueData: "URL:SBC NAV Updater"; Flags: uninsdeletekey; Check: Integrate
Root: HKCU; Subkey: "Software\Classes\sbcnav-updater"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""; Check: Integrate
Root: HKCU; Subkey: "Software\Classes\sbcnav-updater\shell\open\command"; ValueType: string; ValueData: """{app}\SBCNAVUpdater.exe"" --background"; Check: Integrate

[Run]
Filename: "{app}\SBCNAVUpdater.exe"; Description: "Connect this PC and open SBC NAV"; Flags: postinstall nowait skipifsilent; Check: Integrate

[Code]
function IsTestInstall: Boolean;
begin
  Result := ExpandConstant('{param:TESTINSTALL|0}') = '1';
end;

function Integrate: Boolean;
begin
  Result := not IsTestInstall;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Request: Variant;
  Locator: Variant;
  Service: Variant;
  Processes: Variant;
  Status: String;
begin
  Result := '';
  if IsTestInstall or not FileExists(ExpandConstant('{app}\SBCNAVUpdater.exe')) then exit;
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Service := Locator.ConnectServer('', 'root\CIMV2');
    Processes := Service.ExecQuery('SELECT ProcessId FROM Win32_Process WHERE Name = ''SBCNAVUpdater.exe'' AND CommandLine LIKE ''%--serve%''');
    if Processes.Count = 0 then exit;
    Request := CreateOleObject('WinHttp.WinHttpRequest.5.1');
    Request.SetTimeouts(2000, 2000, 2000, 3000);
    Request.Open('GET', 'http://127.0.0.1:48722/status', False);
    Request.SetRequestHeader('Origin', 'https://sbcnav-38t2.vercel.app');
    Request.Send();
    Status := Request.ResponseText;
    if (Request.Status <> 200) or (Pos('"busy": false', Status) = 0) or (Pos('"deskflow_busy": false', Status) = 0) then
      Result := 'SBC NAV is working or cannot confirm its status. Finish the current update before installing a new version.';
  except
    { Restart Manager handles closed apps. An unreachable running helper needs review. }
    Result := 'Open SBC NAV and check that the desktop connection is idle before upgrading. If it will not respond, restart Windows and run setup before starting an update.';
  end;
end;
