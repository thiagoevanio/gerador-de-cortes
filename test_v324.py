"""3.24: aba Legendar — só legenda num vídeo já editado (vertical, horizontal ou quadrado)."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cortes
import legendar


def _p(textos, passo=0.5):
    return [{"t": t, "ini": round(i * passo, 2), "fim": round(i * passo + passo * 0.8, 2)} for i, t in enumerate(textos)]


def _video(pasta, w, h, d=4.0, r=30, audio=True):
    v = Path(pasta) / f"v_{w}x{h}.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x335577:s={w}x{h}:r={r}:d={d}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=f=300:d={d}", "-shortest", "-c:a", "aac"]
    subprocess.run(cmd + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", str(v)], check=True)
    return v


class Tela(unittest.TestCase):
    def test_lado_menor_vira_1080(self):
        self.assertEqual(legendar.tela(1080, 1920), (1080, 1920))
        self.assertEqual(legendar.tela(1920, 1080), (1920, 1080))
        self.assertEqual(legendar.tela(720, 1280), (1080, 1920))
        self.assertEqual(legendar.tela(1280, 720), (1920, 1080))
        self.assertEqual(legendar.tela(1080, 1080), (1080, 1080))

    def test_ass_na_tela_do_video(self):
        with tempfile.TemporaryDirectory() as d:
            ass = legendar.montar_ass(_p(["oi", "tudo", "bem"]), Path(d) / "l.ass",
                                      {"largura": 1920, "altura": 1080, "duracao": 3}, legendar.opcoes_padrao())
            texto = ass.read_text(encoding="utf-8")
        self.assertIn("PlayResX: 1920", texto)
        self.assertIn("PlayResY: 1080", texto)


class Revisao(unittest.TestCase):
    PAL = _p("ele falou que a casa já tinha sido vendida. eu não acreditei nisso cara".split())

    def test_texto_com_tempo_por_frase(self):
        texto = legendar.texto_para_revisar(self.PAL)
        self.assertTrue(texto.splitlines()[0].startswith("[00:00] ele falou"))
        self.assertEqual(len(texto.splitlines()), len(legendar.frases(self.PAL)))

    def test_mesma_quantidade_mantem_o_tempo(self):
        linhas = legendar.texto_para_revisar(self.PAL).splitlines()
        linhas[0] = linhas[0].replace("casa", "CASA")
        novas = legendar.aplicar_revisao(self.PAL, "\n".join(linhas))
        self.assertEqual([p["ini"] for p in novas], [p["ini"] for p in self.PAL])
        self.assertIn("CASA", [p["t"] for p in novas])

    def test_quantidade_diferente_redivide_o_tempo(self):
        linhas = legendar.texto_para_revisar(self.PAL).splitlines()
        g = legendar.frases(self.PAL)[0]
        linhas[0] = "[00:00] ELE DISSE"
        novas = legendar.aplicar_revisao(self.PAL, "\n".join(linhas))
        self.assertEqual([p["t"] for p in novas[:2]], ["ELE", "DISSE"])
        self.assertAlmostEqual(novas[0]["ini"], self.PAL[g[0]]["ini"])
        self.assertLessEqual(novas[1]["fim"], self.PAL[g[-1]]["fim"] + 1e-6)
        self.assertLess(novas[0]["fim"], novas[1]["ini"] + 1e-6)

    def test_linha_so_com_tempo_tira_a_frase(self):
        linhas = legendar.texto_para_revisar(self.PAL).splitlines()
        linhas[1] = "[00:05]"
        novas = legendar.aplicar_revisao(self.PAL, "\n".join(linhas))
        self.assertNotIn("acreditei", [p["t"] for p in novas])

    def test_linha_a_mais_ou_a_menos_avisa(self):
        texto = legendar.texto_para_revisar(self.PAL)
        with self.assertRaises(ValueError):
            legendar.aplicar_revisao(self.PAL, texto + "\nlinha nova")
        with self.assertRaises(ValueError):
            legendar.aplicar_revisao(self.PAL, texto.splitlines()[0])

    def test_tira_muletas_so_da_legenda(self):
        pal = _p(["hum", "ele", "éé", "falou"])
        self.assertEqual([p["t"] for p in legendar.sem_muletas(pal)], ["ele", "falou"])


class IA(unittest.TestCase):
    def test_correcao_e_enfase_com_trava(self):
        pal = _p(["o", "Renato", "Cariane", "quase", "comprou", "a", "casa", "do", "vizinho"])
        resp = {"correcoes": {"1": "Renato Cariani", "2": "Cariani"}, "enfase": [0, 2, 4]}
        with patch.object(cortes, "IA_PRINCIPAL", "claude"), patch.object(cortes, "ia_json", return_value=resp):
            novas = legendar.melhorar_com_ia(pal, log=lambda t: None)
        self.assertEqual(" ".join(p["t"] for p in novas), "o Renato Cariani quase comprou a casa do vizinho")
        self.assertEqual([p["t"] for p in novas if p.get("enfase")], ["Cariani"])   # 1 a cada ~8 e palavra forte

    def test_sem_ia_nao_chama(self):
        with patch.object(cortes, "IA_PRINCIPAL", "nenhuma"), patch.object(cortes, "ia_json") as ia:
            legendar.melhorar_com_ia(_p(["oi"]), log=lambda t: None)
        ia.assert_not_called()


class Video(unittest.TestCase):
    def test_queima_mantendo_formato_fps_e_audio(self):
        with tempfile.TemporaryDirectory() as d:
            for w, h, r in ((1920, 1080, 30), (720, 1280, 60)):
                v = _video(d, w, h, r=r)
                saida = legendar.queimar(v, _p(["legenda", "de", "teste", "aqui"]), legendar.opcoes_padrao(),
                                         log=lambda t: None)
                vi = legendar.info(saida)
                self.assertEqual((vi["largura"], vi["altura"]), (w, h))
                self.assertAlmostEqual(vi["fps"], r, delta=0.5)
                self.assertEqual(vi["audio"], "aac")
                self.assertTrue(saida.name.endswith("_legendado.mp4"))
                self.assertTrue(saida.with_suffix(".srt").exists())
                self.assertEqual(legendar.saida_para(v).name, v.stem + "_legendado_2.mp4")   # não sobrescreve

    def test_video_previa_leve_pra_assistir(self):
        with tempfile.TemporaryDirectory() as d, patch.object(legendar, "PASTA_PREVIAS", Path(d) / "previas"):
            v = _video(d, 1920, 1080, d=6)
            p = legendar.video_previa(v, _p(["oi", "tudo", "bem"]), legendar.opcoes_padrao(), log=lambda t: None,
                                      limite_s=3)
            vi = legendar.info(p)
            self.assertEqual(vi["altura"], 540)                   # leve: lado menor 540
            self.assertAlmostEqual(vi["duracao"], 3, delta=0.3)   # vídeo longo: só o começo
            self.assertEqual(vi["audio"], "aac")
            self.assertTrue(v.exists())                           # o original não é tocado

    def test_previa_do_proprio_video(self):
        with tempfile.TemporaryDirectory() as d:
            img = legendar.previa(_video(d, 1080, 1920), legendar.opcoes_padrao(), largura_saida=200)
        self.assertGreater(img.height, img.width)

    def test_sem_audio_avisa(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "não tem áudio"):
                legendar.transcrever(_video(d, 640, 360, audio=False), d)


class Aba(unittest.TestCase):
    def test_aba_na_interface(self):
        codigo = Path("interface.py").read_text(encoding="utf-8")
        self.assertIn('abas.add(self.aba_legendar, text="  📝 Legendar  ")', codigo)
        self.assertIn("aba_legendar.montar(self, self.aba_legendar)", codigo)


if __name__ == "__main__":
    unittest.main()
