"""3.12: IA mais completa e com mais qualidade — motor (JSON tolerante, chamada enxuta, saúde dos
provedores, registro de uso, modelos por tarefa), juiz local das perguntas, glossário de nomes,
gosto do dono, prompt 2.0, lote e escolha de momentos. Nada aqui chama IA de verdade."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cortes
import ia_aprende
import ia_juiz
import ia_motor
import momentos
import postagem


def _pal(texto, passo=0.5):
    return [{"t": t, "ini": round(passo * i, 2), "fim": round(passo * i + 0.4, 2)} for i, t in enumerate(texto.split())]


class LeitorJson(unittest.TestCase):
    def ler(self, texto):
        return ia_motor.ler_json(texto)

    def test_respostas_com_defeito(self):
        barra = chr(92)
        casos = [
            ('Aqui:\n```json\n{"pergunta": "ELE VOLTOU??", "nota": 7}\n```', {"pergunta": "ELE VOLTOU??", "nota": 7}),
            ('{"pergunta": "X??", "hashtags": ["#a", "#b",], }', {"pergunta": "X??", "hashtags": ["#a", "#b"]}),
            ("{'pergunta': 'ELE DISSE ISSO??', 'nota': 8}", {"pergunta": "ELE DISSE ISSO??", "nota": 8}),
            ('{"ok": True, "foto": None}', {"ok": True, "foto": None}),
            ('{"nota": 7, // comentário\n "tom": "humor"}', {"nota": 7, "tom": "humor"}),
            ('{"titulo": "Ele disse "nunca mais" e saiu", "nota": 6}',
             {"titulo": 'Ele disse "nunca mais" e saiu', "nota": 6}),
            ('{"a": "x" "b": "y"}', {"a": "x", "b": "y"}),
            ('{pergunta: "OI??", nota: 5}', {"pergunta": "OI??", "nota": 5}),
            ('{"emoji": "' + barra + "ud83d" + barra + 'ude31"}', {"emoji": chr(0x1F631)}),
            ('Resposta {conforme pedido}: {"ok": 1}', {"ok": 1}),
            ('x {"a": {"b": 1}, "c": [{"d": 2}]} y', {"a": {"b": 1}, "c": [{"d": 2}]}),
        ]
        for texto, esperado in casos:
            self.assertEqual(self.ler(texto)[0], esperado, texto)

    def test_cortada_no_fim_aproveita_o_que_veio(self):
        v, info = self.ler('{"pergunta": "O TÉCNICO SAIU??", "alternativas": ["A??", "B')
        self.assertEqual(v["pergunta"], "O TÉCNICO SAIU??")
        self.assertTrue(info["truncado"])
        v, info = self.ler('{"cortes": [{"corte": 1, "pergunta": "A??"}, {"corte": 2, "pergunta": "B')
        self.assertEqual(len(v["cortes"]), 2)                 # pega o JSON de fora, não só o 1º pedaço
        self.assertTrue(info["truncado"])

    def test_perfeito_nao_marca_reparo_e_prosa_falha(self):
        self.assertEqual(self.ler('{"a": [1, 2]}')[1], {"reparos": 0, "truncado": False})
        for texto in ("Desculpe, não consigo ajudar.", "[1, 2, 3]", "Não sei. [12s] foi ali."):
            with self.assertRaises(ValueError):
                self.ler(texto)
        self.assertEqual(cortes.extrair_json('ok: {"x": 1,}'), {"x": 1})


class Saude(unittest.TestCase):
    def test_pausa_volta_e_backoff(self):
        s = ia_motor.Saude()
        self.assertEqual(s.falha("claude", "limite", "x", agora=1000), 1800)
        self.assertFalse(s.liberado("claude", agora=1500))
        self.assertIn("limite de uso", s.motivo("claude", agora=1500))
        self.assertTrue(s.liberado("claude", agora=2801))
        self.assertEqual(s.falha("claude", "limite", "x", agora=3000), 3600)      # 2ª seguida: dobra
        s.sucesso("claude")
        self.assertTrue(s.liberado("claude", agora=3001))
        self.assertEqual(s.falha("gemini", "invalida", "", agora=0), 0)           # respondeu mal: não pausa
        self.assertTrue(s.liberado("gemini", agora=1))
        pausa = s.falha("c", "limite", "Claude AI usage limit reached|1731300000", agora=1731290000)
        self.assertEqual(pausa, 10000)                                           # até a hora que o limite volta

    def test_classifica_erros(self):
        self.assertEqual(ia_motor.classificar_erro("Claude AI usage limit reached|1731300000"), "limite")
        self.assertEqual(ia_motor.classificar_erro("HTTP 429 Too Many Requests"), "limite")
        self.assertEqual(ia_motor.classificar_erro("Invalid API key · Please run /login"), "auth")
        self.assertEqual(ia_motor.classificar_erro("Request timed out"), "timeout")
        self.assertEqual(ia_motor.classificar_erro("deu pau"), "erro")


class Modelos(unittest.TestCase):
    def test_degraus_por_qualidade_e_tarefa(self):
        eco, equi, maxi = ({"ia_qualidade": q} for q in ("economico", "equilibrado", "maximo"))
        self.assertEqual(ia_motor.modelo_claude(eco, "corte"), "haiku")
        self.assertEqual(ia_motor.modelo_claude(eco, "corte", escalar=True), "sonnet")
        self.assertEqual(ia_motor.modelo_claude(equi, "corte"), "sonnet")
        self.assertEqual(ia_motor.modelo_claude(equi, "momentos"), "sonnet")
        self.assertEqual(ia_motor.modelo_claude(equi, "espanhol"), "haiku")
        self.assertEqual(ia_motor.modelo_claude(equi, "corte", escalar=True), "opus")
        self.assertEqual(ia_motor.modelo_claude(maxi, "lote"), "opus")
        self.assertEqual(ia_motor.modelo_claude(maxi, "revisao"), "sonnet")
        self.assertEqual(ia_motor.modelo_claude({"ia_qualidade": "maximo", "claude_modelo": "haiku"}, "corte"), "haiku")
        self.assertEqual(ia_motor.modelo_claude({"claude_modelo": "haiku"}, "corte", escalar=True), "sonnet")
        self.assertEqual(ia_motor.nivel_qualidade({"economico": True}), "economico")       # config antiga
        self.assertEqual(ia_motor.nivel_qualidade({"economico": False}), "maximo")
        g = {"ia_qualidade": "equilibrado", "gemini_modelo": "gemini-flash-lite-latest"}
        self.assertEqual(ia_motor.modelo_gemini(g, "corte"), "gemini-flash-latest")
        self.assertEqual(ia_motor.modelo_gemini(g, "geral"), "gemini-flash-lite-latest")


class RegistroDeUso(unittest.TestCase):
    def test_resumo(self):
        with tempfile.TemporaryDirectory() as d, patch("otimizador_corte.registrar_economia_tokens"):
            arq = Path(d) / "uso.jsonl"
            ia_motor.registrar_uso("claude", "corte", True, 4.2, "haiku", 900, 300, 0.001, arquivo=arq)
            ia_motor.registrar_uso("claude", "corte", False, 1.0, "haiku", erro="limite", arquivo=arq)
            ia_motor.registrar_uso("gemini", "momentos", True, 2.0, "", chars_entrada=3800, chars_saida=380,
                                   arquivo=arq)
            r = ia_motor.resumo_uso(7, arquivo=arq)
            self.assertEqual((r["chamadas"], r["falhas"]), (3, 1))
            self.assertEqual(r["por_provedor"]["claude (haiku)"]["chamadas"], 2)
            self.assertEqual(r["tokens_entrada"], 900 + 1000)              # estimado pelo tamanho do texto
            texto = ia_motor.texto_uso(7, arquivo=arq)
            self.assertIn("3 chamadas", texto)
            self.assertIn("1 falhou", texto)


class _Proc:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


def _envelope(resultado, erro=False, **extra):
    e = {"type": "result", "subtype": "success", "is_error": erro, "result": resultado,
         "usage": {"input_tokens": 10, "cache_creation_input_tokens": 900, "cache_read_input_tokens": 0,
                   "output_tokens": 5}, "modelUsage": {"claude-haiku-5-5": {}}, "total_cost_usd": 0.0002}
    e.update(extra)
    return json.dumps(e)


class ClaudeEnxuto(unittest.TestCase):
    def setUp(self):
        self.chamadas = []
        p1 = patch.object(cortes, "comando_claude", return_value=["claude"])
        p2 = patch.object(cortes, "_CLAUDE_ENXUTO", True)
        for p in (p1, p2):
            p.start()
            self.addCleanup(p.stop)

    def _rodar(self, respostas):
        def falso(cmd, **k):
            self.chamadas.append((cmd, k))
            return respostas[len(self.chamadas) - 1]
        return patch("subprocess.run", side_effect=falso)

    def test_chamada_enxuta_e_uso_real(self):
        with self._rodar([_Proc(_envelope('{"ok": true}'))]):
            r = cortes.claude_json("pergunta", modelo="haiku", sistema=ia_motor.SISTEMA_PADRAO)
        self.assertEqual(r, {"ok": True})
        cmd, k = self.chamadas[0]
        self.assertIn("--no-session-persistence", cmd)
        self.assertIn("--strict-mcp-config", cmd)
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")              # sem ferramentas
        self.assertEqual(cmd[cmd.index("--model") + 1], "haiku")
        sistema = Path(cmd[cmd.index("--system-prompt-file") + 1]).read_text(encoding="utf-8")
        self.assertEqual(sistema, ia_motor.SISTEMA_PADRAO)
        self.assertEqual(Path(k["cwd"]), ia_motor.pasta_neutra())        # nenhum arquivo do projeto junto
        info = ia_motor.ultimo()
        self.assertEqual((info["modelo"], info["tokens_entrada"], info["tokens_saida"]), ("claude-haiku-5-5", 910, 5))

    def test_modelo_forte_tem_reserva_leve(self):
        with self._rodar([_Proc(_envelope('{"ok": 1}'))]):
            cortes.claude_json("x", modelo="sonnet")
        cmd = self.chamadas[0][0]
        self.assertEqual(cmd[cmd.index("--fallback-model") + 1], "haiku")

    def test_imagem_vai_pelo_nome_com_read(self):
        with tempfile.TemporaryDirectory() as d:
            img = Path(d) / "frames.jpg"
            img.write_bytes(b"x")
            with self._rodar([_Proc(_envelope('{"foto": 2}'))]):
                r = cortes.claude_json("escolha a foto", cwd=Path(d), imagens=[img], modelo="haiku")
            cmd, k = self.chamadas[0]
            self.assertEqual(r, {"foto": 2})
            self.assertEqual(cmd[cmd.index("--tools") + 1], "Read")
            self.assertIn("frames.jpg", k["input"])                       # o Claude precisa saber o nome
            self.assertEqual(Path(k["cwd"]), Path(d))

    def test_limite_atingido_vira_pausa(self):
        with self._rodar([_Proc(_envelope("Claude AI usage limit reached|1731300000", erro=True))]):
            self.assertIsNone(cortes.claude_json("x", modelo="haiku"))
        self.assertEqual(ia_motor.ultimo()["erro_tipo"], "limite")

    def test_programa_antigo_usa_o_modo_simples(self):
        respostas = [_Proc("", "error: unknown option '--system-prompt-file'", 1), _Proc(_envelope('{"ok": 1}'))]
        with self._rodar(respostas):
            r = cortes.claude_json("x", modelo="haiku")
        self.assertEqual(r, {"ok": 1})
        self.assertEqual(len(self.chamadas), 2)
        self.assertNotIn("--system-prompt-file", self.chamadas[1][0])
        self.assertFalse(cortes._CLAUDE_ENXUTO)


class IaJson(unittest.TestCase):
    def setUp(self):
        ia_motor.saude.zerar()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(ia_motor.saude.zerar)
        for p in (patch.object(ia_motor, "ARQ_USO", Path(self.tmp.name) / "uso.jsonl"),
                  patch("otimizador_corte.registrar_economia_tokens"),
                  patch.object(cortes, "carregar_config", return_value={"ia_qualidade": "equilibrado"}),
                  patch.object(cortes, "IA_PRINCIPAL", "claude"), patch.object(cortes, "IA_RESERVA", True)):
            p.start()
            self.addCleanup(p.stop)

    def test_limite_pausa_e_reserva_assume(self):
        pedidos = {"claude": 0, "gemini": 0}

        def claude(prompt, **k):
            pedidos["claude"] += 1
            ia_motor.anotar(erro_tipo="limite", erro="usage limit reached")
            return None

        def gemini(prompt, **k):
            pedidos["gemini"] += 1
            ia_motor.anotar(modelo="gemini-x")
            return {"ok": 1}
        with patch.object(cortes, "IAS", {"claude": (claude, lambda: True), "gemini": (gemini, lambda: True)}):
            self.assertEqual(cortes.ia_json("x", tarefa="corte"), {"ok": 1})
            self.assertEqual(ia_motor.resultado()["provedor"], "gemini")
            self.assertEqual(cortes.ia_json("y", tarefa="corte"), {"ok": 1})
        self.assertEqual(pedidos, {"claude": 1, "gemini": 2})              # 2ª vez nem tenta o Claude
        r = ia_motor.resumo_uso(1, arquivo=ia_motor.ARQ_USO)
        self.assertEqual((r["chamadas"], r["falhas"]), (3, 1))

    def test_resposta_sem_json_pede_de_novo(self):
        prompts = []

        def claude(prompt, **k):
            prompts.append(prompt)
            if len(prompts) == 1:
                ia_motor.anotar(erro_tipo="invalida", erro="resposta sem JSON")
                return None
            return {"ok": 1}
        with patch.object(cortes, "IAS", {"claude": (claude, lambda: True)}):
            self.assertEqual(cortes.ia_json("pedido", tarefa="corte"), {"ok": 1})
        self.assertEqual(len(prompts), 2)
        self.assertTrue(prompts[1].startswith("IMPORTANTE"))

    def test_modelo_e_sistema_por_tarefa(self):
        recebido = {}

        def claude(prompt, **k):
            recebido.update(k)
            return {"ok": 1}
        with patch.object(cortes, "IAS", {"claude": (claude, lambda: True)}):
            cortes.ia_json("x", tarefa="corte")
            self.assertEqual(recebido["modelo"], "sonnet")
            self.assertEqual(recebido["sistema"], ia_motor.SISTEMA_PADRAO)
            cortes.ia_json("x", tarefa="espanhol")
            self.assertEqual(recebido["modelo"], "haiku")
            with ia_motor.rotulo("momentos"):
                cortes.ia_json("x")
            self.assertEqual(recebido["modelo"], "sonnet")


class Juiz(unittest.TestCase):
    def setUp(self):
        self.base = ia_juiz.Base("o carro capotou e você não pode mexer no gta seis, ele pagou quarenta mil",
                                 "TUDO QUE VOCÊ PRECISA SABER ANTES DE COMPRAR GTA 6", "Davy Jones GTA 6")

    def test_notas(self):
        boa = ia_juiz.avaliar_pergunta("NO GTA 6, SE O CARRO CAPOTAR VOCÊ NÃO MEXE??", self.base)
        generica = ia_juiz.avaliar_pergunta("VOCÊ VIU ISSO??", self.base)
        inventada = ia_juiz.avaliar_pergunta("ELE PAGOU 500 MIL NO CARRO??", self.base)
        por_extenso = ia_juiz.avaliar_pergunta("ELE PAGOU 40 MIL NO CARRO DO GTA??", self.base)
        self.assertGreaterEqual(boa["nota"], 80)
        self.assertLess(generica["nota"], ia_juiz.NOTA_RUIM)
        self.assertIn("genérica", generica["motivos"])
        self.assertLess(inventada["nota"], ia_juiz.NOTA_BOA)
        self.assertTrue(any("500" in m for m in inventada["motivos"]))
        self.assertFalse(any("40" in m for m in por_extenso["motivos"]))   # "quarenta mil" vale

    def test_troca_so_quando_vale(self):
        boa = "NO GTA 6, SE O CARRO CAPOTAR VOCÊ NÃO MEXE??"
        p, alts, rel = ia_juiz.escolher_pergunta("VOCÊ VIU ISSO??", [boa], self.base)
        self.assertEqual(p, boa)
        self.assertTrue(rel["trocou"])
        self.assertEqual(alts, [])                                      # a genérica não volta como opção
        p, alts, rel = ia_juiz.escolher_pergunta(boa, ["VOCÊ VIU ISSO??"], self.base)
        self.assertEqual(p, boa)
        self.assertFalse(rel["trocou"])

    def test_limpezas(self):
        q = "NO GTA 6, SE O CARRO CAPOTAR VOCÊ NÃO MEXE??"
        self.assertEqual(ia_juiz.destaque_para(q, ["CAPOTAR", "MOTO"]), ["CAPOTAR"])
        self.assertEqual(ia_juiz.destaque_para(q, ["MOTO"]), ["CAPOTAR", "CARRO"])
        self.assertEqual(ia_juiz.limpar_titulo('  "GTA 6: o carro capota"  '), "GTA 6: o carro capota")
        self.assertEqual(ia_juiz.normalizar_hashtags(["#GTA6", "gta 6", "#gta6", "#Física dos carros", "", 5, "#123"]),
                         ["#GTA6", "#Físicadoscarros"])


class Glossario(unittest.TestCase):
    ORIG = ["então", "o", "davi", "jones", "falou", "do", "gta", "6."]
    CERTO = ["Então", "o", "Davy", "Jones", "falou", "do", "GTA", "6."]

    def test_extrai_nomes_corrigidos(self):
        self.assertEqual(ia_aprende.extrair_termos(self.ORIG, self.CERTO), {"Davy Jones": "davi jones", "GTA 6": "gta 6"})
        self.assertEqual(ia_aprende.extrair_termos(["mais", "eu", "acho."], ["Mas", "eu", "acho."]), {})
        self.assertEqual(ia_aprende.extrair_termos(["o", "gaules", "riu"], ["o", "Gaules", "riu"]), {"Gaules": "gaules"})
        self.assertEqual(ia_aprende.extrair_termos(["a", "b"], ["a"]), {})

    def test_ia_precisa_confirmar_e_dono_vale_na_hora(self):
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "g.json"
            ia_aprende.aprender_correcoes("Davy Jones GTA 6", self.ORIG, self.CERTO, "ia", arquivo=arq)
            self.assertEqual(ia_aprende.termos_confirmados("Davy Jones GTA 6", arquivo=arq), [])
            ia_aprende.aprender_correcoes("Davy Jones GTA 6", self.ORIG, self.CERTO, "ia", arquivo=arq)
            self.assertEqual(set(ia_aprende.termos_confirmados("Davy Jones GTA 6", arquivo=arq)), {"Davy Jones", "GTA 6"})
            self.assertEqual(ia_aprende.termos_confirmados("Outro canal", arquivo=arq), [])
            ia_aprende.aprender_correcoes("Outro canal", ["o", "gaules"], ["o", "Gaules"], "dono", arquivo=arq)
            self.assertEqual(ia_aprende.termos_confirmados("Outro canal", arquivo=arq), ["Gaules"])
            self.assertEqual(ia_aprende.dica_whisper("Outro canal", arquivo=arq), "Nomes: Gaules.")

    def test_whisper_recebe_os_nomes(self):
        with patch("ia_aprende.dica_whisper", return_value="Nomes: Davy Jones."):
            dica = cortes.dica_transcricao({"canal": "Davy Jones GTA 6", "titulo": "Título " * 80})
        self.assertIn("Nomes: Davy Jones.", dica)                          # vem antes do título (não é cortado)

    def test_gosto_do_dono(self):
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "gosto.json"
            self.assertFalse(ia_aprende.registrar_troca_pergunta("Padrão", "A??", "A??", arquivo=arq))
            self.assertTrue(ia_aprende.registrar_troca_pergunta("Padrão", "VOCÊ VIU??", "O GTA 6 MUDOU TUDO??",
                                                                 arquivo=arq))
            texto = ia_aprende.gosto_para_prompt("Padrão", arquivo=arq)
            self.assertIn('trocou "VOCÊ VIU??" por "O GTA 6 MUDOU TUDO??"', texto)
            self.assertEqual(ia_aprende.gosto_para_prompt("Outro", arquivo=arq), "")


class Prompt(unittest.TestCase):
    def test_transcricao_com_tempo_e_pausa(self):
        ps = [{"t": "Então", "ini": 0.0, "fim": 0.3}, {"t": "ele", "ini": 0.4, "fim": 0.6},
              {"t": "falou.", "ini": 2.0, "fim": 2.4}, {"t": "Mas", "ini": 5.2, "fim": 5.4}]
        self.assertEqual(cortes._transcricao_numerada(ps), "[0s] 0:Então 1:ele ‖ 2:falou. [5s] 3:Mas")

    def test_pedido_completo(self):
        ps = _pal("o carro capotou e você não pode mexer no gta seis")
        meta = {"titulo": "GTA 6", "canal": "Canal"}
        with tempfile.TemporaryDirectory() as d, patch.object(cortes, "IA_PRINCIPAL", "claude"), \
                patch("ia_aprende.termos_confirmados", return_value=["Davy Jones"]):
            padrao, itens, trecho, _ = cortes._pedido_corte(ps, meta, Path(d))
            prompt = cortes._prompt_corte(meta, "chat: kkkk", ps, trecho, itens)
        self.assertTrue(itens[0].startswith('"resumo"'))                  # entende antes de escrever
        self.assertTrue(any(i.startswith('"chamada"') for i in itens))
        self.assertIn("<transcricao>", prompt)
        self.assertIn("<contexto>", prompt)
        self.assertIn("Davy Jones", prompt)
        self.assertIn("Exemplos do NÍVEL", prompt)
        self.assertIn("[0s] 0:o", prompt)
        for k in ("resumo", "chamada", "motivo_nota"):
            self.assertIn(k, padrao)


class PensarComIa(unittest.TestCase):
    TEXTO = "o carro capotou e você ficou preso no gta seis sem poder mexer"
    BOA = "NO GTA 6 O CARRO CAPOTA E VOCÊ FICA PRESO??"

    def _rodar(self, respostas, qualidade):
        chamadas = []

        def ia(prompt, **k):
            chamadas.append(k)
            return respostas[len(chamadas) - 1]
        meta = {"titulo": "GTA 6 novidades", "canal": "Canal"}
        with tempfile.TemporaryDirectory() as d, patch.object(cortes, "ia_json", side_effect=ia), \
                patch.object(cortes, "IA_PRINCIPAL", "claude"), patch.object(cortes, "IA_QUALIDADE", qualidade), \
                patch.object(cortes, "_guia_estilo", return_value=[]), \
                patch("ia_aprende.termos_confirmados", return_value=[]):
            dados = cortes.pensar_com_ia(_pal(self.TEXTO), meta, Path(d))
        return dados, chamadas

    def test_economico_refaz_no_modelo_forte_quando_vem_generica(self):
        dados, chamadas = self._rodar([{"pergunta": "VOCÊ VIU ISSO??", "titulo": "t"},
                                       {"pergunta": self.BOA, "titulo": "GTA 6: preso no carro"}], "economico")
        self.assertEqual(len(chamadas), 2)
        self.assertTrue(chamadas[1].get("forte"))
        self.assertEqual(dados["pergunta"], self.BOA)

    def test_equilibrado_nao_gasta_chamada_extra(self):
        dados, chamadas = self._rodar([{"pergunta": self.BOA, "titulo": "t"}], "equilibrado")
        self.assertEqual(len(chamadas), 1)
        self.assertEqual(chamadas[0].get("tarefa"), "corte")
        self.assertGreaterEqual(dados["_ia"]["juiz"], 80)

    def test_juiz_usa_a_alternativa_boa(self):
        dados, chamadas = self._rodar([{"pergunta": "VOCÊ VIU ISSO??", "alternativas": [self.BOA]}], "equilibrado")
        self.assertEqual(len(chamadas), 1)
        self.assertEqual(dados["pergunta"], self.BOA)
        self.assertNotIn("VOCÊ VIU ISSO??", dados["alternativas"])

    def test_sem_ia_pergunta_feita_no_pc(self):
        dados, _ = self._rodar([None], "equilibrado")
        self.assertNotEqual(dados["pergunta"], "VOCÊ VIU ISSO??")
        self.assertTrue(dados["_ia"].get("falhou"))
        self.assertEqual(dados["palavras"], self.TEXTO.split())


class Lote(unittest.TestCase):
    def test_numeracao_corte_faltando_e_chaves_uma_vez(self):
        pedidos = [dict(palavras=_pal(t), frames=None, pergunta=None, contexto="", pedir_emoji=False,
                        pedir_serie=False) for t in ("um dois tres quatro", "cinco seis sete oito nove",
                                                     "dez onze doze")]
        prompts = []

        def ia(prompt, **k):
            prompts.append(prompt)
            return {"cortes": [{"corte": 3, "pergunta": "TRES DOZE??"}, {"corte": 1, "pergunta": "UM QUATRO??"}]}
        with tempfile.TemporaryDirectory() as d, patch.object(cortes, "ia_json", side_effect=ia), \
                patch.object(cortes, "IA_PRINCIPAL", "claude"), patch.object(cortes, "_guia_estilo", return_value=[]):
            saida = cortes.pensar_lote(pedidos, {"titulo": "t", "canal": "c"}, Path(d))
        self.assertEqual(prompts[0].count("### CORTE"), 3)
        self.assertEqual(prompts[0].count('"resumo": 1 frase'), 1)        # chaves comuns só 1 vez
        self.assertEqual(saida[0]["pergunta"], "UM QUATRO??")
        self.assertIsNone(saida[1])                                      # esse pede a IA separado
        self.assertEqual(saida[2]["pergunta"], "TRES DOZE??")

    def test_resposta_cortada_descarta_o_ultimo(self):
        pedidos = [dict(palavras=_pal("a b c"), frames=None, pergunta=None, contexto="") for _ in range(2)]

        def ia(prompt, **k):
            ia_motor.registrar_resultado(provedor="claude", truncado=True)
            return {"cortes": [{"corte": 1, "pergunta": "A??"}, {"corte": 2, "pergunta": "B"}]}
        with tempfile.TemporaryDirectory() as d, patch.object(cortes, "ia_json", side_effect=ia), \
                patch.object(cortes, "IA_PRINCIPAL", "claude"), patch.object(cortes, "_guia_estilo", return_value=[]):
            saida = cortes.pensar_lote(pedidos, {"titulo": "t", "canal": "c"}, Path(d))
        self.assertEqual(saida[0]["pergunta"], "A??")
        self.assertIsNone(saida[1])


class Momentos(unittest.TestCase):
    def test_nota_e_momento_fraco_fica_de_fora(self):
        trechos = [(0, 90), (100, 190)]
        frases = [[(1.0, 20.0, "a"), (21.0, 60.0, "b")], [(101.0, 130.0, "c"), (131.0, 170.0, "d")]]
        textos = [[(x, t) for x, _, t in f] for f in frases]
        resposta = [{"frase_inicio": "F1", "frase_fim": "F2", "nota": 8, "motivo": "história completa"},
                    {"frase_inicio": "F3", "frase_fim": "F4", "nota": 2, "motivo": "conversa sem pico"}]
        pedidos, logs = [], []
        with patch.object(cortes, "ia_json", side_effect=lambda p, **k: pedidos.append(p) or resposta), \
                patch.object(cortes, "carregar_config", return_value={}), patch.object(cortes, "IA_PRINCIPAL", "claude"):
            r = momentos._ranquear(trechos, textos, {"titulo": "t", "canal": "c"}, 2, 60, logs.append, frases=frases)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["nota_ia"], 8)
        self.assertIn('"nota"', pedidos[0])
        self.assertTrue(any("nota 8" in str(x) for x in logs))


class FinalLimpo(unittest.TestCase):
    """FFmpeg real, sem IA: o cartaz do fim não fica embaixo de emoji e a capa nunca é o cartaz."""

    def test_emoji_e_capa_longe_do_cartaz(self):
        import subprocess
        import acabamento
        import conclusao_tarefas
        cortes.checar_ffmpeg()
        palavras = [{"t": "palavra", "ini": round(0.5 * i, 2), "fim": round(0.5 * i + 0.4, 2), "confianca": 0.9}
                    for i in range(40)]
        palavras[-1]["t"] = "fim."

        def dados_falsos(st):
            return {"palavras": [p["t"] for p in st["palavras"]], "pergunta": "TESTE DO CARTAZ??", "destaque": [],
                    "titulo": "teste", "hashtags": [], "foto": None, "emoji": "😱", "nota": None, "gancho": 37,
                    "emojis": [[33, "😱"], [38, "🔥"]]}
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            fonte, foto = pasta / "fonte.mp4", pasta / "foto.png"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25",
                            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "21", "-c:v",
                            "libx264", "-c:a", "aac", str(fonte)], check=True, capture_output=True)
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=1280x720",
                            "-frames:v", "1", str(foto)], check=True, capture_output=True)
            cfg = dict(cortes.CONFIG_PADRAO, seguir_rosto=False, tirar_silencios=False, tirar_vicios=False,
                       layout="normal", revisor=False, serie=False, checar_inedito=False, ia_principal="nenhuma",
                       efeito_gancho=False, gancho_inicio=False, guardar_projeto_edicao=True, musica_fundo=False,
                       estilo_corte="faixa", final_corte="cta", capa=True, aparar_ia=False, limpar_abertura=False,
                       emojis_legenda=True, plataforma_alvo="nenhuma")
            with patch.object(cortes, "carregar_config", return_value=cfg), \
                    patch.object(conclusao_tarefas, "BASE", pasta / "jobs"), \
                    patch.object(cortes, "_dados_ia", side_effect=dados_falsos), \
                    patch.object(acabamento, "gerar_capa", wraps=acabamento.gerar_capa) as capa:
                final = cortes.gerar_corte(fonte, 0, 20.5, foto=str(foto), transcricao_teste=palavras,
                                           usar_claude=False, pasta_saida=pasta / "render")
            ficha = json.loads(final.with_suffix(".json").read_text(encoding="utf-8"))
            receita = json.loads((final.parent / ficha["projeto_edicao"] / "receita.json").read_text(encoding="utf-8"))
            cta = next(e for e in receita["extras"] if Path(e["png"]).name.startswith("cta_"))
            emojis = [e for e in receita["extras"] if Path(e["png"]).name.startswith("emoji_")]
            self.assertEqual(len(emojis), 1)                       # o do finzinho saiu
            self.assertLessEqual(emojis[0]["fim"], cta["ini"])      # o outro some antes do cartaz
            t_capa = capa.call_args[0][2]
            self.assertLessEqual(t_capa, receita["duracao"] - 3.4)  # a capa não pega o cartaz do fim


class Postagem(unittest.TestCase):
    def test_chamada_na_legenda_e_no_txt(self):
        ficha = {"titulo": "GTA 6: carro capotado", "hashtags": ["#gta6"], "chamada": "E você, ia capotar?"}
        texto = postagem.legenda_post(ficha)
        self.assertIn("E você, ia capotar?", texto)
        self.assertIn("#gta6", texto)
        with tempfile.TemporaryDirectory() as d:
            saida = Path(d) / "a.mp4"
            cortes.escrever_saidas(saida, ficha, {"canal": "c", "titulo": "t"})
            self.assertIn("E você, ia capotar?", saida.with_suffix(".txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
