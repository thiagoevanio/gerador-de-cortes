"""3.15: doutor de instalação (examina o PC, conserta, lê o erro e pede ajuda à IA) e atalhos que acham
o Python certo sozinhos."""
import hashlib
import io
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import doutor


def _item(id_, ok, conserto=None):
    return dict(id=id_, nome=id_, ok=ok, detalhe="", conserto=None if ok else conserto)


class Exame(unittest.TestCase):
    def test_pc_sem_python_312(self):
        with patch.object(doutor, "python_do_programa", return_value=None), \
             patch.object(doutor, "python_base", return_value=None), \
             patch.object(doutor, "pythons_do_pc", return_value=["C:/Py314/python.exe"]), \
             patch.object(doutor, "versao_de", side_effect=lambda c: (3, 14) if "314" in str(c) else None), \
             patch.object(doutor, "venv_quebrado", return_value=False), \
             patch.object(doutor, "internet_ok", return_value=(True, "")):
            rel = {i["id"]: i for i in doutor.examinar()}
        self.assertEqual(rel["python"]["conserto"], "instalar_python")
        self.assertIn("3.14", rel["python"]["detalhe"])          # explica por que o 3.14 não serve
        self.assertEqual(rel["bibliotecas"]["conserto"], "instalar_bibliotecas")

    def test_venv_de_outro_pc(self):
        with patch.object(doutor, "python_do_programa", return_value=None), \
             patch.object(doutor, "python_base", return_value="C:/Py312/python.exe"), \
             patch.object(doutor, "venv_quebrado", return_value=True), \
             patch.object(doutor, "versao_de", return_value=None), \
             patch.object(doutor, "internet_ok", return_value=(True, "")):
            rel = {i["id"]: i for i in doutor.examinar()}
        self.assertEqual(rel["python"]["conserto"], "criar_venv")

    def test_este_pc_esta_completo(self):
        rel = doutor.examinar()
        self.assertEqual([i["nome"] for i in doutor.problemas(rel)], [])
        self.assertIn("Tudo certo", doutor.texto_relatorio(rel))


class LerErro(unittest.TestCase):
    def test_regras(self):
        casos = {
            "ImportError: DLL load failed while importing cv2": "instalar_vcredist",
            "ERROR: No matching distribution found for numpy==2.5.4": "criar_venv",
            "THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE": "limpar_cache_pip",
            "'ffmpeg' não é reconhecido como um comando interno": "ajustar_path",
            "No Python at 'D:\\Python312\\python.exe'": "criar_venv",
        }
        for erro, conserto in casos.items():
            self.assertIn(conserto, doutor.ler_erro(erro)[0], erro)

    def test_passos_manuais(self):
        _, _, manuais = doutor.ler_erro("ssl.SSLError: CERTIFICATE_VERIFY_FAILED")
        self.assertTrue(any("data e a hora" in m for m in manuais))
        self.assertEqual(doutor.ler_erro("tudo bem"), ([], [], []))


class IA(unittest.TestCase):
    def test_ia_so_escolhe_da_lista(self):
        resposta = {"causa": "x", "explicacao": "y",
                    "consertos": ["instalar_vcredist", "rm -rf C:\\", "format_c", "criar_venv"],
                    "passos_manuais": ["reinicie o PC"]}
        with patch("cortes.ia_json", return_value=resposta) as ia:
            r = doutor.perguntar_ia([_item("ffmpeg", False, "instalar_ffmpeg")], "erro qualquer", print)
        self.assertEqual(r["consertos"], ["instalar_vcredist", "criar_venv"])
        self.assertIn("não instrução", ia.call_args.args[0])          # o log vai como material
        self.assertIn("NÃO roda comandos", ia.call_args.kwargs["sistema"])

    def test_sem_ia(self):
        with patch("cortes.ia_json", return_value=None):
            self.assertIsNone(doutor.perguntar_ia([], "erro", print))


