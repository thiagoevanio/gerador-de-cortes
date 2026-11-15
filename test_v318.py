"""3.18: desempenho — rostos em sequência, chip de vídeo no recorte/intermediários (com decodificação),
lives checadas em paralelo, progresso com tempo restante, tempos por etapa, limpeza de disco e modo PC fraco."""
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import cortes
import desempenho
import efeitos


class Rostos(unittest.TestCase):
    def test_leitura_em_sequencia_pega_as_mesmas_amostras(self):
        import cv2
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "v.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x240:r=30:d=3",
                            "-c:v", "libx264", "-g", "90", str(v)], check=True)
            cap = cv2.VideoCapture(str(v))
            idx = [i for i, _f in efeitos.amostras_video(cap, 0.5)]
            cap.release()
        self.assertEqual(idx, list(range(0, 90, 15)))

    def test_nao_pula_mais_no_video(self):
        codigo = Path(efeitos.__file__).read_text(encoding="utf-8")
        self.assertNotIn("cap.set(cv2.CAP_PROP_POS_FRAMES", codigo)


class ChipDeVideo(unittest.TestCase):
    def test_decodificador_so_nos_videos_de_entrada(self):
        cmd = ["ffmpeg", "-y", "-i", "a.mp4", "-loop", "1", "-i", "topo.png", "-i", "boom.wav",
               "-c:v", "h264_qsv", "-global_quality", "19", "saida.mp4"]
        with patch.object(cortes, "_decodificar_hw", True):
            novo = cortes._com_decodificador_hw(cmd)
        self.assertEqual(novo[2:5], ["-hwaccel", "qsv", "-i"])
        self.assertEqual(novo.count("-hwaccel"), 1)
        self.assertEqual(cortes._sem_hwaccel(novo), cmd)

    def test_sem_encoder_de_hardware_nao_mexe(self):
        cmd = ["ffmpeg", "-i", "a.mp4", "-c:v", "libx264", "s.mp4"]
        self.assertEqual(cortes._com_decodificador_hw(cmd), cmd)

    def test_volta_pro_processador_se_o_chip_nao_decodificar(self):
        chamadas = []

        def executar(cmd, cwd=None, progresso=None):
            chamadas.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 1 if "-hwaccel" in cmd else 0, "", "erro")
        with patch.object(cortes, "_executar", side_effect=executar), patch.object(cortes, "_decodificar_hw", True):
            cortes.rodar(["ffmpeg", "-y", "-i", "a.mp4", "-c:v", "h264_qsv", "-global_quality", "19", "s.mp4"])
            self.assertFalse(cortes._decodificar_hw)
        self.assertIn("-hwaccel", chamadas[0])
        self.assertNotIn("-hwaccel", chamadas[1])
        self.assertIn("h264_qsv", chamadas[1])                 # o encoder do chip continua

    def test_intermediario_usa_o_chip(self):
        with patch.object(cortes, "_encoder_h264_cache", "h264_qsv"):
            self.assertEqual(cortes.args_encoder_video(intermediario=True), ["-c:v", "h264_qsv", "-global_quality", "17"])
        with patch.object(cortes, "_encoder_h264_cache", "libx264"):
            self.assertIn("ultrafast", cortes.args_encoder_video(intermediario=True))

    def test_recorte_usa_o_encoder_escolhido(self):
        codigo = Path(cortes.__file__).read_text(encoding="utf-8")
        self.assertNotIn('"-c:v", "libx264", "-preset", "veryfast", "-crf", "20"', codigo)


class Progresso(unittest.TestCase):
    def test_avisa_quanto_falta(self):
        avisos = []
        with tempfile.TemporaryDirectory() as d, patch.object(cortes, "log", side_effect=avisos.append):
            r = cortes._executar(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=8", "-c:v", "libx264",
                                  "-preset", "slow", str(Path(d) / "s.mp4")], progresso=("Montando", 8))
        self.assertEqual(r.returncode, 0)
        self.assertTrue(avisos, "nenhum aviso de progresso")
        self.assertRegex(avisos[0], r"^Montando: \d+% \(falta ~\d+")


