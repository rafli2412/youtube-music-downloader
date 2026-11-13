#ifndef AppVersion
  #error AppVersion must be supplied by the build script
#endif
#ifndef SourceDir
  #error SourceDir must be supplied by the build script
#endif
#ifndef PrerequisiteDir
  #error PrerequisiteDir must be supplied by the build script
#endif
#ifndef OutputDir
  #error OutputDir must be supplied by the build script
#endif
#ifndef WebViewSHA256
  #error WebViewSHA256 must be supplied by the build script
#endif

[Setup]
AppId={{BB27ABBE-3AC2-4DBA-9DED-120D682B93D6}
AppName=YouTube Music Downloader
AppVersion={#AppVersion}
AppPublisher=rafli2412
DefaultDirName={localappdata}\Programs\YouTube Music Downloader
DefaultGroupName=YouTube Music Downloader
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.19041
OutputDir={#OutputDir}
OutputBaseFilename=youtube-music-downloader-{#AppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
ChangesEnvironment=yes
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\ytmp3-desktop.exe
SetupLogging=yes
SetupIconFile=..\icons\app.ico
InfoBeforeFile=INSTALL.txt

[Tasks]
Name: "addtopath"; Description: "Make ytmp3 available in new terminal windows"; Flags: checkedonce
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PrerequisiteDir}\MicrosoftEdgeWebview2Setup.exe"; Flags: dontcopy

[Icons]
Name: "{userprograms}\YouTube Music Downloader"; Filename: "{app}\ytmp3-desktop.exe"
Name: "{userdesktop}\YouTube Music Downloader"; Filename: "{app}\ytmp3-desktop.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ytmp3-desktop.exe"; Description: "Open YouTube Music Downloader"; Flags: nowait postinstall skipifsilent

[Code]
const
  EdgeKey = 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  OwnerKey = 'Software\Rafli2412\YouTubeMusicDownloader\Installer';

function RuntimeInRoot(Root: Integer): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(Root, EdgeKey, 'pv', Version) and
    (StrToIntDef(Copy(Version, 1, Pos('.', Version) - 1), 0) > 0);
end;

function HasWebView2: Boolean;
begin
  Result := RuntimeInRoot(HKLM32) or RuntimeInRoot(HKCU32) or
    RuntimeInRoot(HKLM64) or RuntimeInRoot(HKCU64);
end;

function HasDotNet: Boolean;
var
  Release: Cardinal;
begin
  Result := (RegQueryDWordValue(HKLM32, 'Software\Microsoft\NET Framework Setup\NDP\v4\Full', 'Release', Release) and (Release >= 528040)) or
    (RegQueryDWordValue(HKLM64, 'Software\Microsoft\NET Framework Setup\NDP\v4\Full', 'Release', Release) and (Release >= 528040));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Bootstrapper: String;
  ExitCode, Attempt: Integer;
begin
  Result := '';
  if not HasDotNet then begin
    Result := 'Microsoft .NET Framework 4.8 or newer is required. Install it through Windows Update, then run Setup again.';
    Exit;
  end;
  if WizardIsTaskSelected('addtopath') and (Pos(';', ExpandConstant('{app}')) > 0) then begin
    Result := 'Choose an install folder without semicolons, or uncheck the terminal PATH option.';
    Exit;
  end;
  if HasWebView2 then Exit;
  ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
  Bootstrapper := ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe');
  if CompareText(GetSHA256OfFile(Bootstrapper), '{#WebViewSHA256}') <> 0 then begin
    Result := 'The WebView2 installer failed its integrity check. Download a fresh app installer.';
    Exit;
  end;
  WizardForm.StatusLabel.Caption := 'Installing Microsoft WebView2. Internet access is required...';
  if not Exec(Bootstrapper, '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then begin
    Result := 'Could not start Microsoft WebView2 setup. Check your connection and run this installer again.';
    Exit;
  end;
  if (ExitCode = 3010) or (ExitCode = 1641) then begin
    NeedsRestart := True;
    Result := 'Restart Windows to finish installing WebView2, then run this app installer again.';
    Exit;
  end;
  for Attempt := 1 to 20 do begin
    if HasWebView2 then Exit;
    Sleep(500);
  end;
  Result := 'Microsoft WebView2 could not be installed (code ' + IntToStr(ExitCode) + '). Check your connection or contact your administrator, then retry. No app files have been installed.';
end;

function NormalPath(Value: String): String;
begin
  Result := Trim(Value);
  if (Length(Result) > 1) and (Result[1] = '"') and (Result[Length(Result)] = '"') then
    Result := Copy(Result, 2, Length(Result) - 2);
  while (Length(Result) > 3) and (Result[Length(Result)] = '\') do
    Delete(Result, Length(Result), 1);
end;

function RemoveEntry(Value, Entry: String; var Found: Boolean): String;
var
  Token: String;
  Separator: Integer;
  First: Boolean;
begin
  Result := '';
  Found := False;
  First := True;
  repeat
    Separator := Pos(';', Value);
    if Separator = 0 then Token := Value
    else begin
      Token := Copy(Value, 1, Separator - 1);
      Delete(Value, 1, Separator);
    end;
    if CompareText(NormalPath(Token), NormalPath(Entry)) = 0 then Found := True
    else begin
      if not First then Result := Result + ';';
      Result := Result + Token;
      First := False;
    end;
  until Separator = 0;
end;

procedure RemoveOwnedPath;
var
  Entry, Value, Updated: String;
  Found: Boolean;
begin
  if not RegQueryStringValue(HKCU, OwnerKey, 'PathEntry', Entry) then Exit;
  if RegQueryStringValue(HKCU, 'Environment', 'Path', Value) then begin
    Updated := RemoveEntry(Value, Entry, Found);
    if Found and not RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Updated) then
      RaiseException('Could not remove the app terminal path. Your other PATH entries were kept.');
  end;
  RegDeleteValue(HKCU, OwnerKey, 'PathEntry');
  RegDeleteKeyIfEmpty(HKCU, OwnerKey);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Value, Unused, ExistingOwned: String;
  Found: Boolean;
begin
  if CurStep <> ssPostInstall then Exit;
  if not WizardIsTaskSelected('addtopath') then begin
    RemoveOwnedPath;
    Exit;
  end;
  if RegQueryStringValue(HKCU, OwnerKey, 'PathEntry', ExistingOwned) and
    (CompareText(NormalPath(ExistingOwned), NormalPath(ExpandConstant('{app}'))) <> 0) then
    RemoveOwnedPath;
  RegQueryStringValue(HKCU, 'Environment', 'Path', Value);
  Unused := RemoveEntry(Value, ExpandConstant('{app}'), Found);
  if Found then Exit;
  if (Value <> '') and (Copy(Value, Length(Value), 1) <> ';') then Value := Value + ';';
  if not RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Value + ExpandConstant('{app}')) then
    RaiseException('Could not add the terminal command to your user PATH.');
  if not RegWriteStringValue(HKCU, OwnerKey, 'PathEntry', ExpandConstant('{app}')) then begin
    RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Value);
    RaiseException('Could not record the terminal PATH setting.');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then RemoveOwnedPath;
end;
