"""3.19: downloads que não travam — desafio do YouTube resolvido (yt-dlp-ejs + Node), só os pedaços do
trecho (índice sidx), reserva com limite de tempo e yt-dlp atualizado sozinho."""
import struct
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import baixador
import cortes


def _caixa(tipo, corpo=b""):
    return struct.pack(">I4s", 8 + len(corpo), tipo.encode()) + corpo


def _sidx(escala, inicio_pts, pedacos, primeiro=0):
    corpo = bytes([0, 0, 0, 0]) + struct.pack(">II", 1, escala) + struct.pack(">II", inicio_pts, primeiro)
    corpo += struct.pack(">HH", 0, len(pedacos))
    for tam, dur in pedacos:
        corpo += struct.pack(">III", tam, dur, 0x90000000)
    return _caixa("sidx", corpo)


class Indice(unittest.TestCase):
    def test_le_o_sidx(self):
        cabeca = _caixa("ftyp", b"isom" + b"\0" * 4) + _caixa("moov", b"\0" * 20)
        fim_moov = len(cabeca)
        cabeca += _sidx(1000, 0, [(500, 5000), (700, 5000), (900, 5000)])
        fm, partes = baixador.ler_indice(cabeca)
        self.assertEqual(fm, fim_moov)
        self.assertEqual([(a, b) for a, b, _x, _y in partes], [(0, 5), (5, 10), (10, 15)])
        self.assertEqual(partes[0][2], len(cabeca))                   # o 1º pedaço vem logo depois do índice
        self.assertEqual(partes[1][2] - partes[0][2], 500)
        self.assertEqual(partes[2][3] - partes[2][2] + 1, 900)

    def test_sem_indice(self):
        self.assertIsNone(baixador.ler_indice(_caixa("ftyp", b"x" * 8) + _caixa("moov", b"\0" * 20)))

    def test_baixa_so_os_pedacos_do_trecho(self):
        cabeca = _caixa("ftyp", b"isom" + b"\0" * 4) + _caixa("moov", b"\0" * 20)
        cabeca += _sidx(1000, 0, [(100, 5000)] * 6)                   # 6 pedaços de 5 s e 100 bytes
        arquivo = cabeca + bytes(range(256)) * 3
        pedidos = []

        def pegar(fmt, a, b, tentativas=3):
            pedidos.append((a, b))
            return arquivo[a:b + 1]
        with tempfile.TemporaryDirectory() as d, patch.object(baixador, "_pegar", side_effect=pegar):
            inicio = baixador.baixar_partes({"url": "x"}, 12, 18, Path(d) / "p.mp4")
            dados = (Path(d) / "p.mp4").read_bytes()
        self.assertEqual(inicio, 10)                                  # começa no pedaço de 10 s
        base = len(cabeca)
        self.assertEqual(pedidos[-1], (base + 200, base + 399))       # só os pedaços de 10-15 s e 15-20 s
        self.assertEqual(len(dados), cabeca.index(b"sidx") - 4 + 200)


class Opcoes(unittest.TestCase):
    def test_desafio_do_youtube_e_limites(self):
        with patch.object(baixador, "motor_js", return_value={"node": {"path": "node.exe"}}):
            op = baixador.opcoes_ytdlp(format="x")
            self.assertEqual(op["js_runtimes"], {"node": {"path": "node.exe"}})
            self.assertEqual(baixador.args_cli_js(), ["--js-runtimes", "node:node.exe"])
        self.assertEqual(op["socket_timeout"], 30)
        self.assertEqual(op["http_chunk_size"], 10 * 1024 * 1024)
        self.assertEqual(op["format"], "x")

    def test_este_pc_resolve_o_desafio(self):
        self.assertTrue(baixador.tem_ejs())
        self.assertIsNotNone(baixador.motor_js())

    def test_ninguem_mais_usa_ytdlp_sem_as_opcoes(self):
        for arq in ("momentos.py", "monitor.py", "tendencias.py", "chat_vod.py"):
            texto = Path(arq).read_text(encoding="utf-8")
            self.assertIn("baixador.opcoes_ytdlp", texto, arq)
        self.assertNotIn("download_range_func", Path("cortes.py").read_text(encoding="utf-8"))


class Reserva(unittest.TestCase):
    def test_limite_de_tempo(self):
        with tempfile.TemporaryDirectory() as d, \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired("yt-dlp", 300)):
            with self.assertRaisesRegex(RuntimeError, "passou de 5 min"):
                baixador.trecho_com_limite("u", 0, 10, Path(d), "b", ["res:720"], 300)

    def test_rapido_falha_e_o_tradicional_assume(self):
        class Ydl:
            def __init__(self, op): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def extract_info(self, url, download=False): return {"title": "T", "uploader": "C"}
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            arq = pasta / "original.mp4"

            def tradicional(*a, **k):
                arq.write_bytes(b"x" * 20000)
                return arq
            with patch("yt_dlp.YoutubeDL", Ydl), \
                 patch.object(baixador, "trecho_rapido", side_effect=ValueError("sem índice")), \
                 patch.object(baixador, "trecho_com_limite", side_effect=tradicional) as trad, \
                 patch.object(cortes, "duracao_video", return_value=45.0):
                r, meta = cortes.baixar_trecho("https://www.youtube.com/watch?v=abc", 10, 55, pasta)
        self.assertEqual(r, arq)
        self.assertEqual(meta["titulo"], "T")
        trad.assert_called_once()


class Atualizar(unittest.TestCase):
    def test_so_a_cada_3_dias(self):
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "ytdlp.txt"
            arq.write_text(str(time.time() - 3600), encoding="utf-8")
            with patch.object(baixador, "ARQ_ATUALIZADO", arq), patch("subprocess.run") as run:
                self.assertIsNone(baixador.manter_atualizado(log=lambda t: None))
                run.assert_not_called()
                run.return_value = subprocess.CompletedProcess([], 0, "2026.11.10 0.8.0", "")
                avisos = []
                self.assertTrue(baixador.manter_atualizado(log=avisos.append, forcar=True))
            self.assertIn("-U", run.call_args_list[0].args[0])
            self.assertIn("yt-dlp-ejs", run.call_args_list[0].args[0])
            self.assertTrue(avisos)

    def test_bibliotecas(self):
        import doutor
        self.assertIn(("yt-dlp-ejs", "yt_dlp_ejs"), doutor.BIBLIOTECAS)
        self.assertIn("yt-dlp-ejs", Path("requirements.txt").read_text(encoding="utf-8"))
        self.assertIn("instalar_node", doutor.CONSERTOS)


class Decodificacao(unittest.TestCase):
    def test_sem_caractere_invisivel_nos_arquivos(self):
        for arq in Path(".").glob("*.py"):
            self.assertNotIn(chr(8), arq.read_text(encoding="utf-8"), arq.name)


if __name__ == "__main__":
    unittest.main()