class Tempos(unittest.TestCase):
    def test_soma_as_etapas(self):
        m = [(0, "Aguardando o renderizador..."), (1, "Recortando o trecho do arquivo..."), (11, "Recortando: 50% (falta ~5 s)"),
             (16, "Transcrevendo o áudio no processador..."), (36, "Olhando os rostos do vídeo..."),
             (50, "Montando o vídeo 9:16"), (70, "Montando o vídeo: 50% (falta ~20 s)")]
        e = cortes.etapas_do_log(m, fim=90)
        self.assertEqual(e, {"espera": 1, "recortar": 15, "legenda": 20, "rostos": 14, "montagem": 40})

    def test_registra_e_resume(self):
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "tempos.jsonl"
            agora = time.time()
            for _ in range(3):
                cortes.registrar_tempos([(agora - 60, "Aguardando"), (agora - 50, "Olhando os rostos")], "x.mp4", 45, arquivo=arq)
            t = desempenho.tempos_recentes(arquivo=arq)
        self.assertEqual(t["cortes"], 3)
        self.assertAlmostEqual(t["etapas"]["rostos"], 50, delta=1)
        self.assertIn("olhar os rostos", desempenho.texto_tempos(t))


class Disco(unittest.TestCase):
    def test_apaga_so_projeto_antigo(self):
        with tempfile.TemporaryDirectory() as d:
            saida = Path(d)
            velho, novo = saida / "_edicao" / "velho", saida / "_edicao" / "novo"
            for p in (velho, novo):
                p.mkdir(parents=True)
                (p / "com_gancho.mp4").write_bytes(b"x" * 1000)
            antigo = time.time() - 40 * 86400
            for f in (velho, velho / "com_gancho.mp4"):
                os.utime(f, (antigo, antigo))
            (saida / "corte.mp4").write_bytes(b"pronto")
            n, livres = desempenho.limpar_projetos_edicao(saida, 30)
            self.assertEqual((n, livres), (1, 1000))
            self.assertFalse(velho.exists())
            self.assertTrue(novo.exists())
            self.assertTrue((saida / "corte.mp4").exists())
            self.assertEqual(desempenho.limpar_projetos_edicao(saida, 0), (0, 0))   # 0 = nunca apagar

    def test_restos_de_tarefa(self):
        with tempfile.TemporaryDirectory() as d:
            resto = Path(d) / "_trabalho" / "tarefa_abc"
            resto.mkdir(parents=True)
            self.assertEqual(desempenho.limpar_trabalho(Path(d))[0], 0)          # recente: tarefa em andamento
            self.assertEqual(desempenho.limpar_trabalho(Path(d), agora=time.time() + 13 * 3600)[0], 1)

    def test_relatorio(self):
        self.assertIn("Livre no disco", desempenho.texto_disco())


class Lives(unittest.TestCase):
    def test_checa_em_paralelo_e_na_ordem(self):
        import monitor

        def lento(canal, url):
            time.sleep(0.4)
            return {"title": canal}
        lista = [(f"k{i}", f"c{i}", "twitch", f"u{i}") for i in range(4)]
        with patch.object(monitor, "info_live", side_effect=lento):
            t = time.time()
            r = monitor.checar_lives(lista)
        self.assertLess(time.time() - t, 1.0)
        self.assertEqual([x["title"] for x in r], ["c0", "c1", "c2", "c3"])
        self.assertEqual(monitor.checar_lives([]), [])


class PcFraco(unittest.TestCase):
    def test_whisper_base_e_720p(self):
        cfg = dict(cortes.carregar_config(), modo_pc_fraco=True)
        cfg.pop("whisper_final", None)
        with patch.object(cortes, "carregar_config", return_value=cfg), patch.object(cortes, "MODELO_WHISPER", "auto"):
            self.assertEqual(cortes.modelo_final(), "base")
        anterior = (cortes.BAIXAR_1080, cortes.MODO_PC_FRACO)
        try:
            cortes.aplicar_config(dict(cfg, baixar_1080=True))
            self.assertFalse(cortes.BAIXAR_1080)
            self.assertTrue(cortes.MODO_PC_FRACO)
        finally:
            cortes.aplicar_config()
        self.assertEqual((cortes.BAIXAR_1080, cortes.MODO_PC_FRACO), anterior)


if __name__ == "__main__":
    unittest.main()
