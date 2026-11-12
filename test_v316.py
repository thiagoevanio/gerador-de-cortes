"""3.16: instalador .exe (Inno Setup) com atalho personalizado na área de trabalho."""
import re
import subprocess
import unittest
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ISS = (PASTA / "setup.iss").read_text(encoding="utf-8-sig")
PESSOAIS = re.compile(r"(^|/)(config\.json|canais\.json|estado\.json|aprendizado\.json|tendencias\.json|"
                      r"client_secret\.json|token_youtube.*\.json|.*\.sqlite3.*|python_do_programa\.txt)$")


def erros_de_sintaxe(arquivo):
    cmd = ("$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile("
           f"'{PASTA / arquivo}',[ref]$null,[ref]$e); $e.Count")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=120)
    return r.stdout.strip()


class Setup(unittest.TestCase):
    def test_scripts_sem_erro_de_sintaxe(self):
        for arq in ("gerar_setup.ps1", "instalar.ps1"):
            self.assertEqual(erros_de_sintaxe(arq), "0", arq)

    def test_atalho_personalizado(self):
        self.assertIn(r'Name: "{autodesktop}\Gerador de Cortes"', ISS)
        self.assertIn(r'IconFilename: "{app}\icone.ico"', ISS)
        self.assertIn("SetupIconFile=icone.ico", ISS)

    def test_instala_sem_admin_e_chama_o_doutor(self):
        self.assertIn("PrivilegesRequired=lowest", ISS)          # Program Files não deixaria salvar cortes
        self.assertIn(r'instalar.ps1"" -Setup', ISS)
        self.assertIn("waituntilterminated", ISS)

    def test_desinstalar_guarda_os_cortes_por_padrao(self):
        self.assertIn(r'Name: "{app}\.venv"', ISS)
        self.assertIn("MB_DEFBUTTON2, IDNO", ISS)

    def test_nenhum_dado_pessoal_no_git(self):
        """O GERAR-SETUP só empacota o que está no git: contas e configurações não podem estar lá."""
        arquivos = subprocess.run(["git", "ls-files"], cwd=PASTA, capture_output=True, text=True).stdout.split()
        self.assertEqual([a for a in arquivos if PESSOAIS.search(a)], [])

    def test_instalar_ps1_nao_duplica_atalho(self):
        ps1 = (PASTA / "instalar.ps1").read_text(encoding="utf-8-sig")
        self.assertIn('unins000.exe")) { $Setup = $true }', ps1)
        self.assertIn("-Verb RunAs -Wait", ps1)


if __name__ == "__main__":
    unittest.main()
