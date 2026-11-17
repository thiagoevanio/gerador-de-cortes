"""3.22: IA local que faz tudo sem errar, legenda que não duplica e posição da legenda livre."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cortes
import efeitos
import ia_cortes
import otimizador_corte as oc
import previa


def _palavras(textos, passo=0.4):
    return [{"t": t, "ini": round(i * passo, 2), "fim": round(i * passo + 0.35, 2)} for i, t in enumerate(textos)]


class TravaDuplicata(unittest.TestCase):
    ORIG = ["o", "Renato", "Cariane", "quase", "fez", "o", "pix"]

    def test_correcao_que_repete_a_vizinha_e_desfeita(self):
        # 'Renato' → 'Renato Cariani' com 'Cariane' logo depois = "RENATO CARIANI CARIANI"
        seguras, n = oc.travar_duplicatas(self.ORIG, ["o", "Renato Cariani", "Cariani", "quase", "fez", "o", "pix"])
        self.assertEqual(seguras[1], "Renato")
        self.assertEqual(seguras[2], "Cariani")         # a correção boa continua
        self.assertEqual(n, 1)

    def test_lista_deslocada_nao_entra(self):
        # IA "andou" uma casa: a palavra 3 virou a 4 ('fez fez' na legenda)
        seguras, n = oc.travar_duplicatas(self.ORIG, ["o", "Renato", "Cariani", "fez", "fez", "o", "pix"])
        self.assertEqual(seguras[3], "quase")
        self.assertEqual(n, 1)

    def test_frase_inteira_e_palavra_inventada(self):
        seguras, n = oc.travar_duplicatas(self.ORIG, ["o", "Renato", "Cariani", "quase fez o", "fez", "o", "dinheiro"])
        self.assertEqual(seguras[3], "quase")
        self.assertEqual(seguras[6], "pix")
        self.assertEqual(n, 2)

    def test_pela_entrada_principal(self):
        textos, _ = oc.reconciliar_palavras_ia(_palavras(self.ORIG), None, {"1": "Renato Cariani", "2": "Cariani"})
        self.assertEqual(" ".join(textos), "o Renato Cariani quase fez o pix")


class RepeticoesWhisper(unittest.TestCase):
    def test_mesma_palavra_no_mesmo_instante(self):
        ps = [{"t": "ele", "ini": 0.0, "fim": 0.3}, {"t": "falou", "ini": 0.3, "fim": 0.7},
              {"t": "falou", "ini": 0.5, "fim": 0.8}, {"t": "isso", "ini": 0.9, "fim": 1.2}]
        limpas, n = oc.limpar_repeticoes(ps)
        self.assertEqual([p["t"] for p in limpas], ["ele", "falou", "isso"])
        self.assertEqual(n, 1)

    def test_loop_de_alucinacao(self):
        textos = ["oi"] + ["obrigado", "por", "assistir"] * 4 + ["tchau"]
        limpas, n = oc.limpar_repeticoes(_palavras(textos))
        self.assertEqual([p["t"] for p in limpas], ["oi", "obrigado", "por", "assistir", "tchau"])
        self.assertEqual(n, 9)

    def test_repeticao_de_verdade_fica(self):
        textos = ["não", "não", "não", "para", "com", "isso", "para", "com", "isso"]
        limpas, n = oc.limpar_repeticoes(_palavras(textos))
        self.assertEqual(n, 0)


class IaLocal(unittest.TestCase):
    def setUp(self):
        self.antes = cortes.IA_PRINCIPAL
        cortes.IA_PRINCIPAL = "local"

    def tearDown(self):
        cortes.IA_PRINCIPAL = self.antes

    def test_faz_tudo_menos_a_foto(self):
        ps = _palavras(["então", "ele", "chegou", "e", "falou", "que", "a", "casa", "já", "foi", "vendida"])
        with tempfile.TemporaryDirectory() as d:
            _, itens, trecho, folha = ia_cortes._pedido_corte(ps, {"titulo": "t"}, Path(d), frames=[Path("x")])
        chaves = " ".join(i.split(":")[0] for i in itens)
        for k in ('"correcoes"', '"gancho"', '"enfase"', '"pergunta"', '"titulo"'):
            self.assertIn(k, chaves)
        self.assertNotIn('"foto"', chaves)
        self.assertIsNone(folha)
        self.assertIn("0:então", trecho)                # lista numerada (antes: texto corrido)

    def test_molde_no_prompt(self):
        ps = _palavras(["a", "b", "c"])
        with tempfile.TemporaryDirectory() as d:
            _, itens, trecho, _ = ia_cortes._pedido_corte(ps, {"titulo": "t"}, Path(d))
        prompt = ia_cortes._prompt_corte({"titulo": "t"}, "", ps, trecho, itens, local=True)
        self.assertIn('"gancho": 0', prompt)
        self.assertIn("de 0 a 2", prompt)

    def test_resposta_tipica_de_modelo_pequeno(self):
        """Tipos trocados, emoji em texto, nota absurda, correção que duplica: nada disso passa."""
        ps = _palavras(["o", "Renato", "Cariane", "quase", "fez", "o", "pix"])
        bruto = {"resumo": "x", "correcoes": {"1": "Renato Cariani", "2": "Cariani"},
                 "pergunta": "cariani quase fez o pix na casa errada??", "alternativas": "nenhuma",
                 "destaque": "PIX", "titulo": "Cariani e o pix", "nota": 85, "tom": "engraçado",
                 "gancho": "6", "enfase": ["3", "x", 99], "emojis": [[6, "surpreso"], [4, "😱"]],
                 "emoji": "rindo", "hashtags": "#cariani"}
        dados = ia_cortes._validar_dados(bruto, ia_cortes._pedido_corte(ps, {}, Path("."))[0], ps, None)
        self.assertEqual(" ".join(dados["palavras"]), "o Renato Cariani quase fez o pix")
        self.assertIsNone(dados["nota"])
        self.assertEqual(dados["emojis"], [[4, "😱"]])
        self.assertEqual(dados["emoji"], "😱")
        self.assertEqual(dados["alternativas"], [])
        self.assertTrue(dados["pergunta"].endswith("??"))

    def test_lote_vira_um_por_vez(self):
        self.assertIsNone(ia_cortes.pensar_lote([{"palavras": []}], {}, Path(".")))


class Ollama(unittest.TestCase):
    def test_contexto_do_tamanho_do_pedido(self):
        self.assertEqual(ia_cortes.contexto_local("x" * 100), 4096)
        grande = ia_cortes.contexto_local("x" * 30000)       # ~10 mil tokens de transcrição
        self.assertGreaterEqual(grande, 30000 // 3 + 2048)
        self.assertEqual(grande % 1024, 0)

    def test_pedido_vai_com_contexto_e_temperatura_baixa(self):
        enviados = []

        class Resp:
            status = 200

            def __init__(self, corpo):
                self.corpo = corpo

            def read(self):
                return json.dumps(self.corpo).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def abrir(req, timeout=0):
            if isinstance(req, str):                           # /api/tags
                return Resp({"models": [{"name": cortes.MODELO_LOCAL}]})
            enviados.append((json.loads(req.data), timeout))
            return Resp({"response": '{"pergunta": "OI??"}', "prompt_eval_count": 10, "eval_count": 5})
        with patch("urllib.request.urlopen", side_effect=abrir):
            r = ia_cortes.ollama_json("p" * 20000, timeout=75)
        self.assertEqual(r, {"pergunta": "OI??"})
        corpo, timeout = enviados[0]
        self.assertGreater(corpo["options"]["num_ctx"], 4096)
        self.assertLessEqual(corpo["options"]["temperature"], 0.3)
        self.assertEqual(corpo["keep_alive"], "15m")
        self.assertGreaterEqual(timeout, 240)                  # carregar o modelo no processador demora

    def test_modelo_nao_baixado_avisa(self):
        with patch.object(ia_cortes, "ollama_rodando", return_value=True), \
                patch.object(ia_cortes, "modelos_ollama", return_value=["llama3:8b"]):
            self.assertIsNone(ia_cortes.ollama_json("oi"))


class PosicaoLegenda(unittest.TestCase):
    def test_desvio_do_rosto_so_desce(self):
        rostos = [(1500, 1880)] * 10                          # rosto até o rodapé: não dá pra descer
        self.assertEqual(efeitos.margem_legenda_segura(rostos, 300, 70, minimo=20), 300)   # e não sobe
        rostos = [(1300, 1600)] * 10
        self.assertLess(efeitos.margem_legenda_segura(rostos, 400, 70, minimo=20), 400)    # desce

    def test_zona_do_app_nao_empurra_mais(self):
        codigo = Path("cortes.py").read_text(encoding="utf-8")
        self.assertNotIn("MARGEM_LEGENDA + 330", codigo)
        self.assertNotIn('margem = zona["baixo"]', codigo)
        self.assertEqual(previa._margem(40), 40)
        self.assertNotIn("+ 330", Path("previa.py").read_text(encoding="utf-8"))

    def test_marca_sobe_quando_a_legenda_cola_no_rodape(self):
        with tempfile.TemporaryDirectory() as d, patch.object(cortes, "MARCA", "canal"):
            for margem, pos in ((40, ",9,40,36,70,"), (300, ",3,40,36,36,")):
                ass = cortes.gerar_ass(_palavras(["oi"]), ["oi"], Path(d) / "l.ass", duracao=2, margem=margem)
                linha = next(l for l in ass.read_text(encoding="utf-8").splitlines() if l.startswith("Style: Marca"))
                self.assertIn(pos, linha)

    def test_barra_vai_do_rodape_ao_topo(self):
        self.assertIn('escala(0, "Posição da legenda (↑)", 10, 1500, passo=10)',
                      Path("interface.py").read_text(encoding="utf-8"))

    def test_previa_mostra_a_legenda_onde_pediu(self):
        cfg = dict(cortes.carregar_config(), estilo_corte="clean", legenda_margem=40, plataforma_alvo="tiktok")
        try:
            img = previa.gerar_previa(cfg, altura=960)
            self.assertEqual(img.size, (540, 960))
        finally:
            cortes.aplicar_config(cortes.carregar_config())


if __name__ == "__main__":
    unittest.main()
