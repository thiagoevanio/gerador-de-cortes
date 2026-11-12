# Instalador do Gerador de Cortes 9:16 — examina o PC e instala tudo sozinho (pede permissão de administrador)
# Passo 1: garante um Python 3.12 (winget ou python.org, com a assinatura conferida).
# Passo 2: o doutor (doutor.py) faz o resto: ambiente .venv, bibliotecas, Visual C++, ffmpeg e PATH,
#          lendo os erros e tentando de novo; se ainda falhar, pede o diagnóstico à IA.
$ErrorActionPreference = "Continue"
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Start-Process powershell "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}
Set-Location $PSScriptRoot
$Host.UI.RawUI.WindowTitle = "Instalador - Gerador de Cortes 9:16"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$env:PYTHONUTF8 = "1"
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}

function Titulo($t) { Write-Host ""; Write-Host "===== $t =====" -ForegroundColor Yellow }
function Ok($t) { Write-Host "  OK  $t" -ForegroundColor Green }
function Aviso($t) { Write-Host "  !!  $t" -ForegroundColor Red }
function Atualizar-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}
function Tem-Winget { return [bool](Get-Command winget -ErrorAction SilentlyContinue) }
function Instalar($id, $nome) {
    if (-not (Tem-Winget)) { Aviso "winget indisponível: não deu pra instalar $nome por aqui."; return }
    Write-Host "  instalando $nome..."
    winget install -e --id $id --accept-package-agreements --accept-source-agreements --silent --disable-interactivity | Out-Host
    Atualizar-Path
}
function Achar-Python312 {
    # nunca usa o 'python' falso da Microsoft Store (WindowsApps) nem outra versão (3.13, 3.14...)
    $candidatos = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $c = & py -3.12 -c "import sys;print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $c) { $candidatos += "$c".Trim() }
    }
    $candidatos += @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
                     "C:\Program Files\Python312\python.exe",
                     (Get-Command python -ErrorAction SilentlyContinue).Source)
    foreach ($c in $candidatos) {
        if ($c -and (Test-Path $c) -and ($c -notlike "*WindowsApps*")) {
            $v = & $c -c "import sys;print('%d.%d' % sys.version_info[:2])" 2>$null
            if ("$v".Trim() -eq "3.12") { return $c }
        }
    }
    return $null
}
function Baixar-Python {
    $url = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
    $exe = Join-Path $env:TEMP "python-3.12.10-amd64.exe"
    Write-Host "  baixando o Python 3.12 do python.org..."
    try { Invoke-WebRequest -Uri $url -OutFile $exe -UseBasicParsing } catch { Aviso "download falhou: $_"; return }
    $s = Get-AuthenticodeSignature -LiteralPath $exe
    if ($s.Status -ne "Valid" -or $s.SignerCertificate.Subject -notlike "*Python Software Foundation*") {
        Aviso "o instalador baixado não tem a assinatura da Python Software Foundation. Não vou rodar."; return
    }
    Write-Host "  instalando (uns 2 minutos)..."
    Start-Process $exe -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0 Include_tcltk=1 Include_pip=1" -Wait
    Atualizar-Path
}

Write-Host ""
Write-Host "   GERADOR DE CORTES 9:16 - INSTALADOR" -ForegroundColor White -BackgroundColor DarkRed
Write-Host "   Examina o PC e instala o que falta. Pode demorar de 5 a 20 minutos (depende da internet)."

Titulo "1/5  Python 3.12"
$py = Achar-Python312
if (-not $py) {
    Write-Host "  O programa usa o Python 3.12 (as bibliotecas não funcionam no 3.13/3.14). Ele fica"
    Write-Host "  separado dos outros Pythons do PC, sem atrapalhar nada."
    Instalar "Python.Python.3.12" "Python 3.12"
    $py = Achar-Python312
    if (-not $py) { Baixar-Python; $py = Achar-Python312 }
}
if ($py) { Ok "Python 3.12: $py" } else {
    Aviso "Não consegui instalar o Python 3.12."
    Write-Host "  Instale à mão: https://www.python.org/downloads/release/python-31210/"
    Write-Host "  (marque 'Add python.exe to PATH') e rode o INSTALAR.bat de novo."
    Read-Host "Enter para sair"; exit
}

