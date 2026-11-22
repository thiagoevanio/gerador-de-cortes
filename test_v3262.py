"""3.26.2: correções da análise completa — prévia sem a pasta Temp, pasta de reels à prova de vídeo
aberto, Doutor reinstalando a biblioteca certa, PIN do celular, só a nossa extensão e legenda traduzida."""
import base64
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import celular
import cortes
import doutor
import instagram
import legendas
import monitor
import previa


class Previa(unittest.TestCase):
    def test_funciona_mesmo_se_o_windows_apagar_a_pasta_temp(self):
        shutil.rmtree(previa._PASTA, ignore_errors=True)
        self.assertTrue(previa._foto_exemplo().exists())


class PastaDeReels(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.pasta = Path(self.dir.name)
        indice = {"AAAAA1": {"data": "20261101"}, "BBBBB2": {"data": "20261110"}, "CCCCC3": {"data": "20261120"}}
        for rid in indice:
            (self.pasta / f"{rid}.mp4").write_bytes(b"0")
        (self.pasta / "reels.json").write_text(json.dumps(indice), encoding="utf-8")

    def tearDown(self):
        self.dir.cleanup()

    def test_video_aberto_no_player_nao_baguca_a_pasta(self):
        original = Path.rename
        chamadas = []

        def rename(self_, alvo):
            chamadas.append(self_.name)
            if len(chamadas) == 2:                       # o 2º arquivo está aberto no player
                raise PermissionError("em uso")
            return original(self_, alvo)
        antes = sorted(p.name for p in self.pasta.glob("*.mp4"))
        with patch.object(Path, "rename", rename), self.assertRaises(OSError):
            instagram.organizar(self.pasta)
        self.assertEqual(sorted(p.name for p in self.pasta.glob("*.mp4")), antes)   # desfez tudo
        self.assertEqual(instagram.organizar(self.pasta), 3)                         # depois organiza
        self.assertEqual(sorted(p.name for p in self.pasta.glob("*.mp4"))[0], "001 - 2026-11-20 - CCCCC3.mp4")

    def test_nome_de_passagem_e_reconhecido(self):
        (self.pasta / "BBBBB2.mp4").rename(self.pasta / "~1a2b3c4d_BBBBB2.mp4")
        self.assertEqual(instagram._ja_baixados(self.pasta), {"AAAAA1", "BBBBB2", "CCCCC3"})  # não baixa de novo
        self.assertEqual(instagram.arquivo_do_reel(self.pasta, "BBBBB2").name, "~1a2b3c4d_BBBBB2.mp4")
        instagram.organizar(self.pasta)
        self.assertFalse(list(self.pasta.glob("~*")))

    def test_ja_em_ordem_nao_mexe_em_nada(self):
        instagram.organizar(self.pasta)
        with patch.object(Path, "rename", side_effect=AssertionError("não devia renomear")):
            instagram.organizar(self.pasta)


class Doutor(unittest.TestCase):
    def test_reinstala_a_biblioteca_que_falta(self):
        self.assertEqual(set(doutor.PIP_DO_MODULO), {m for _, m in doutor.BIBLIOTECAS})
        pedidos = []
        with patch.object(doutor, "python_do_venv", return_value="py"), \
                patch.object(doutor, "faltando_em", side_effect=[["faster_whisper", "cv2"], []]), \
                patch.object(doutor, "rodar", side_effect=lambda cmd, log=None: (pedidos.append(cmd), (0, ""))[1]):
            self.assertTrue(doutor.conserto_reinstalar_bibliotecas(print))
        self.assertEqual(pedidos[0][-2:], ["faster-whisper", "opencv-python-headless"])


class PinDoCelular(unittest.TestCase):
    def setUp(self):
        self.p = patch.dict(celular._estado, {"pin": "123456"})
        self.p.start()
        celular._tentativas.update(erros=0, ate=0.0)

    def tearDown(self):
        self.p.stop()
        celular._tentativas.update(erros=0, ate=0.0)

    def test_bloqueia_depois_de_errar_demais(self):
        self.assertIs(celular.conferir_pin("123456"), True)
        for _ in range(celular.ERROS_MAX):
            self.assertIs(celular.conferir_pin("000000"), False)
        espera = celular.conferir_pin("123456")          # nem o certo entra durante o bloqueio
        self.assertNotIn(espera, (True, False))
        self.assertGreater(espera, 0)

    def test_pin_novo_tem_6_digitos(self):
        self.assertRegex(celular.pin_novo(), r"^\d{6}$")


class SoANossaExtensao(unittest.TestCase):
    def test_id_fixo_bate_com_a_chave_do_manifest(self):
        m = json.loads(Path("extensao_chrome/manifest.json").read_text(encoding="utf-8"))
        der = base64.b64decode(m["key"])
        ident = "".join(chr(ord("a") + int(c, 16)) for c in hashlib.sha256(der).hexdigest()[:32])
        self.assertEqual(ident, monitor.ID_EXTENSAO)

    def test_outra_extensao_e_barrada(self):
        class Falso(monitor.Painel):
            def __init__(self, origem):
                self.headers = {"Host": f"127.0.0.1:{monitor.PORTA}", "Origin": origem}
        self.assertTrue(Falso(monitor.ORIGEM_EXTENSAO)._origem_permitida())
        self.assertFalse(Falso("chrome-extension://" + "a" * 32)._origem_permitida())


class LegendaTraduzida(unittest.TestCase):
    def test_uma_linha_e_sem_encavalar(self):
        with tempfile.TemporaryDirectory() as d:
            ass = cortes.gerar_ass_blocos([(0, 3, "esta es una frase muy larga que no cabe en una sola linea"),
                                           (2.5, 5, "y otra")], Path(d) / "es.ass")
            linhas = [l for l in ass.read_text(encoding="utf-8").splitlines() if l.startswith("Dialogue: 0,")]
        self.assertGreater(len(linhas), 2)                 # a frase longa virou pedaços
        self.assertTrue(all("{\\q2}" in l for l in linhas))
        tempos = [(legendas._seg(l.split(",")[1]), legendas._seg(l.split(",")[2])) for l in linhas]
        for (_, fim), (ini, _) in zip(tempos, tempos[1:]):
            self.assertLessEqual(fim, ini)


if __name__ == "__main__":
    unittest.main()
