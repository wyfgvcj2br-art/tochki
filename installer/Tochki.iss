; Windows installation payload contains no user data. Keep AppId stable across upgrades.
#ifndef AppVersion
  #define AppVersion "2.6.0"
#endif
#ifndef Payload
  #define Payload "..\dist\installed\Точки"
#endif
#ifndef OutputPath
  #define OutputPath "..\dist"
#endif

[Setup]
AppId={{CB821F4C-9D80-4F96-9C9F-75F389817D98}
AppName=ТОЧКИ
AppVersion={#AppVersion}
AppVerName=ТОЧКИ {#AppVersion}
AppPublisher=Saudade_meow
AppPublisherURL=https://github.com/wyfgvcj2br-art/tochki
AppSupportURL=https://github.com/wyfgvcj2br-art/tochki/issues
AppUpdatesURL=https://github.com/wyfgvcj2br-art/tochki/releases
DefaultDirName={autopf}\Tochki
DefaultGroupName=Точки
DisableProgramGroupPage=yes
DisableDirPage=no
UsePreviousAppDir=yes
UsePreviousTasks=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputPath}
OutputBaseFilename=Tochki-Setup-x64
SetupIconFile=..\app\Точки.ico
UninstallDisplayIcon={app}\Точки.exe
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany=Saudade_meow
VersionInfoDescription=Установка приложения ТОЧКИ
VersionInfoProductName=ТОЧКИ
VersionInfoProductVersion={#AppVersion}
WizardStyle=modern
#ifdef BaselineTest
Compression=zip
SolidCompression=no
#else
Compression=lzma2
SolidCompression=yes
#endif
DiskSpanning=no
CloseApplications=yes
RestartApplications=no
Uninstallable=yes
UninstallDisplayName=ТОЧКИ
LicenseFile=..\licenses\WEBVIEW2-LICENSE.txt
ChangesEnvironment=no
ChangesAssociations=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"; Flags: unchecked

[Files]
Source: "{#Payload}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\WebView2"

[Icons]
Name: "{commonprograms}\Точки\Точки"; Filename: "{app}\Точки.exe"; WorkingDir: "{app}"; AppUserModelID: "SaudadeMeow.Tochki"
Name: "{commondesktop}\Точки"; Filename: "{app}\Точки.exe"; WorkingDir: "{app}"; Tasks: desktopicon; AppUserModelID: "SaudadeMeow.Tochki"

[Run]
Filename: "{app}\Точки.exe"; Description: "Запустить «ТОЧКИ»"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Code]
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpSelectDir) and
     (FileExists(ExpandConstant('{app}\portable.json')) or
      (DirExists(ExpandConstant('{app}\Data')) and
       not FileExists(ExpandConstant('{app}\distribution.json')))) then
  begin
    MsgBox('Выберите новую папку установки. Данные старой Portable-версии можно импортировать после первого запуска.', mbError, MB_OK);
    Result := False;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if FileExists(ExpandConstant('{app}\portable.json')) or
     (DirExists(ExpandConstant('{app}\Data')) and
      not FileExists(ExpandConstant('{app}\distribution.json'))) then
    Result := 'Нельзя устанавливать поверх Portable. Выберите новую папку и импортируйте Data после запуска.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ExitCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    { Fixed Version 120+ needs AppContainer read/execute ACLs on Windows 10.
      Apply them at install time, never by elevating the running app. }
    if not Exec(ExpandConstant('{sys}\icacls.exe'),
       '"' + ExpandConstant('{app}\WebView2') +
       '" /grant *S-1-15-2-2:(OI)(CI)(RX) /grant *S-1-15-2-1:(OI)(CI)(RX)',
       '', SW_HIDE, ewWaitUntilTerminated, ExitCode) or (ExitCode <> 0) then
      RaiseException('Не удалось настроить доступ к встроенному WebView2. Повторите установку.');
  end;
end;