Titulo "2/5  Examinando o PC e instalando o que falta"
& $py doutor.py --consertar
$okDoutor = ($LASTEXITCODE -eq 0)
$prog = (Get-Content (Join-Path $PSScriptRoot "python_do_programa.txt") -ErrorAction SilentlyContinue | Select-Object -First 1)
if (-not $prog -or -not (Test-Path $prog)) { $prog = $py }
if ($okDoutor) { Ok "Python, bibliotecas, Visual C++ e ffmpeg prontos" } else { Aviso "Ainda falta algo — vou tentar de novo com ajuda da IA depois do passo 3." }

Titulo "3/5  Inteligência artificial"
Write-Host "  Qual IA você quer usar?"
Write-Host "   [1] Claude  (precisa de assinatura do Claude)"
Write-Host "   [2] Codex   (usa a conta do ChatGPT)"
Write-Host "   [3] Local   (grátis, roda no PC, mais lenta e mais simples)"
Write-Host "   [4] Todas"
Write-Host "   [5] Nenhuma agora"
Write-Host "   [6] Gemini  (conta Google, cota grátis generosa)"
$op = Read-Host "  Digite o número"
if ($op -in @("1", "4")) { Instalar "Anthropic.ClaudeCode" "Claude Code"; Ok "Claude Code" }
if ($op -in @("2", "6", "4")) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Instalar "OpenJS.NodeJS.LTS" "Node.js" }
    $npm = (Get-Command npm -ErrorAction SilentlyContinue).Source
    if (-not $npm) { $npm = "C:\Program Files\nodejs\npm.cmd" }
    if ($op -in @("2", "4")) { & $npm install -g '@openai/codex'; Ok "Codex" }
    if ($op -in @("6", "4")) { & $npm install -g '@google/gemini-cli'; Ok "Gemini" }
}
if ($op -in @("3", "4")) {
    Instalar "Ollama.Ollama" "Ollama (IA local)"
    $ollama = (Get-Command ollama -ErrorAction SilentlyContinue).Source
    if (-not $ollama) { $ollama = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" }
    if (Test-Path $ollama) {
        Start-Process $ollama "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
        Start-Sleep 6
        $modelo = & $prog -c "import contas;print(contas.modelo_recomendado())" 2>$null
        if (-not $modelo) { $modelo = "qwen2.5:3b" }
        Write-Host "  baixando o modelo de IA local recomendado pra este PC: $modelo ..."
        & $ollama pull $modelo
        & $prog -c "import cortes;c=cortes.carregar_config();c['modelo_local']='$modelo';cortes.salvar_config(c)" 2>$null
        Ok "IA local pronta ($modelo — dá pra trocar em Contas & IA)"
    } else { Aviso "Ollama instalado, mas precisa reiniciar o PC antes de baixar o modelo." }
}

Titulo "4/5  Conferindo tudo"
if (-not $okDoutor) {
    $py2 = Achar-Python312
    if (-not $py2) { $py2 = $py }
    & $py2 doutor.py --consertar --ia
    $okDoutor = ($LASTEXITCODE -eq 0)
} else {
    & $prog doutor.py | Out-Host
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
if (-not $okDoutor) {
    Aviso "Quase tudo pronto, mas ainda falta algo (veja os itens com X acima)."
    Write-Host "  O registro completo está em instalacao.log. Siga as dicas acima e rode o INSTALAR.bat de novo,"
    Write-Host "  ou abra o programa: na aba 'Contas & IA' o botão 'Examinar o PC' mostra o que falta."
    Read-Host "  Aperte Enter para fechar"; exit
}
Write-Host "  TUDO PRONTO!" -ForegroundColor Green
Write-Host "  Abra o 'Gerador de Cortes' na área de trabalho."
Write-Host "  Na aba 'Contas & IA', clique em 'Conectar conta' pra fazer login (só na primeira vez)."
Read-Host "  Aperte Enter para fechar"
