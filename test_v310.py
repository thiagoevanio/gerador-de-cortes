"""3.10: zoom nas palavras-chave, final (chamada/loop), zona segura, abertura limpa, A/B de template,
capa e chave do Gemini protegida."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import acabamento
import cofre
import conclusao_tarefas
import cortes
import templates_edicao as te


def _pal(textos, passo=0.5, dur=0.4):
    return [{"t": t, "ini": round(passo * i, 2), "fim": round(passo * i + dur, 2), "confianca": 0.9}
            for i, t in enumerate(textos)]


class Acabamento(unittest.TestCase):
    def test_zona_segura(self):
        todas = acabamento.zona_segura("todas")
        for nome in ("tiktok", "reels", "shorts"):
            z = acabamento.zona_segura(nome)
            self.assertTrue(all(todas[k] >= z[k] for k in z), nome)
        self.assertEqual(acabamento.zona_segura("nenhuma")["baixo"], 0)
        self.assertEqual(acabamento.zona_segura("não existe"), todas)

    def test_tempos_enfase_espacados_e_longe_do_gancho(self):
        pal = _pal(["a"] * 40)
        for i in (0, 4, 5, 12, 20, 30):
            pal[i]["enfase"] = True
        tempos = acabamento.tempos_enfase(pal, gancho_t=10.0, duracao=20.0)
        self.assertEqual(tempos, [2.0, 6.0, 15.0])      # 0 (cedo), 2.5 (colado), 10.0 (gancho) ficam fora
        expr = acabamento.expr_enfase(tempos, 0.08)
        self.assertTrue(expr.startswith("(1+0.080*"))
        self.assertEqual(acabamento.expr_enfase([], 0.08), "1")

    def test_abertura_limpa(self):
        resto = ["hoje", "eu", "vou", "contar", "uma", "história", "muito", "boa"] + ["palavra"] * 30
        t1 = ["Então,", "cara,"] + resto
        self.assertEqual(acabamento.abertura_limpa(_pal(t1), t1), 2)
        t2 = ["Bom", "dia", "pessoal,"] + resto                  # "Bom dia" faz parte da frase: não mexe
        self.assertEqual(acabamento.abertura_limpa(_pal(t2), t2), 0)
        t3 = ["Olha", "isso", "aqui,"] + resto
        self.assertEqual(acabamento.abertura_limpa(_pal(t3), t3), 0)
        self.assertEqual(acabamento.abertura_limpa(_pal(t3), t3, indice_ia=3), 3)     # a IA mandou
        self.assertEqual(acabamento.abertura_limpa(_pal(t3), t3, indice_ia=25), 0)    # longe demais: ignora
        pal = _pal(t1)
        pal[0]["gancho"] = True                                   # nunca corta o gancho fora
        self.assertEqual(acabamento.abertura_limpa(pal, t1), 0)

    def test_emoji_nunca_sobre_a_faixa(self):
        # legenda embaixo: emoji logo acima dela
        self.assertEqual(acabamento.y_acima_ou_abaixo(1920, 480, 66, 150, 980, 480), int(1920 - 480 - 66 * 1.9 - 150))
        # legenda subiu pra perto da faixa (margem 839): emoji vai pra baixo dela, fora da faixa
        y = acabamento.y_acima_ou_abaixo(1920, 839, 66, 150, 980, 480)
        self.assertGreaterEqual(y, 1920 - 839)
        self.assertLessEqual(y + 150, 1920 - 480)

    def test_fim_para_loop(self):
        pal = _pal(["x"] * 30)
        self.assertAlmostEqual(acabamento.fim_para_loop(pal, 20.0), 14.9 + 0.28, places=2)
        self.assertIsNone(acabamento.fim_para_loop(pal, 15.3))
        self.assertIsNone(acabamento.fim_para_loop([], 20))

    def test_template_alternativo_e_diferente(self):
        for nome in te.TEMPLATES:
            self.assertNotEqual(te.alternativo(nome)["nome"], nome)
        self.assertGreater(te.resolver("Hormozi")["efeitos"]["zoom_enfase"], 0)
        self.assertFalse(te.resolver("Clássico")["efeitos"].get("zoom_enfase"))

    def test_validacao_abertura(self):
        pal = _pal(["a", "b", "c"])
        padrao = {"palavras": [p["t"] for p in pal], "pergunta": "P", "destaque": [], "titulo": "t",
                  "hashtags": [], "foto": None, "emoji": "😱", "nota": None, "gancho": None}
        self.assertEqual(cortes._validar_dados({"abertura": "2"}, padrao, pal, None)["abertura"], 2)
        self.assertEqual(cortes._validar_dados({"abertura": "x"}, padrao, pal, None)["abertura"], 0)


class Cofre(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "DPAPI só existe no Windows")
    def test_ida_e_volta(self):
        segredo = "chave-de-teste-123"
        guardado = cofre.proteger(segredo)
        self.assertTrue(guardado.startswith("dpapi:"))
        self.assertNotIn(segredo, guardado)
        self.assertEqual(cofre.revelar(guardado), segredo)
        self.assertEqual(cofre.proteger(guardado), guardado)       # não protege duas vezes
        self.assertEqual(cofre.revelar("texto puro"), "texto puro")
        self.assertEqual(cofre.revelar("dpapi:lixo!!"), "")
        self.assertEqual(cofre.proteger(""), "")

    @unittest.skipUnless(sys.platform == "win32", "DPAPI só existe no Windows")
    def test_config_nunca_grava_chave_aberta(self):
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "config.json"
            with patch.object(cortes, "ARQ_CONFIG", arq):
                cortes.salvar_config({"gemini_api_key": "segredo-xyz", "marca": "@t"})
                self.assertNotIn("segredo-xyz", arq.read_text(encoding="utf-8"))
                self.assertEqual(cortes.carregar_config()["gemini_api_key"], "segredo-xyz")


class CorteCompleto(unittest.TestCase):
    """FFmpeg real, sem internet e sem IA: abertura, chamada no fim, zona segura, capa e versão B."""

    def _fonte(self, pasta, segundos=22):
        fonte = pasta / "fonte.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", str(segundos),
                        "-c:v", "libx264", "-g", "25", "-c:a", "aac", str(fonte)], check=True, capture_output=True)
        return fonte

    def _cfg(self, **extra):
        return dict(cortes.CONFIG_PADRAO, seguir_rosto=False, tirar_silencios=False, tirar_vicios=False,
                    layout="normal", revisor=False, serie=False, checar_inedito=False, ia_principal="nenhuma",
                    efeito_gancho=False, gancho_inicio=False, guardar_projeto_edicao=True, musica_fundo=False,
                    estilo_corte="clean", template_edicao="Viral Dinâmico", legenda_margem=170, **extra)

    def test_cta_zona_capa_abertura_e_versao_b(self):
        cortes.checar_ffmpeg()
        textos = ["Então,", "cara,"] + ["palavra"] * 36 + ["fim."]
        palavras = _pal(textos)
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            fonte = self._fonte(pasta)
            cfg = self._cfg(ab_teste=True, ab_variar="template")
            with patch.object(cortes, "carregar_config", return_value=cfg), \
                    patch.object(conclusao_tarefas, "BASE", pasta / "jobs"):
                final = cortes.gerar_corte(fonte, 0, 20, pergunta="TESTE DA VERSAO NOVA??",
                                           transcricao_teste=palavras, usar_claude=False,
                                           pasta_saida=pasta / "render")
            ficha = json.loads(final.with_suffix(".json").read_text(encoding="utf-8"))
            # abertura: "Então, cara," saiu
            trans = json.loads(final.with_suffix(".transcricao.json").read_text(encoding="utf-8"))["palavras"]
            self.assertEqual(trans[0]["t"], "palavra")
            self.assertLess(cortes.duracao_video(final), 19.6)
            # zona segura: legenda acima da área dos botões
            self.assertGreaterEqual(ficha["revisor"]["margem"], acabamento.zona_segura("todas")["baixo"])
            # chamada no fim
            receita = json.loads((final.parent / ficha["projeto_edicao"] / "receita.json")
                                 .read_text(encoding="utf-8"))
            cta = [e for e in receita["extras"] if Path(e["png"]).name.startswith("cta_")]
            self.assertEqual(len(cta), 1)
            self.assertGreater(cta[0]["ini"], receita["duracao"] - 3)
            # capa
            capa = final.with_suffix(".capa.jpg")
            self.assertTrue(capa.is_file())
            self.assertEqual(ficha["capa"], capa.name)
            # versão B com outro template
            ficha_b = json.loads(final.with_name(final.stem + "_B.json").read_text(encoding="utf-8"))
            self.assertTrue(final.with_name(final.stem + "_B.mp4").is_file())
            self.assertEqual(ficha["template"], "Viral Dinâmico")
            self.assertEqual(ficha_b["template"], "Hormozi")
            self.assertEqual(ficha_b["pergunta"], ficha["pergunta"])
            self.assertEqual((ficha["variante"], ficha_b["variante"], ficha["ab_variou"]), ("A", "B", "template"))

    def test_final_em_loop_e_zoom_nas_palavras_chave(self):
        cortes.checar_ffmpeg()
        textos = ["Essa"] + ["palavra"] * 27 + ["acabou."]
        palavras = _pal(textos)                       # última fala termina em 14.4s; o vídeo tem 20s
        for i in (6, 14, 22):
            palavras[i]["enfase"] = True
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            fonte = self._fonte(pasta)
            cfg = self._cfg(final_corte="loop", plataforma_alvo="nenhuma", capa=False)
            with patch.object(cortes, "carregar_config", return_value=cfg), \
                    patch.object(conclusao_tarefas, "BASE", pasta / "jobs"):
                final = cortes.gerar_corte(fonte, 0, 20, pergunta="TESTE DO LOOP??", transcricao_teste=palavras,
                                           usar_claude=False, pasta_saida=pasta / "render")
            ficha = json.loads(final.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertAlmostEqual(cortes.duracao_video(final), 14.4 + 0.28, delta=0.4)
            receita = json.loads((final.parent / ficha["projeto_edicao"] / "receita.json")
                                 .read_text(encoding="utf-8"))
            self.assertEqual(receita["estilo_render"]["enfase"], [3.0, 7.0, 11.0])
            self.assertFalse([e for e in receita["extras"] if Path(e["png"]).name.startswith("cta_")])
            self.assertFalse(final.with_suffix(".capa.jpg").exists())
            self.assertLess(ficha["revisor"]["margem"], 520)      # zona desligada: 170 + 330 do clean


if __name__ == "__main__":
    unittest.main()
