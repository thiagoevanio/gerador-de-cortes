# Gera o dist\Instalar-Gerador-de-Cortes-<versão>.exe (um arquivo só, pra mandar pra quem quiser instalar).
# Só entram os arquivos do programa que estão no git: config.json, contas, tokens, cortes, gravações,
# .venv e ferramentas deste PC NUNCA vão junto. Os testes também ficam de fora.
# -Teste: gera uma versão que só copia (sem o passo do Python), usada nos testes automáticos.
param([switch]$Teste)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    Write-Host "Instalando o Inno Setup (grátis, só neste PC; quem instala o Gerador não precisa dele)..."
    winget install -e --id JRSoftware.InnoSetup --scope user --accept-package-agreements --accept-source-agreements --silent --disable-interactivity
    $iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    if (-not (Test-Path $iscc)) { throw "Não achei o Inno Setup. Baixe em https://jrsoftware.org/isdl.php e rode de novo." }
}

$versao = (Get-Content VERSAO.txt | Select-Object -First 1).Trim()
$fora = '^(test_.*|\.git.*|setup\.iss|gerar_setup\.ps1|GERAR-SETUP\.bat|desinstalar\.ps1)$'
$pacote = Join-Path $PSScriptRoot "dist\_pacote"
if (Test-Path $pacote) { Remove-Item $pacote -Recurse -Force }
$n = 0
foreach ($rel in (git ls-files)) {
    if ((Split-Path $rel -Leaf) -match $fora -or -not (Test-Path -LiteralPath $rel)) { continue }
    $dest = Join-Path $pacote $rel
    New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
    Copy-Item -LiteralPath $rel $dest
    $n++
}
Write-Host "Empacotando $n arquivos da versão $versao..."
$extra = if ($Teste) { @("/DTeste", "/FInstalar-Gerador-de-Cortes-TESTE") } else { @() }
& $iscc "/DVersao=$versao" "/DPacote=$pacote" @extra /Qp setup.iss
if ($LASTEXITCODE -ne 0) { throw "O Inno Setup deu erro (código $LASTEXITCODE)." }
Remove-Item $pacote -Recurse -Force
if ($Teste) { return }
$exe = Get-Item "dist\Instalar-Gerador-de-Cortes-$versao.exe"
Write-Host ""
Write-Host ("PRONTO: {0}  ({1:N0} MB)" -f $exe.FullName, ($exe.Length / 1MB)) -ForegroundColor Green
Write-Host "Mande esse arquivo pra quem quiser instalar: dois cliques e ele faz o resto."
