"""3.27: pergunta do gancho desvia do rosto, legenda foge do texto já gravado no vídeo, tirar silêncios
pelo volume do próprio vídeo e o Modo PC fraco usando mesmo o Whisper base."""
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

import acabamento
import cortes
import efeitos
import legendas


class GanchoForaDoRosto(unittest.TestCase):
    def test_desce_pra_baixo_do_rosto(self):
        rostos = [(460, 660)] * 10                       # rosto no alto da tela, onde a pergunta fica
        alt = acabamento.altura_gancho("O QUE TEM DE TÃO ESPECIAL NESSA CORRENTE??")
        y = acabamento.y_gancho_livre(rostos, alt, 250, topo_min=250, limite_baixo=1500)
        self.assertGreaterEqual(y, 660)                   # começa depois do queixo
        self.assertLessEqual(y + alt, 1500)               # sem descer até a legenda

    def test_sobe_quando_cabe_acima(self):
        y = acabamento.y_gancho_livre([(700, 900)] * 10, 200, 600, topo_min=160)
        self.assertLessEqual(y + 200, 700)

    def test_sem_rosto_ou_longe_fica_onde_esta(self):
        self.assertIsNone(acabamento.y_gancho_livre([], 300))
        self.assertIsNone(acabamento.y_gancho_livre([(1200, 1400)] * 10, 300))

    def test_posicao_no_texto_e_mantida_na_troca(self):
        t = legendas.texto_gancho_ass("ele falou isso?", ["ISSO"], y=700)
        self.assertTrue(t.startswith("{\\an8\\pos(540,700)}"))
        self.assertEqual(legendas.posicao_gancho(t), "{\\an8\\pos(540,700)}")
        self.assertEqual(legendas.posicao_gancho(legendas.texto_gancho_ass("ele falou isso?")), "")


def _quadro(texto=None, y=1040, logo=False):
    import cv2
    q = np.full((1137, 640, 3), 90, np.uint8)
    cv2.circle(q, (320, 300), 120, (200, 170, 150), -1)  # "pessoa"
    if logo:                                              # letreiro parado (não é legenda)
        cv2.putText(q, "LOGO FIXO AQUI", (200, 900), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 4)
        cv2.putText(q, "LOGO FIXO AQUI", (200, 900), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    if texto:
        x = (640 - len(texto) * 11) // 2
        cv2.putText(q, texto, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 4)
        cv2.putText(q, texto, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return q


class TextoJaGravado(unittest.TestCase):
    def _analise(self, quadros):
        import cv2
        return {"w": 720, "h": 1280, "linhas_texto": [efeitos._linhas_com_texto(cv2, q) for q in quadros]}

    def test_acha_a_legenda_do_jogo(self):
        falas = ["AH OLHA SO ISSO", None, "MAS QUE BAITA AZAR MESMO", "VAMOS ENCONTRAR O BRIAN", None,
                 "SEGUINDO O RIO ALI", None, None]
        f = efeitos.faixa_texto_fixa(self._analise([_quadro(t) for t in falas]))
        self.assertIsNotNone(f)
        self.assertTrue(0.85 < f[0] < 0.92 < f[1] < 0.95)

    def test_sem_texto_ou_letreiro_parado_nao_conta(self):
        self.assertIsNone(efeitos.faixa_texto_fixa(self._analise([_quadro() for _ in range(8)])))
        self.assertIsNone(efeitos.faixa_texto_fixa(self._analise([_quadro(logo=True) for _ in range(8)])))

    def test_legenda_sai_de_cima_do_texto(self):
        nova = efeitos.margem_longe_do_texto((1698, 1830), 215, 67)
        self.assertGreaterEqual(1920 - nova, 0)
        self.assertLessEqual(1920 - nova, 1698)           # a nossa termina antes do texto começar
        self.assertEqual(efeitos.margem_longe_do_texto((1000, 1100), 215, 67), 215)   # longe: não mexe
        self.assertEqual(efeitos.margem_longe_do_texto(None, 215, 67), 215)


def _wav(destino, ganho_db, partes):
    """partes = [(segundos, 'fala'|'pausa')]: 'fala' = ruído modulado (tipo voz), pausa = silêncio quase total."""
    sr, rng = 16000, np.random.default_rng(1)
    blocos = []
    for seg, tipo in partes:
        n = int(seg * sr)
        if tipo == "fala":
            env = 0.35 + 0.25 * np.sin(np.linspace(0, seg * 2 * np.pi * 4, n))
            blocos.append(rng.normal(0, 0.18, n) * env)
        else:
            blocos.append(rng.normal(0, 0.0004, n))
    a = np.concatenate(blocos) * 10 ** (ganho_db / 20)
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())
    return destino


class SilencioPeloVolumeDoVideo(unittest.TestCase):
    def test_mesmo_corte_com_microfone_alto_ou_baixo(self):
        partes = [(6, "fala"), (1.5, "pausa"), (6, "fala"), (2.0, "pausa"), (6, "fala")]
        with tempfile.TemporaryDirectory() as d:
            alto = efeitos.intervalos_sem_silencio(_wav(Path(d) / "a.wav", 0, partes))[2]
            baixo = efeitos.intervalos_sem_silencio(_wav(Path(d) / "b.wav", -18, partes))[2]
        self.assertGreater(alto, 2.5)                     # as 2 pausas saem...
        self.assertAlmostEqual(alto, baixo, delta=0.3)     # ...com o microfone alto ou baixo

    def test_trava_quando_seria_pausa_demais(self):
        with tempfile.TemporaryDirectory() as d:
            v = _wav(Path(d) / "c.wav", 0, [(2, "fala"), (10, "pausa"), (2, "fala"), (10, "pausa")])
            manter, _, removido = efeitos.intervalos_sem_silencio(v)
        self.assertEqual(removido, 0.0)
        self.assertEqual(len(manter), 1)


class PcFracoUsaOBase(unittest.TestCase):
    def test_modelo(self):
        for fraco, escolhido, esperado in ((True, "small", "base"), (True, "turbo", "turbo"),
                                           (False, "small", "small"), (False, "turbo", "turbo")):
            cfg = dict(cortes.carregar_config(), modo_pc_fraco=fraco, whisper_final=escolhido)
            with patch.object(cortes, "carregar_config", return_value=cfg):
                self.assertEqual(cortes.modelo_final(), esperado)


if __name__ == "__main__":
    unittest.main()
