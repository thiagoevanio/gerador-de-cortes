"""3.21: qualidade de vídeo e edição — mais bitrate no final (look-ahead), menos recompressões
(gancho direto na montagem, intermediários quase sem perda), 60 fps automático, loudnorm em
2 passadas, exposição automática e zoom lento."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cortes
import desempenho
import efeitos
import render
import templates_edicao as te


def _video(pasta, dur=6.0, r=30, escuro=False, audio=True):
    v = Path(pasta) / f"v{r}.mp4"
    fonte = f"color=c=0x202020:s=320x240:r={r}:d={dur}" if escuro else f"testsrc2=s=320x240:r={r}:d={dur}"
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", fonte]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=f=300:d={dur}", "-shortest", "-c:a", "aac"]
    subprocess.run(cmd + ["-c:v", "libx264", "-preset", "ultrafast", str(v)], check=True)
    return v


class Encoder(unittest.TestCase):
    def test_final_usa_look_ahead_quando_da(self):
        with patch.object(cortes, "_encoder_h264_cache", "h264_qsv"), \
                patch.object(desempenho, "_look_ahead_cache", True):
            self.assertEqual(cortes.args_encoder_video(),
                             ["-c:v", "h264_qsv", "-global_quality", "19", "-look_ahead", "1"])
        with patch.object(cortes, "_encoder_h264_cache", "h264_qsv"), \
                patch.object(desempenho, "_look_ahead_cache", False):
            self.assertEqual(cortes.args_encoder_video(), ["-c:v", "h264_qsv", "-global_quality", "15"])

    def test_intermediario_quase_sem_perda(self):
        with patch.object(cortes, "_encoder_h264_cache", "h264_qsv"):
            self.assertEqual(cortes.args_encoder_video(intermediario=True),
                             ["-c:v", "h264_qsv", "-global_quality", "15"])

    def test_fallback_tira_o_look_ahead_inteiro(self):
        cmd = ["ffmpeg", "-y", "-i", "a.mp4", "-c:v", "h264_qsv", "-global_quality", "19",
               "-look_ahead", "1", "-pix_fmt", "yuv420p", "s.mp4"]
        hw = cmd.index("-c:v")
        novo = cmd[:hw] + ["-c:v", "libx264"] + cmd[cortes._fim_args_encoder(cmd, hw):]
        self.assertNotIn("-look_ahead", novo)
        self.assertNotIn("-global_quality", novo)
        self.assertIn("-pix_fmt", novo)

    def test_recorte_e_trecho_sao_intermediarios(self):
        self.assertNotIn('args_encoder_video(crf_padrao=20)', Path("cortes.py").read_text(encoding="utf-8"))
        self.assertIn("args_encoder_video(intermediario=True)", Path("baixador.py").read_text(encoding="utf-8"))


class Fps(unittest.TestCase):
    def test_segue_a_fonte_60(self):
        with tempfile.TemporaryDirectory() as d:
            v60, v30 = _video(d, 1, 60, audio=False), _video(d, 1, 30, audio=False)
            self.assertEqual(render.fps_saida(v60), 60)
            self.assertEqual(render.fps_saida(v30), 30)
            with patch.object(cortes, "MODO_PC_FRACO", True):
                self.assertEqual(render.fps_saida(v60), 30)


class Previa(unittest.TestCase):
    def test_gancho_dentro_da_montagem(self):
        """A prévia [4s, 6s] entra no começo SEM re-encode: a saída dura 2 s a mais que a fonte."""
        cortes.aplicar_config(dict(cortes.carregar_config(), estilo_corte="clean", musica_fundo=False))
        try:
            with tempfile.TemporaryDirectory() as d:
                v = _video(d, 8.0)
                saida = Path(d) / "s.mp4"
                cortes.renderizar(v, None, None, saida, "cortado", gancho_t=4.0, previa=(4.0, 6.0))
                self.assertAlmostEqual(cortes.duracao_video(saida), 10.0, delta=0.4)
                self.assertTrue(cortes.tem_audio(saida))
                self.assertTrue(list(Path(d).glob("whoosh_*.wav")))  # som da virada, gerado pelo render
        finally:
            cortes.aplicar_config(cortes.carregar_config())

    def test_pipeline_nao_recomprime_mais_o_gancho(self):
        codigo = Path("cortes.py").read_text(encoding="utf-8")
        self.assertNotIn("efeitos.prefixar_gancho(", codigo)
        self.assertIn("previa=previa_gancho", codigo)


class Loudnorm(unittest.TestCase):
    def test_duas_passadas_mede_e_aplica_linear(self):
        with tempfile.TemporaryDirectory() as d:
            ln = render._loudnorm_medido(_video(d, 4.0))
        self.assertIn("linear=true", ln)
        self.assertIn("measured_I=", ln)

    def test_sem_medida_volta_pro_dinamico(self):
        self.assertEqual(render._loudnorm_medido(Path("nao_existe.mp4")),
                         "loudnorm=I=-14:TP=-1.5:LRA=11")


class Exposicao(unittest.TestCase):
    def test_levanta_video_escuro_e_deixa_o_claro(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("eq=gamma=", efeitos.correcao_exposicao(_video(d, 12.0, escuro=True, audio=False)))
            self.assertEqual(efeitos.correcao_exposicao(_video(d, 12.0, audio=False)), "")


class ZoomLento(unittest.TestCase):
    def test_chave_no_template(self):
        self.assertEqual(te.resolver("Clássico")["efeitos"]["zoom_lento"], 0.0)
        self.assertEqual(te.resolver("Podcast Premium")["efeitos"]["zoom_lento"], 0.05)


if __name__ == "__main__":
    unittest.main()
