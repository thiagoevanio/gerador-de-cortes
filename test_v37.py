"""Testes da v3.7: Otimizador Local de Cortes, Delta de Palavras, Reconciliador Tolerante, Gancho Multimodal e Performance."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import cortes
import efeitos
import otimizador_corte


class OtimizadorTokens(unittest.TestCase):
    def test_delta_esparso_por_indice_e_termo(self):
        palavras = [
            {"t": "o", "ini": 0.0, "fim": 0.2},
            {"t": "gaules,", "ini": 0.2, "fim": 0.6},
            {"t": "falou", "ini": 0.6, "fim": 1.0},
            {"t": "com", "ini": 1.0, "fim": 1.2},
            {"t": "caze.", "ini": 1.2, "fim": 1.7},
        ]
        reconciliadas, metodo = otimizador_corte.reconciliar_palavras_ia(
            palavras, lista_ia=None, correcoes={"1": "Gaules", "caze": "Casimiro"}
        )
        self.assertEqual(metodo, "delta_esparso")
        self.assertEqual(reconciliadas, ["o", "Gaules,", "falou", "com", "Casimiro."])

    def test_alinhamento_tolerante_quando_ia_muda_contagem(self):
        palavras = [
            {"t": "Salve", "ini": 0.0, "fim": 0.3},
            {"t": "gaules", "ini": 0.3, "fim": 0.7},
            {"t": "da", "ini": 0.7, "fim": 0.9},
            {"t": "loud", "ini": 0.9, "fim": 1.3},
            {"t": "hoje", "ini": 1.3, "fim": 1.6},
            {"t": "né", "ini": 1.6, "fim": 1.9},
        ]
        lista_ia_incompleta = ["Salve,", "Gaules", "da", "LOUD!", "hoje"]
        reconciliadas, metodo = otimizador_corte.reconciliar_palavras_ia(palavras, lista_ia=lista_ia_incompleta)
        self.assertEqual(metodo, "alinhamento_tolerante")
        self.assertEqual(len(reconciliadas), len(palavras))
        self.assertEqual(reconciliadas[1], "Gaules")
        self.assertEqual(reconciliadas[3], "LOUD!")

    def test_validar_dados_aceita_correcoes_sem_lista_completa(self):
        palavras = [{"t": "ele", "ini": 0.0, "fim": 0.3}, {"t": "gaules", "ini": 0.3, "fim": 0.8}]
        padrao = {"palavras": ["ele", "gaules"], "pergunta": "P??", "destaque": [], "titulo": "T",
                  "hashtags": [], "foto": None, "emoji": "😱", "nota": 8, "gancho": None}
        dados = cortes._validar_dados({"pergunta": "VIU ISSO??", "correcoes": {"1": "Gaules"}}, padrao, palavras, None)
        self.assertEqual(dados["palavras"], ["ele", "Gaules"])


class InteligenciaLocalZeroToken(unittest.TestCase):
    def test_achar_gancho_multimodal_semantico_e_acustico(self):
        palavras = [
            {"t": "a", "ini": 0.5, "fim": 1.0},
            {"t": "gente", "ini": 1.0, "fim": 1.8},
            {"t": "estava", "ini": 2.0, "fim": 3.0},
            {"t": "conversando", "ini": 4.0, "fim": 5.0},
            {"t": "normal", "ini": 5.0, "fim": 6.0},
            {"t": "descobri", "ini": 7.0, "fim": 7.6},
            {"t": "segredo!", "ini": 7.6, "fim": 8.4},
            {"t": "fim", "ini": 10.0, "fim": 11.0},
        ]
        sr = 16000
        audio = np.ones(sr * 12, dtype=np.float32) * 0.05
        audio[sr * 7:sr * 9] = 0.45
        idx = otimizador_corte.achar_gancho_multimodal(palavras, audio=audio, sr=sr)
        self.assertIn(idx, (5, 6))

    def test_gerar_pergunta_local_contextualizada(self):
        palavras = [
            {"t": "Ele", "ini": 0.0, "fim": 0.3},
            {"t": "revelou", "ini": 0.3, "fim": 0.7},
            {"t": "o", "ini": 0.7, "fim": 0.9},
            {"t": "segredo", "ini": 0.9, "fim": 1.4},
            {"t": "do", "ini": 1.4, "fim": 1.6},
            {"t": "jogo!", "ini": 1.6, "fim": 2.1},
        ]
        res = otimizador_corte.gerar_pergunta_local(palavras, {"titulo": "Podcast"})
        self.assertTrue(res["pergunta"].endswith("??"))
        self.assertIn("SEGREDO", res["pergunta"])
        self.assertTrue(res["destaque"])

    def test_analisar_ritmo_retencao(self):
        palavras = [{"t": f"p{i}", "ini": round(i * 0.35, 2), "fim": round(i * 0.35 + 0.28, 2)} for i in range(40)]
        rel = otimizador_corte.analisar_ritmo_retencao(palavras, 14.5)
        self.assertGreaterEqual(rel["nota_retencao"], 80.0)
        self.assertEqual(rel["buracos_ritmo"], 0)

    def test_camera_rejeita_falso_pico_isolado(self):
        valores = [0.30, 0.31, 0.95, 0.30, 0.31]
        suave = efeitos._suavizar_segmento_camera(valores)
        self.assertTrue(all(abs(x - 0.305) < 0.05 for x in suave), suave)

    def test_escolher_melhor_quadro_evita_escuro_e_borrado(self):
        import cv2
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            escuro = pasta / "f1.jpg"
            nitido = pasta / "f2.jpg"
            cv2.imwrite(str(escuro), np.zeros((180, 320, 3), dtype=np.uint8))
            img_nitida = np.full((180, 320, 3), 120, dtype=np.uint8)
            cv2.rectangle(img_nitida, (80, 40), (240, 140), (255, 255, 255), 3)
            cv2.line(img_nitida, (0, 0), (320, 180), (20, 200, 20), 2)
            cv2.imwrite(str(nitido), img_nitida)
            escolhido = otimizador_corte.escolher_melhor_quadro([escuro, nitido], detector_rosto=None)
            self.assertEqual(escolhido, nitido)


if __name__ == "__main__":
    unittest.main()
