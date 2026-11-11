# Instalador do Gerador de Cortes 9:16 — instala tudo sozinho (pede permissão de administrador)
$ErrorActionPreference = "Continue"
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Start-Process powershell "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}
Set-Location $PSScriptRoot
$Host.UI.RawUI.WindowTitle = "Instalador - Gerador de Cortes 9:16"

function Titulo($t) { Write-Host ""; Write-Host "===== $t =====" -ForegroundColor Yellow }
function Ok($t) { Write-Host "  OK  $t" -ForegroundColor Green }
function Aviso($t) { Write-Host "  !!  $t" -ForegroundColor Red }
function Atualizar-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}
function Instalar($id, $nome) {
    Write-Host "  instalando $nome..."
    winget install -e --id $id --accept-package-agreements --accept-source-agreements --silent | Out-Host
    Atualizar-Path
}
function Achar-Python {
    foreach ($c in @((Get-Command python -ErrorAction SilentlyContinue).Source,
                     "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
                     "C:\Program Files\Python312\python.exe")) {
        if ($c -and (Test-Path $c) -and ($c -notlike "*WindowsApps*")) {
            $v = & $c --version 2>&1
            if ("$v" -like "Python 3*") { return $c }
        }
    }
    return $null
}

Write-Host ""
Write-Host "   GERADOR DE CORTES 9:16 - INSTALADOR" -ForegroundColor White -BackgroundColor DarkRed
Write-Host "   Isso instala tudo que o programa precisa. Pode demorar alguns minutos."

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Aviso "O 'winget' não está disponível. Instale o 'Instalador de Aplicativo' (App Installer) pela Microsoft Store e rode de novo."
    Read-Host "Aperte Enter para sair"; exit
}

Titulo "1/5  Python"
$py = Achar-Python
if (-not $py) { Instalar "Python.Python.3.12" "Python 3.12"; $py = Achar-Python }
if ($py) { Ok "Python: $py" } else { Aviso "Não consegui instalar o Python."; Read-Host "Enter para sair"; exit }

Titulo "2/5  ffmpeg (monta os vídeos)"
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { Instalar "Gyan.FFmpeg" "ffmpeg" }
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) { Ok "ffmpeg instalado" } else { Aviso "ffmpeg vai funcionar depois de reiniciar o PC." }

Titulo "3/5  Bibliotecas do Python"
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -r requirements.txt
if ($LASTEXITCODE -eq 0) { Ok "bibliotecas instaladas" } else { Aviso "deu algum erro nas bibliotecas" }

Titulo "4/5  Inteligência artificial"
Write-Host "  Qual IA você quer usar?"
Write-Host "   [1] Claude  (precisa de assinatura do Claude)"
Write-Host "   [2] Codex   (usa a conta do ChatGPT)"
Write-Host "   [3] Local   (grátis, roda no PC, mais lenta e mais simples)"
Write-Host "   [4] Todas"
Write-Host "   [5] Nenhuma agora"
Write-Host "   [6] Gemini  (conta Google, cota grátis generosa)"
$op = Read-Host "  Digite o número"
if ($op -in @("1", "4")) { Instalar "Anthropic.ClaudeCode" "Claude Code"; Ok "Claude Code" }
if ($op -in @("2", "4")) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Instalar "OpenJS.NodeJS.LTS" "Node.js" }
    $npm = (Get-Command npm -ErrorAction SilentlyContinue).Source
    if (-not $npm) { $npm = "C:\Program Files\nodejs\npm.cmd" }
    & $npm install -g '@openai/codex'
    Ok "Codex"
}
if ($op -in @("6", "4")) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Instalar "OpenJS.NodeJS.LTS" "Node.js" }
    $npm = (Get-Command npm -ErrorAction SilentlyContinue).Source
    if (-not $npm) { $npm = "C:\Program Files\nodejs\npm.cmd" }
    & $npm install -g '@google/gemini-cli'
    Ok "Gemini"
}
if ($op -in @("3", "4")) {
    Instalar "Ollama.Ollama" "Ollama (IA local)"
    $ollama = (Get-Command ollama -ErrorAction SilentlyContinue).Source
    if (-not $ollama) { $ollama = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" }
    if (Test-Path $ollama) {
        Start-Process $ollama "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
        Start-Sleep 6
        Write-Host "  baixando o modelo de IA local (uns 2 GB)..."
        & $ollama pull qwen2.5:3b
        Ok "IA local pronta"
    } else { Aviso "Ollama instalado, mas precisa reiniciar o PC antes de baixar o modelo." }
}

Titulo "5/5  Atalhos e Programas instalados"
$versao = (Get-Content (Join-Path $PSScriptRoot "VERSAO.txt") -ErrorAction SilentlyContinue | Select-Object -First 1)
if (-not $versao) { $versao = "3.0.0" }
$icone = Join-Path $PSScriptRoot "icone.ico"
$alvo = Join-Path $PSScriptRoot "interface.bat"
$ws = New-Object -ComObject WScript.Shell
$locais = @([Environment]::GetFolderPath("Desktop"), (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"))
foreach ($pasta in $locais) {
    $lnk = $ws.CreateShortcut((Join-Path $pasta "Gerador de Cortes.lnk"))
    $lnk.TargetPath = $alvo
    $lnk.WorkingDirectory = $PSScriptRoot
    $lnk.IconLocation = "$icone,0"
    $lnk.WindowStyle = 7
    $lnk.Description = "Gerador de Cortes 9:16"
    $lnk.Save()
}
Ok "Atalhos na área de trabalho e no menu Iniciar"
# aparece em Configurações > Aplicativos (com desinstalar), sem precisar de admin
$chave = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\GeradorDeCortes916"
New-Item -Path $chave -Force | Out-Null
$desinst = "powershell -NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $PSScriptRoot 'desinstalar.ps1')`""
$props = @{ DisplayName = "Gerador de Cortes 9:16"; DisplayVersion = $versao; Publisher = "Gerador de Cortes";
            DisplayIcon = $icone; InstallLocation = $PSScriptRoot; UninstallString = $desinst; NoModify = 1; NoRepair = 1 }
foreach ($k in $props.Keys) { Set-ItemProperty -Path $chave -Name $k -Value $props[$k] }
Ok "Aparece em Configurações > Aplicativos (versão $versao)"

Write-Host ""
Write-Host "  TUDO PRONTO!" -ForegroundColor Green
Write-Host "  Abra o 'Gerador de Cortes' na área de trabalho."
Write-Host "  Na aba 'Contas & IA', clique em 'Conectar conta' pra fazer login (só na primeira vez)."
Read-Host "  Aperte Enter para fechar"
