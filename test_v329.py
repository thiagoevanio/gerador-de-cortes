"""3.29: voz limpa com IA (RNNoise), nitidez sempre que o vídeo é esticado (medida com VMAF/SSIM),
medidor de qualidade e 'tirar a música da fonte' (Demucs)."""
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

import cortes
import qualidade
import render
import separar_voz
import templates_edicao as te


def _rms_db(caminho):
    with wave.open(str(caminho)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype("float64") / 32768
    return 20 * np.log10(np.sqrt((a ** 2).mean()) + 1e-12)


class VozLimpa(unittest.TestCase):
    def test_rnnoise_ligado_desligado_e_no_jogo(self):
        cfg = dict(cortes.carregar_config(), limpar_voz_ia=True, reduzir_chiado=True)
        with patch.object(cortes, "carregar_config", return_value=cfg):
            self.assertIn("arnndn=m='", cortes.filtro_limpeza_voz())
            self.assertIn("rnnoise_voz.rnnn'", cortes.filtro_limpeza_voz())
            self.assertEqual(cortes.filtro_limpeza_voz(jogo=True), ",afftdn=nf=-25")   # som do jogo fica
        with patch.object(cortes, "carregar_config", return_value=dict(cfg, limpar_voz_ia=False)):
            self.assertEqual(cortes.filtro_limpeza_voz(), ",afftdn=nf=-25")

    def test_tira_muito_mais_ruido_que_o_filtro_antigo(self):
        with tempfile.TemporaryDirectory() as d:
            ruido = Path(d) / "ruido.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                            "anoisesrc=color=pink:amplitude=0.05:sample_rate=48000:d=5", "-ac", "1", str(ruido)],
                           check=True)
            base = _rms_db(ruido)
            saidas = {}
            for nome, f in (("rnn", cortes.filtro_limpeza_voz().lstrip(",")), ("antigo", "afftdn=nf=-25")):
                out = Path(d) / f"{nome}.wav"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ruido), "-filter_complex",
                                f"[0:a]{f}[o]", "-map", "[o]", "-ac", "1", str(out)], check=True)
                saidas[nome] = base - _rms_db(out)
        self.assertGreater(saidas["rnn"], 15)                 # medido: ~28 dB
        self.assertGreater(saidas["rnn"], saidas["antigo"] + 10)

    def _render_grafo(self, er):
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            video = pasta / "v.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25",
                            "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=48000", "-t", "3",
                            "-c:v", "libx264", "-c:a", "aac", str(video)], check=True)
            comandos, rodar_de_verdade = [], cortes.rodar

            def rodar(cmd, **k):
                if "-filter_complex" not in cmd:               # ffprobe/duração: roda normal
                    return rodar_de_verdade(cmd, **k)
                comandos.append(cmd)
                raise RuntimeError("parou aqui")
            with patch.object(cortes, "rodar", rodar), self.assertRaises(RuntimeError):
                render.renderizar(video, None, None, pasta / "saida.mp4", "cortado", estilo_render=er)
        return comandos[0][comandos[0].index("-filter_complex") + 1]

    def test_render_nunca_usa_rnnoise_e_nao_limpa_duas_vezes(self):
        """O arnndn trava às vezes no fechamento do FFmpeg: no render final ele não entra nunca. Se a voz
        já veio limpa do começo do corte, o afftdn também não (só tiraria brilho)."""
        cfg = dict(cortes.carregar_config(), reduzir_chiado=True, audio_padrao=True)
        with patch.object(cortes, "carregar_config", return_value=cfg), patch.object(cortes, "AUDIO_PADRAO", True):
            ja_limpa = self._render_grafo({"voz_limpa": True})
            sem = self._render_grafo({})
        self.assertNotIn("arnndn", ja_limpa + sem)
        self.assertNotIn("afftdn", ja_limpa)
        self.assertIn("afftdn", sem)


def _wav(destino, tipo, segundos=12, sr=48000):
    """'fala': ruído modulado como sílabas + chiado de fundo; 'jogo': estrondos altos sem voz."""
    rng = np.random.default_rng(3)
    t = np.arange(sr * segundos) / sr
    if tipo == "fala":
        silabas = (np.sin(2 * np.pi * 4 * t) > 0).astype(float)
        a = 0.25 * np.sin(2 * np.pi * 180 * t) * silabas * (1 + 0.5 * np.sin(2 * np.pi * 900 * t))             + rng.normal(0, 0.01, len(t))
    else:
        a = rng.normal(0, 0.3, len(t)) * (np.mod(t, 1.0) < 0.7)
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
    return destino


