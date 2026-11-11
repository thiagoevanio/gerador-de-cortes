"""3.9: download com nova tentativa, gancho só quando vale, nota mínima no automático, música com ducking."""
import random
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import cortes
import musica


def _pal(textos, passo=0.5):
    return [{"t": t, "ini": passo * i, "fim": passo * i + 0.4} for i, t in enumerate(textos)]


class Download(unittest.TestCase):
    def setUp(self):
        cortes.aplicar_config(cortes.carregar_config())

    def _falso_ytdlp(self, falhas, erro="ffmpeg exited with code 3436169992"):
        chamadas = []

        class YDL:
            def __init__(self, opcoes):
                self.opcoes = opcoes

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def extract_info(self, url, download=True):
                chamadas.append(self.opcoes)
                if len(chamadas) <= falhas:
                    Path(self.opcoes["outtmpl"].replace("%(ext)s", "mp4.part")).write_bytes(b"x")
                    raise RuntimeError(erro)
                Path(self.opcoes["outtmpl"].replace("%(ext)s", "mp4")).write_bytes(b"0" * 20_000)
                return {"title": "T", "uploader": "Canal"}

        mod = types.ModuleType("yt_dlp")
        mod.YoutubeDL = YDL
        utils = types.ModuleType("yt_dlp.utils")
        utils.download_range_func = lambda *a: None
        return chamadas, {"yt_dlp": mod, "yt_dlp.utils": utils}

    def test_tenta_de_novo_e_usa_formato_simples(self):
        chamadas, mods = self._falso_ytdlp(falhas=2)
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(sys.modules, mods), \
                mock.patch("time.sleep"), mock.patch.object(cortes, "duracao_video", return_value=30.0):
            arq, meta = cortes.baixar_trecho("https://x", 10, 40, Path(d))
            self.assertEqual(arq.name, "original.mp4")
            self.assertEqual(meta["canal"], "Canal")
            self.assertFalse(list(Path(d).glob("*.part")))
        self.assertEqual(len(chamadas), 3)
        self.assertEqual(chamadas[0]["format"], "bv*+ba/b")
        self.assertTrue(chamadas[2]["format"].startswith("b[ext=mp4]"))   # plano B: arquivo único

    def test_erro_definitivo_nao_insiste(self):
        chamadas, mods = self._falso_ytdlp(falhas=9, erro="ERROR: Private video")
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(sys.modules, mods), mock.patch("time.sleep"):
            with self.assertRaises(RuntimeError):
                cortes.baixar_trecho("https://x", 10, 40, Path(d))
        self.assertEqual(len(chamadas), 1)


class Gancho(unittest.TestCase):
    def test_repeticao_do_comeco(self):
        textos = ["olha", "isso", "aqui", "galera", "mano", "olha", "isso", "aqui", "galera"]
        pal = _pal(textos, 1.5)
        self.assertTrue(cortes.gancho_repete_inicio(pal, textos, 7.4, 12.4))

    def test_momento_novo_vale(self):
        textos = ["bom", "dia", "pessoal", "hoje", "vamos", "falar"] + ["filler"] * 20 + \
                 ["ninguém", "acreditou", "nessa", "resposta"]
        pal = _pal(textos)
        a = pal[26]["ini"] - 0.1
        self.assertFalse(cortes.gancho_repete_inicio(pal, textos, a, a + 2.2))


class NotaAutomatico(unittest.TestCase):
    def test_padrao_e_config(self):
        cfg = dict(cortes.carregar_config(), nota_minima_automatico=7, musica_volume="x")
        cortes.aplicar_config(cfg)
        self.assertEqual(cortes.NOTA_MINIMA_AUTO, 7)
        self.assertEqual(cortes.MUSICA_VOLUME, 0.16)
        cortes.aplicar_config(cortes.carregar_config())


class Musica(unittest.TestCase):
    def test_escolha_por_clima_sem_repetir(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            musica.garantir_pastas(p)
            self.assertIsNone(musica.escolher("humor", pasta=p))
            for n in ("a.mp3", "b.mp3"):
                (p / "tensa" / n).write_bytes(b"0" * 30_000)
            (p / "solta.mp3").write_bytes(b"0" * 30_000)
            rng = random.Random(1)
            e1 = musica.escolher("polemica", pasta=p, rng=rng)
            e2 = musica.escolher("polemica", pasta=p, rng=rng)
            self.assertEqual({e1.parent.name, e2.parent.name}, {"tensa"})
            self.assertNotEqual(e1, e2)
            self.assertEqual(musica.escolher("humor", pasta=p).name, "solta.mp3")   # pasta vazia → soltas
            self.assertTrue((p / "LEIA-ME.txt").exists())

    def test_render_com_ducking(self):
        cortes.aplicar_config(dict(cortes.carregar_config(), estilo_corte="clean"))
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            v = p / "video.mp4"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=4",
                            "-f", "lavfi", "-i", "sine=f=300:d=4", "-shortest", "-c:v", "libx264",
                            "-preset", "ultrafast", "-c:a", "aac", str(v)], check=True)
            m = p / "musica.wav"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=f=660:d=1.5", str(m)],
                           check=True)
            saida = p / "saida.mp4"
            cortes.renderizar(v, None, None, saida, "cortado",
                              estilo_render={"musica": {"arquivo": str(m), "vol": 0.2}})
            self.assertTrue(saida.exists())
            self.assertTrue(cortes.tem_audio(saida))
            self.assertAlmostEqual(cortes.duracao_video(saida), 4.0, delta=0.3)   # loop não estica o vídeo
        cortes.aplicar_config(cortes.carregar_config())


class TamanhoLegenda(unittest.TestCase):
    def test_piso_por_template(self):
        import templates_edicao as te
        noticia = te.resolver("Notícia")["legenda"]
        self.assertEqual(te.tamanho_legenda(78, noticia), 66)      # 78×0.82=64 → piso 66
        self.assertEqual(te.tamanho_legenda(55, noticia), 55)      # não passa do tamanho do perfil
        self.assertEqual(te.tamanho_legenda(100, noticia), 82)
        self.assertEqual(te.tamanho_legenda(78, te.resolver("Hormozi")["legenda"]), 98)
        for nome in te.TEMPLATES:
            self.assertGreaterEqual(te.tamanho_legenda(78, te.resolver(nome)["legenda"]), 62, nome)


if __name__ == "__main__":
    unittest.main()