class Consertar(unittest.TestCase):
    def test_conserta_e_confere(self):
        exames = [[_item("ffmpeg", False, "instalar_ffmpeg")], [_item("ffmpeg", True)]]
        feito = []
        with patch.object(doutor, "examinar", side_effect=exames), \
             patch.dict(doutor.CONSERTOS, {"instalar_ffmpeg": (lambda log: feito.append(1) or True, "ffmpeg")}):
            ok, _ = doutor.consertar(lambda t: None)
        self.assertTrue(ok)
        self.assertEqual(feito, [1])

    def test_regra_depois_ia(self):
        """1ª rodada falha; o log tem um erro desconhecido → a IA escolhe o conserto que resolve."""
        ruim = [_item("bibliotecas", False, "instalar_bibliotecas")]
        exames = [ruim, ruim, [_item("bibliotecas", True)]]
        feitos = []

        def conserto(nome, resolve):
            return (lambda log: feitos.append(nome) or resolve, nome)
        with patch.object(doutor, "examinar", side_effect=exames), \
             patch.object(doutor, "ultimo_log", return_value="erro estranho que nenhuma regra conhece"), \
             patch.object(doutor, "perguntar_ia", return_value={"causa": "c", "explicacao": "e",
                                                                 "consertos": ["reinstalar_bibliotecas"],
                                                                 "passos_manuais": []}) as ia, \
             patch.dict(doutor.CONSERTOS, {"instalar_bibliotecas": conserto("instalar", False),
                                           "reinstalar_bibliotecas": conserto("reinstalar", True)}):
            ok, _ = doutor.consertar(lambda t: None, usar_ia=True)
        self.assertTrue(ok)
        ia.assert_called_once()
        self.assertEqual(feitos, ["instalar", "reinstalar", "instalar"])

    def test_nao_repete_para_sempre(self):
        ruim = [_item("ffmpeg", False, "instalar_ffmpeg")]
        feitos = []
        with patch.object(doutor, "examinar", return_value=ruim), patch.object(doutor, "ultimo_log", return_value=""), \
             patch.dict(doutor.CONSERTOS, {"instalar_ffmpeg": (lambda log: feitos.append(1) or False, "ffmpeg")}):
            ok, _ = doutor.consertar(lambda t: None, rodadas=5)
        self.assertFalse(ok)
        self.assertEqual(len(feitos), 2)


class Ffmpeg(unittest.TestCase):
    def _zip(self, destino):
        with zipfile.ZipFile(destino, "w") as z:
            z.writestr("ffmpeg-8.0-essentials_build/bin/ffmpeg.exe", b"falso")
            z.writestr("ffmpeg-8.0-essentials_build/doc/leia.txt", b"x")

    def test_recusa_hash_errado(self):
        with tempfile.TemporaryDirectory() as d, \
             patch.object(doutor, "FERRAMENTAS", Path(d) / "ferramentas"), \
             patch.object(doutor, "baixar", side_effect=lambda url, dest, log: self._zip(dest)), \
             patch("urllib.request.urlopen", return_value=io.BytesIO(b"0" * 64 + b"  arquivo.zip")):
            self.assertFalse(doutor.conserto_instalar_ffmpeg(lambda t: None))
            self.assertFalse((Path(d) / "ferramentas" / "ffmpeg").exists())

    def test_extrai_so_o_bin(self):
        with tempfile.TemporaryDirectory() as d:
            zipf = Path(d) / "f.zip"
            self._zip(zipf)
            certo = hashlib.sha256(zipf.read_bytes()).hexdigest().encode()
            ferr = Path(d) / "ferramentas"
            with patch.object(doutor, "FERRAMENTAS", ferr), patch.object(doutor, "FFMPEG_LOCAL", ferr / "ffmpeg" / "bin"), \
                 patch.object(doutor, "baixar", side_effect=lambda url, dest, log: self._zip(dest)), \
                 patch("urllib.request.urlopen", return_value=io.BytesIO(certo)), \
                 patch.object(doutor, "adicionar_ao_path", return_value=True) as path, \
                 patch.object(doutor, "ffmpeg_tem_legenda", return_value=True), \
                 patch("shutil.which", return_value="ffmpeg.exe"):
                self.assertTrue(doutor.conserto_instalar_ffmpeg(lambda t: None))
            self.assertEqual(sorted(p.name for p in (ferr / "ffmpeg").rglob("*") if p.is_file()), ["ffmpeg.exe"])
            path.assert_called_once()

    def test_ffmpeg_deste_pc_tem_legenda(self):
        self.assertTrue(doutor.ffmpeg_tem_legenda(doutor.ffmpeg_atual()))


class Atalhos(unittest.TestCase):
    def test_bat_acha_o_python_com_as_bibliotecas(self):
        with tempfile.TemporaryDirectory() as d:
            teste = Path(d) / "t.bat"
            teste.write_text(f'@echo off\r\ncall "{doutor.PASTA / "_python.bat"}"\r\necho [%PY%]\r\n', encoding="ascii")
            r = subprocess.run(["cmd", "/c", str(teste)], capture_output=True, text=True, timeout=120)
        caminho = r.stdout.strip().strip("[]")
        self.assertTrue(caminho.lower().endswith("python.exe"), r.stdout)
        self.assertEqual(doutor.faltando_em(caminho), [])

    def test_instalador_sem_erro_de_sintaxe(self):
        cmd = ("$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile("
               f"'{doutor.PASTA / 'instalar.ps1'}',[ref]$null,[ref]$e); $e.Count")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.stdout.strip(), "0")


class Path_(unittest.TestCase):
    def test_ffmpeg_local_vem_primeiro(self):
        with tempfile.TemporaryDirectory() as d, patch.object(doutor, "pastas_extras", return_value=[Path(d)]), \
             patch.dict("os.environ", {"PATH": r"C:\Windows"}):
            doutor.path_do_processo()
            import os
            self.assertTrue(os.environ["PATH"].startswith(d))


if __name__ == "__main__":
    unittest.main()