class PassoDeLimpeza(unittest.TestCase):
    def test_tenta_de_novo_quando_o_ffmpeg_trava(self):
        with tempfile.TemporaryDirectory() as d:
            entrada = _wav(Path(d) / "e.wav", "fala", 3)
            de_verdade, chamadas = subprocess.run, []

            def run(cmd, **k):
                chamadas.append(cmd)
                if len(chamadas) == 1:                 # 1ª vez: "travou" sem deixar arquivo
                    return subprocess.CompletedProcess(cmd, 3221225477)
                return de_verdade(cmd, **k)
            with patch.object(separar_voz.subprocess, "run", run):
                self.assertTrue(separar_voz._rodar_rnnoise(entrada, Path(d) / "s.wav"))
        self.assertEqual(len(chamadas), 2)

    def test_jogo_ou_musica_mantem_o_som_original(self):
        with tempfile.TemporaryDirectory() as d:
            jogo = _wav(Path(d) / "jogo.wav", "jogo")
            limpo = Path(d) / "jogo_limpo.wav"
            self.assertTrue(separar_voz._rodar_rnnoise(jogo, limpo))
            self.assertGreaterEqual(separar_voz.parte_que_some(jogo, limpo), 0.4)


class Nitidez(unittest.TestCase):
    def test_entra_sempre_que_estica(self):
        e = {"nitidez": True}
        self.assertIn("unsharp", te.filtro_cor(e, 1080, 1.78))      # 1080p cortado pro 9:16 (antes: sem)
        self.assertIn("unsharp", te.filtro_cor(e, 720, 2.67))
        self.assertNotIn("unsharp", te.filtro_cor(e, 1080, 0.56))   # vídeo inteiro reduzido: não precisa
        self.assertNotIn("unsharp", te.filtro_cor({"nitidez": False}, 720, 2.67))
        self.assertIn("unsharp", te.filtro_cor(e, 720))             # chamada antiga continua igual

    def test_medidor_confirma_a_escolha(self):
        """A régua da 3.29: com a nitidez o VMAF sobe e o SSIM praticamente não cai."""
        cortes.checar_ffmpeg()
        with tempfile.TemporaryDirectory() as d:
            ref, baixa = Path(d) / "ref.mp4", Path(d) / "baixa.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=25",
                            "-t", "1", "-c:v", "libx264", "-crf", "10", str(ref)], check=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ref), "-vf", "scale=1080:608",
                            "-c:v", "libx264", "-crf", "23", str(baixa)], check=True)
            sem = "scale=1920:1080:flags=lanczos"
            com = sem + te.filtro_cor({"nitidez": True}, 1080, 1.78)
            v_sem, v_com = (qualidade.comparar(baixa, ref, f) for f in (sem, com))
            s_sem, s_com = (qualidade.comparar(baixa, ref, f, "ssim") for f in (sem, com))
        self.assertIsNotNone(v_sem)
        self.assertGreater(v_com, v_sem)
        self.assertGreater(s_com, s_sem - 0.01)


class TirarMusica(unittest.TestCase):
    def test_sem_a_ia_instalada_segue_com_o_som_original(self):
        with patch.object(separar_voz, "instalado", return_value=False):
            self.assertIsNone(separar_voz.tirar_musica(Path("x.mp4"), Path("."), log=lambda *_: None))

    def test_desligado_por_padrao(self):
        self.assertFalse(cortes.CONFIG_PADRAO["tirar_musica_fonte"])
        self.assertTrue(cortes.CONFIG_PADRAO["limpar_voz_ia"])

    @unittest.skipUnless(separar_voz.instalado(), "Demucs não instalado neste PC")
    def test_musica_some_e_a_voz_fica(self):
        sr = 44100
        t = np.arange(sr * 6) / sr
        musica = (0.12 * (np.sin(2 * np.pi * 220 * t) + np.sin(2 * np.pi * 277 * t) + np.sin(2 * np.pi * 330 * t))
                  + 0.5 * np.exp(-30 * np.mod(t, 0.5)) * np.sin(2 * np.pi * 60 * t)).astype("float32")
        audio = np.stack([musica, musica])
        voz = separar_voz.so_a_voz(audio)
        queda = 20 * np.log10(np.sqrt((voz ** 2).mean()) / np.sqrt((audio ** 2).mean()) + 1e-12)
        self.assertLess(queda, -20)                            # medido: ~-33 dB


if __name__ == "__main__":
    unittest.main()
