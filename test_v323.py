"""3.23: legenda que não pula nem pisca, revisão em sincronia e IA local que se liga sozinha."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

import cortes
import ia_cortes
import legendas
import projeto_edicao


def _palavras(textos, passo=0.5):
    return [{"t": t, "ini": round(passo * i, 2), "fim": round(passo * i + passo * 0.9, 2)} for i, t in enumerate(textos)]


def _eventos(ass):
    out = []
    for linha in Path(ass).read_text(encoding="utf-8").splitlines():
        if linha.startswith("Dialogue: 0,"):
            _, ini, fim, _r = linha.split(",", 3)
            out.append((legendas._seg(ini), legendas._seg(fim), linha))
    return out


class UmaLinhaSo(unittest.TestCase):
    LONGAS = ("o renato cariani praticamente comprou aquela residência maravilhosa "
              "inacreditavelmente rápido pessoal").split()

    def setUp(self):
        cortes.aplicar_config(cortes.carregar_config())

    def test_mede_com_a_fonte_de_verdade(self):
        medir = legendas.medidor_legenda("Arial Black", 62)
        self.assertIsNotNone(medir)
        self.assertGreater(medir("INACREDITAVELMENTE"), medir("OI") * 5)

    def test_bloco_largo_vira_dois_blocos(self):
        with tempfile.TemporaryDirectory() as d:
            ev = _eventos(cortes.gerar_ass(_palavras(self.LONGAS), self.LONGAS, Path(d) / "l.ass",
                                           template="Clássico"))
        self.assertTrue(all("\\q2" in e[2] for e in ev))          # o libass nunca quebra a linha
        textos = {e[2].split("}")[-1] for e in ev}
        self.assertTrue(textos)

    def test_altura_nao_pula_no_render(self):
        """Renderiza de verdade e mede o topo do texto: antes pulava 71 px no Clássico."""
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            cortes.gerar_ass(_palavras(self.LONGAS), self.LONGAS, d / "l.ass", template="Clássico")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                            f"color=black:s=1080x1920:d={0.5 * len(self.LONGAS)}:r=6", "-vf", "ass=l.ass",
                            str(d / "q_%03d.png")], cwd=d, check=True)
            topos, lados = [], []
            for q in sorted(d.glob("q_*.png")):
                a = np.asarray(Image.open(q).convert("L")) > 60
                if a.any():
                    topos.append(np.where(a.any(1))[0].min())
                    cols = np.where(a.any(0))[0]
                    lados.append((cols.min(), cols.max()))
        self.assertLessEqual(max(topos) - min(topos), 16)            # só o 'pop' da palavra falada
        self.assertGreaterEqual(min(x for x, _ in lados), 0)
        self.assertLess(max(y for _, y in lados), 1080)

    def test_palavra_gigante_encolhe(self):
        palavra = ["PNEUMOULTRAMICROSCOPICOSSILICOVULCANOCONIOTICO"]
        with tempfile.TemporaryDirectory() as d:
            ev = _eventos(cortes.gerar_ass(_palavras(palavra), palavra, Path(d) / "l.ass"))
        self.assertIn("\\fs", ev[0][2])


class SemPiscar(unittest.TestCase):
    def test_nunca_duas_legendas_juntas_nem_flash_nem_buraco(self):
        ps = [{"t": "ele", "ini": 0.0, "fim": 0.4}, {"t": "falou", "ini": 0.4, "fim": 0.8},
              {"t": "muito", "ini": 0.8, "fim": 0.83}, {"t": "rápido", "ini": 0.83, "fim": 1.3},
              {"t": "mesmo", "ini": 1.3, "fim": 1.8}, {"t": "oi", "ini": 1.8, "fim": 1.8},
              {"t": "tchau", "ini": 1.8, "fim": 2.2}, {"t": "depois", "ini": 2.7, "fim": 3.0}]
        for tpl in ("Clássico", "Karaokê", "Viral Dinâmico"):
            with tempfile.TemporaryDirectory() as d:
                ev = _eventos(cortes.gerar_ass(ps, [p["t"] for p in ps], Path(d) / "l.ass", template=tpl))
            for (a0, a1, _), (b0, _b1, _) in zip(ev, ev[1:]):
                self.assertLessEqual(a1, b0 + 1e-6, tpl)                # não encavala
                self.assertFalse(0 < b0 - a1 < 0.15, tpl)               # não 'apaga e acende'
            self.assertTrue(all(f - i >= 0.06 for i, f, _ in ev), tpl)  # sem flash de 1 quadro


class RevisaoEmSincronia(unittest.TestCase):
    def test_previa_vai_pra_receita_e_pro_render(self):
        self.assertIn("previa=list(previa_gancho) if previa_gancho else None",
                      Path("cortes.py").read_text(encoding="utf-8"))
        self.assertEqual(projeto_edicao._previa({"previa": [4.0, 6.0]}), (4.0, 6.0))
        self.assertIsNone(projeto_edicao._previa({}))
        codigo = Path("projeto_edicao.py").read_text(encoding="utf-8")
        self.assertEqual(codigo.count("previa=_previa(r)"), 2)            # revisar legenda e trocar pergunta


class OllamaLigaSozinho(unittest.TestCase):
    def test_liga_quando_esta_instalado_e_desligado(self):
        estados = iter([False, False, True])
        with patch.object(ia_cortes, "ollama_rodando", side_effect=lambda timeout=2: next(estados, True)), \
                patch.object(ia_cortes, "achar_ollama", return_value="ollama.exe"), \
                patch("subprocess.Popen") as popen, patch("time.sleep"):
            self.assertTrue(ia_cortes.garantir_ollama())
        self.assertEqual(popen.call_args.args[0], ["ollama.exe", "serve"])

    def test_sem_ollama_instalado(self):
        with patch.object(ia_cortes, "ollama_rodando", return_value=False), \
                patch.object(ia_cortes, "achar_ollama", return_value=None):
            self.assertFalse(ia_cortes.garantir_ollama())

    def test_aquece_so_com_ia_local(self):
        with patch.object(cortes, "IA_PRINCIPAL", "claude"):
            self.assertIsNone(ia_cortes.aquecer_local())
        self.assertIn("ia_cortes.aquecer_local()", Path("cortes.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
