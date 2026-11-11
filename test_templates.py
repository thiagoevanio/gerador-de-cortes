"""Templates de edição (3.8): legenda .ass por template, escolha automática e validação da IA."""
import tempfile
import unittest
from pathlib import Path

import cortes
import templates_edicao as te


def _palavras():
    textos = ["Ele", "não", "acreditou.", "Olha", "a", "reação", "dele!"]
    return [{"t": t, "ini": 0.4 * i, "fim": 0.4 * i + 0.3} for i, t in enumerate(textos)], textos


class Templates(unittest.TestCase):
    def setUp(self):
        cortes.aplicar_config(cortes.carregar_config())

    def test_todos_geram_legenda(self):
        pal, txt = _palavras()
        pal[1]["enfase"] = True
        with tempfile.TemporaryDirectory() as d:
            for nome in te.TEMPLATES:
                ass = cortes.gerar_ass(pal, txt, Path(d) / "x.ass", duracao=3, template=nome)
                corpo = ass.read_text(encoding="utf-8")
                self.assertIn("Style: Leg,", corpo)
                self.assertIn("Dialogue: 0,", corpo, nome)

    def test_karaoke_e_caixa(self):
        pal, txt = _palavras()
        with tempfile.TemporaryDirectory() as d:
            k = cortes.gerar_ass(pal, txt, Path(d) / "k.ass", template="Karaokê").read_text(encoding="utf-8")
            self.assertIn("\\kf", k)
            n = cortes.gerar_ass(pal, txt, Path(d) / "n.ass", template="Notícia").read_text(encoding="utf-8")
            linha = next(l for l in n.splitlines() if l.startswith("Style: Leg,"))
            self.assertEqual(linha.split(",")[15], "3")          # BorderStyle 3 = caixa

    def test_minimalista_mantem_minusculas(self):
        pal, txt = _palavras()
        with tempfile.TemporaryDirectory() as d:
            m = cortes.gerar_ass(pal, txt, Path(d) / "m.ass", template="Minimalista").read_text(encoding="utf-8")
            self.assertIn("acreditou.", m)

    def test_automatico_pelo_tom(self):
        self.assertEqual(te.resolver(te.AUTOMATICO, "Engraçado")["nome"], "Viral Dinâmico")
        self.assertEqual(te.resolver(te.AUTOMATICO, "treta")["nome"], "Hormozi")
        self.assertEqual(te.resolver(te.AUTOMATICO, None, "jogo")["nome"], "Gamer")
        self.assertEqual(te.resolver("não existe")["nome"], te.PADRAO)

    def test_ritmo_alterna_frases(self):
        pal, txt = _palavras()
        trechos = te.trechos_ritmo(pal, txt, 3.0, minimo=0.5)
        self.assertTrue(trechos)
        self.assertTrue(all(b > a for a, b in trechos))
        self.assertTrue(te.expr_ritmo(trechos, 0.05).startswith("(1+0.050"))

    def test_validacao_ia(self):
        pal, _ = _palavras()
        padrao = {"palavras": [p["t"] for p in pal], "pergunta": "P", "destaque": [], "titulo": "t",
                  "hashtags": [], "foto": None, "emoji": "😱", "nota": None, "gancho": None}
        d = cortes._validar_dados({"pergunta": "ele fez isso mesmo na frente de todo mundo ao vivo no programa??",
                                   "alternativas": ["outra??", 5], "enfase": [1, "2", "x"], "tom": "Polêmico"},
                                  padrao, pal, None)
        self.assertLessEqual(len(d["pergunta"]), 60)
        self.assertFalse(d["pergunta"].endswith(" NO??"))
        self.assertEqual(d["alternativas"], ["OUTRA??"])
        self.assertEqual(d["enfase"], [1, 2])
        self.assertEqual(d["tom"], "polemica")


if __name__ == "__main__":
    unittest.main()
