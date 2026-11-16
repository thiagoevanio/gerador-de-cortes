"""3.20: aba Contas & IA rola até o fim e 3 formatos novos de faixa (Plantão, Explosão, Diagonal)."""
import unittest
from pathlib import Path

import faixas


class Formatos(unittest.TestCase):
    def test_tres_formatos_novos(self):
        for formato in ("Plantão", "Explosão", "Diagonal"):
            self.assertIn(formato, faixas.FORMATOS_FAIXA)
            for pergunta in ("OI?", "ELE FALOU ISSO AO VIVO NA LIVE DE ONTEM SEM QUERER E TODO MUNDO VIU?"):
                img = getattr(faixas, faixas.FORMATOS_FAIXA[formato])(pergunta, ["VIVO"], "canal")
                self.assertEqual(img.mode, "RGBA")
                self.assertGreater(img.height, 150)
                self.assertLess(img.height, 700)

    def test_aparecem_na_aba_visual(self):
        texto = Path("interface.py").read_text(encoding="utf-8")
        for nome in ('"Plantão (jornal)": "Plantão"', '"Explosão (HQ)": "Explosão"', '"Diagonal (esporte)": "Diagonal"'):
            self.assertIn(nome, texto)


class Contas(unittest.TestCase):
    def test_aba_contas_rola(self):
        texto = Path("interface.py").read_text(encoding="utf-8")
        self.assertIn("self.can_contas, esq = self._lista_rolavel(cartao, bg=CARTAO)", texto)
        self.assertIn('"contas": getattr(self, "can_contas", None)', texto)


if __name__ == "__main__":
    unittest.main()
