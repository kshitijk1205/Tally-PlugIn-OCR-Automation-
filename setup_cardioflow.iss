; CardioFlow AI Accountant - Setup Script
; Inno Setup 6 Script

#define MyAppName "CardioFlow AI Accountant"
#define MyAppShortName "CardioFlow"
#define MyAppVersion "1.0"
#define MyAppPublisher "CardioFlow Technologies"
#define MyAppURL "https://cardioflow.in"
#define MyAppExeName "CardioFlow.exe"
#define MyAppAssocName "CardioFlow Data"
#define MyAppAssocExt ".cfd"

[Setup]
AppId={{B8A7C5D3-9F2E-4A1C-8D6B-3E5F7A2C9B1D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppShortName}
DisableProgramGroupPage=yes
DisableDirPage=no
LicenseFile=
PrivilegesRequired=admin
OutputDir=C:\Users\Admin\Desktop\CardioFlow\installer_output
OutputBaseFilename=CardioFlow_Setup_v{#MyAppVersion}
SetupIconFile=
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
DisableWelcomePage=no
ShowLanguageDialog=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: checkedonce

[Files]
Source: "C:\Users\Admin\Desktop\CardioFlow\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\Admin\Desktop\CardioFlow\config.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\Admin\Desktop\CardioFlow\.env"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "C:\Users\Admin\Desktop\CardioFlow\keygen.py"; DestDir: "{app}\tools"; Flags: ignoreversion
Source: "C:\Users\Admin\Desktop\CardioFlow\web_keygen.py"; DestDir: "{app}\tools"; Flags: ignoreversion
Source: "C:\Users\Admin\Desktop\CardioFlow\license_guard.py"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\mobile_uploads"; Permissions: users-modify
Name: "{app}\Backup_tallypush"; Permissions: users-modify

[Icons]
Name: "{autoprograms}\{#MyAppShortName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppShortName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch CardioFlow AI Accountant"; Flags: postinstall nowait skipifsilent shellexec; WorkingDir: "{app}"

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c taskkill /f /im CardioFlow.exe 2>nul"; Flags: runhidden

[Code]
var
  ActivationPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  ActivationPage := CreateInputQueryPage(
    wpSelectTasks,
    'Activation',
    'Enter your activation key',
    'Please enter the activation key provided by CardioFlow Technologies to activate your copy of CardioFlow AI Accountant.'#13#10#13#10 +
    'If you do not have an activation key, contact your distributor.'
  );
  ActivationPage.Add('Activation Key:', False);
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  LicenseFile: string;
  KeyInput: string;
begin
  if CurStep = ssPostInstall then
  begin
    KeyInput := ActivationPage.Values[0];
    if KeyInput <> '' then
    begin
      LicenseFile := ExpandConstant('{app}\license.key');
      SaveStringToFile(LicenseFile, Trim(KeyInput), False);
    end;
  end;
end;
