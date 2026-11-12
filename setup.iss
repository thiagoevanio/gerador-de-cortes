; Instalador (Setup.exe) do Gerador de Cortes 9:16 — feito com o Inno Setup (grátis).
; Não rode este arquivo direto: use o GERAR-SETUP.bat, que separa só os arquivos do programa
; (nada de config.json, contas, cortes ou gravações) e chama o Inno Setup.
;
; O que o Setup faz no PC de quem instala:
;   1. copia o programa para %LOCALAPPDATA%\Programs\Gerador de Cortes (não precisa escolher pasta);
;   2. cria o atalho com o ícone na área de trabalho e no menu Iniciar;
;   3. roda o instalar.ps1 -Setup: Python 3.12, bibliotecas, Visual C++, ffmpeg, PATH e a escolha da IA;
;   4. aparece em Configurações > Aplicativos, com desinstalar.

#ifndef Versao
  #define Versao "3.0"
#endif
#ifndef Pacote
  #define Pacote "dist\_pacote"
#endif

[Setup]
AppId={{6F0C2B7E-3D7A-4E36-9E5B-91A3C0D4C916}
AppName=Gerador de Cortes 9:16
AppVersion={#Versao}
AppVerName=Gerador de Cortes 9:16 (versão {#Versao})
AppPublisher=Gerador de Cortes
DefaultDirName={localappdata}\Programs\Gerador de Cortes
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=Instalar-Gerador-de-Cortes-{#Versao}
SetupIconFile=icone.ico
UninstallDisplayIcon={app}\icone.ico
UninstallDisplayName=Gerador de Cortes 9:16
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Messages]
pt.WelcomeLabel2=Isto vai instalar o [name/ver] no seu computador.%n%nDepois de copiar os arquivos, uma janela azul examina o PC e baixa o que falta (Python 3.12, bibliotecas, ffmpeg). Pode demorar de 5 a 20 minutos, conforme a internet. O Windows vai pedir permissão de administrador uma vez.

[Files]
Source: "{#Pacote}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\Gerador de Cortes"; Filename: "{app}\interface.bat"; WorkingDir: "{app}"; IconFilename: "{app}\icone.ico"; Comment: "Gerador de Cortes 9:16"; Flags: runminimized
Name: "{autoprograms}\Gerador de Cortes"; Filename: "{app}\interface.bat"; WorkingDir: "{app}"; IconFilename: "{app}\icone.ico"; Comment: "Gerador de Cortes 9:16"; Flags: runminimized
Name: "{autoprograms}\Examinar o PC (Gerador de Cortes)"; Filename: "{app}\EXAMINAR-PC.bat"; WorkingDir: "{app}"; IconFilename: "{app}\icone.ico"

[Run]
; examina o PC e instala o que falta (espera terminar). /DTeste gera uma versão sem este passo, só pra testar a cópia.
#ifndef Teste
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\instalar.ps1"" -Setup"; WorkingDir: "{app}"; StatusMsg: "Examinando o PC e instalando o que falta (veja a janela azul)..."; Flags: waituntilterminated
#endif
Filename: "{app}\interface.bat"; WorkingDir: "{app}"; Description: "Abrir o Gerador de Cortes agora"; Flags: postinstall nowait skipifsilent runminimized

[UninstallDelete]
; o que o instalador baixou neste PC (seus cortes e configurações só saem se você disser sim)
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\ferramentas"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files; Name: "{app}\python_do_programa.txt"
Type: files; Name: "{app}\instalacao.log"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and DirExists(ExpandConstant('{app}')) then
    if SuppressibleMsgBox('Apagar também seus cortes prontos, gravações e configurações?' + #13#10 + #13#10 +
              ExpandConstant('{app}') + #13#10 + #13#10 + 'Clique NÃO para guardar.',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
      DelTree(ExpandConstant('{app}'), True, True, True);
end;
