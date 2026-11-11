# Desinstalador do Gerador de Cortes 9:16
$ErrorActionPreference = "SilentlyContinue"
Add-Type -AssemblyName PresentationFramework
$r = [System.Windows.MessageBox]::Show("Remover o Gerador de Cortes do computador?`n`nOs atalhos e a entrada em Aplicativos serão removidos.", "Desinstalar", "YesNo", "Question")
if ($r -ne "Yes") { exit }
$pasta = $PSScriptRoot
Remove-Item (Join-Path ([Environment]::GetFolderPath("Desktop")) "Gerador de Cortes.lnk")
Remove-Item (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Gerador de Cortes.lnk")
Remove-Item "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\GeradorDeCortes916" -Recurse
$r2 = [System.Windows.MessageBox]::Show("Apagar também a pasta do programa?`n$pasta`n`nATENÇÃO: isso apaga seus cortes prontos, gravações e configurações. Clique NÃO pra guardar.", "Desinstalar", "YesNo", "Warning")
if ($r2 -eq "Yes") {
    Start-Process cmd -ArgumentList "/c timeout /t 2 >nul & rmdir /s /q `"$pasta`"" -WindowStyle Hidden
}
[System.Windows.MessageBox]::Show("Gerador de Cortes removido.", "Desinstalar") | Out-Null
