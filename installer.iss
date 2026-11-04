; LinguaPilot installer - Inno Setup script
; Requires Inno Setup 6. Place dist files and icon next to this script.

#define AppName "LinguaPilot"
#define AppVersion "1.0.0"
#define AppPublisher "ilabolAfk"
#define AppURL "https://just-sources.com/lingua-pilot/"

[Setup]
AppId={{8B4F1C2A-3C5E-4A6B-9D2E-7A1F3B4C5D6E}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=installer
OutputBaseFilename=LinguaPilot-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\LinguaPilot.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\LinguaPilot.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\lingua-pilot-server.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "ilabolAfk-code-signing.cer"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\LinguaPilot.exe"; IconFilename: "{app}\icon.ico"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\LinguaPilot.exe"; IconFilename: "{app}\icon.ico"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\LinguaPilot.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
const
  OllamaRegPath = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\Ollama';
  OllamaSetupUrl = 'https://ollama.com/download/OllamaSetup.exe';
  MB_ICONQUESTION = 32;

{ --- Импорт self-signed сертификата в доверенные хранилища --- }
procedure ImportCert(CertFile: String);
var
  ResultCode: Integer;
begin
  { In Root store, user scope }
  Exec(ExpandConstant('{sys}\certutil.exe'), '-user -addstore Root "' + CertFile + '"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  { In TrustedPublisher store, user scope }
  Exec(ExpandConstant('{sys}\certutil.exe'), '-user -addstore TrustedPublisher "' + CertFile + '"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function IsOllamaInstalled(): Boolean;
begin
  Result := RegKeyExists(HKLM, OllamaRegPath) or RegKeyExists(HKCU, OllamaRegPath);
end;

function DownloadProgress(Url, Filename: String; Progress: Int64;
  ProgressMax: Int64): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Choice: Integer;
  OllamaInstaller: String;
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    { Импорт самоподписанного сертификата для доверия к подписи }
    ImportCert(ExpandConstant('{app}\ilabolAfk-code-signing.cer'));
    if not IsOllamaInstalled() then
    begin
      Choice := MsgBox('Ollama (локальная ИИ-модель) не обнаружена. Установить её сейчас?',
        mbInformation, MB_ICONQUESTION + MB_YESNO);
      if Choice = IDYES then
      begin
        MsgBox('Скачивание установщика Ollama... Это может занять несколько минут.',
          mbInformation, MB_OK);
        DownloadTemporaryFile(OllamaSetupUrl, 'OllamaSetup.exe', '', @DownloadProgress);
        OllamaInstaller := ExpandConstant('{tmp}\OllamaSetup.exe');
        if FileExists(OllamaInstaller) then
        begin
          if Exec(OllamaInstaller, '/VERYSILENT', '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
            MsgBox('Ollama установлена. Первый запуск моделей будет дольше — они скачаются автоматически.',
              mbInformation, MB_OK)
          else
            MsgBox('Не удалось завершить установку Ollama. Запустите облако вручную позже.',
              mbError, MB_OK);
        end
        else
          MsgBox('Не удалось скачать Ollama. Проверьте интернет и установите её вручную с ollama.com.',
            mbError, MB_OK);
      end;
    end;
  end;
end;