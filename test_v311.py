"""3.11: IA apara começo/fim, template que aprende com as views e troca de pergunta sem IA."""
import json
import random
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import acabamento
import conclusao_tarefas
import cortes
import projeto_edicao
import resultados
import templates_edicao as te


def _pal(textos, passo=0.5, dur=0.4):
    return [{"t": t, "ini": round(passo * i, 2), "fim": round(passo * i + dur, 2), "confianca": 0.9}
            for i, t in enumerate(textos)]


class Aparar(unittest.TestCase):
    def test_apara_as_duas_pontas(self):
        pal = _pal(["x"] * 80)                       # 40s
        t0, t1 = acabamento.aparar_pela_ia(pal, (6, 70), 40.0)
        self.assertAlmostEqual(t0, 2.95, places=2)   # meio entre a palavra 5 e a 6
        self.assertAlmostEqual(t1, 35.45, places=2)

    def test_travas(self):
        pal = _pal(["x"] * 80)
        self.assertIsNone(acabamento.aparar_pela_ia(pal, (0, 79), 40.0))         # nada a aparar
        self.assertIsNone(acabamento.aparar_pela_ia(pal, (30, 40), 40.0))        # sobraria pouco
        self.assertEqual(acabamento.aparar_pela_ia(pal, (40, 79), 40.0), None)   # começo além do limite
        self.assertIsNone(acabamento.aparar_pela_ia(pal, ("a", 3), 40.0))
        pal[2]["gancho"] = True                                                   # gancho nunca fica de fora
        self.assertEqual(acabamento.aparar_pela_ia(pal, (6, 70), 40.0)[0], 0.0)

    def test_destaque_auto(self):
        self.assertEqual(acabamento.destaque_auto("O CASIMIRO NÃO ACREDITOU NISSO??"), ["ACREDITOU", "CASIMIRO"])
        self.assertEqual(acabamento.destaque_auto("E AÍ??"), [])


class TemplateAprende(unittest.TestCase):
    def test_escolha(self):
        d = {"Hormozi": {"n": 8, "indice": 1.6}, "Notícia": {"n": 6, "indice": 0.9},
             "Neon": {"n": 2, "indice": 5.0}}                                    # Neon: amostra pequena
        sem_explorar = random.Random(3)
        sem_explorar.random = lambda: 0.99
        self.assertEqual(te.escolher_aprendido("Notícia", d, sem_explorar), "Hormozi")
        self.assertEqual(te.escolher_aprendido("Hormozi", d, sem_explorar), "Hormozi")
        explorando = random.Random(3)
        explorando.random = lambda: 0.01
        self.assertEqual(te.escolher_aprendido("Notícia", d, explorando), "Notícia")
        self.assertEqual(te.escolher_aprendido("Notícia", {"Hormozi": d["Hormozi"]}, sem_explorar), "Notícia")
        pouco = {"Hormozi": {"n": 8, "indice": 1.02}, "Notícia": {"n": 6, "indice": 1.0}}
        self.assertEqual(te.escolher_aprendido("Notícia", pouco, sem_explorar), "Notícia")   # vantagem pequena

    def test_desempenho_relativo_por_perfil(self):
        def ficha(tpl, views, perfil="Padrão"):
            return (Path("x.mp4"), {"template": tpl, "perfil": perfil, "views_24h": {"youtube": views}})
        lista = [ficha("Hormozi", v) for v in (300, 400, 500)] + [ficha("Notícia", v) for v in (100, 100, 200)] \
            + [ficha("Neon", 99999, "Outro")]
        with patch.object(resultados, "fichas", return_value=lista):
            d = resultados.desempenho_templates("Padrão")
        self.assertEqual(set(d), {"Hormozi", "Notícia"})
        self.assertGreater(d["Hormozi"]["indice"], d["Notícia"]["indice"])
        self.assertEqual(d["Hormozi"]["n"], 3)


class Fluxo(unittest.TestCase):
    """FFmpeg real, sem internet e sem IA."""

    def setUp(self):
        # o que a IA aprende (gosto do dono, glossário) vai pra arquivos temporários, nunca pros de verdade
        import ia_aprende
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for nome in ("ARQ_GOSTO", "ARQ_GLOSSARIO"):
            p = patch.object(ia_aprende, nome, Path(tmp.name) / f"{nome.lower()}.json")
            p.start()
            self.addCleanup(p.stop)

    def _fonte(self, pasta, segundos=42):
        fonte = pasta / "fonte.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", str(segundos),
                        "-c:v", "libx264", "-g", "25", "-c:a", "aac", str(fonte)], check=True, capture_output=True)
        return fonte

    def _cfg(self, **extra):
        base = dict(cortes.CONFIG_PADRAO, seguir_rosto=False, tirar_silencios=False, tirar_vicios=False,
                    layout="normal", revisor=False, serie=False, checar_inedito=False, ia_principal="nenhuma",
                    efeito_gancho=False, gancho_inicio=False, guardar_projeto_edicao=True, musica_fundo=False,
                    template_edicao="Viral Dinâmico", capa=True)
        base.update(extra)
        return base

    def test_ia_apara_o_trecho(self):
        cortes.checar_ffmpeg()
        textos = ["resto", "do", "assunto", "anterior."] + ["palavra"] * 70 + ["tchau", "pessoal", "até", "mais."]
        palavras = _pal(textos)                       # 78 palavras, 39s

        def dados_falsos(st):
            return {"palavras": [p["t"] for p in st["palavras"]], "pergunta": "TESTE DE APARAR??", "destaque": [],
                    "titulo": "teste aparar", "hashtags": [], "foto": None, "emoji": "😱", "nota": None,
                    "gancho": None, "aparar": [4, 73]}
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            fonte = self._fonte(pasta)
            cfg = self._cfg(estilo_corte="clean", final_corte="nada")
            with patch.object(cortes, "carregar_config", return_value=cfg), \
                    patch.object(cortes, "_dados_ia", side_effect=dados_falsos), \
                    patch.object(conclusao_tarefas, "BASE", pasta / "jobs"):
                final = cortes.gerar_corte(fonte, 0, 39.5, transcricao_teste=palavras, usar_claude=False,
                                           pasta_saida=pasta / "render")
            trans = json.loads(final.with_suffix(".transcricao.json").read_text(encoding="utf-8"))["palavras"]
            self.assertEqual(trans[0]["t"], "palavra")
            self.assertEqual(trans[-1]["t"], "palavra")
            self.assertEqual(len(trans), 70)
            self.assertAlmostEqual(cortes.duracao_video(final), 35.2, delta=0.8)

    def _trocar(self, estilo):
        cortes.checar_ffmpeg()
        palavras = _pal(["Essa"] + ["palavra"] * 24 + ["acabou."])
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            fonte = self._fonte(pasta, 15)
            foto = pasta / "foto.png"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=1280x720",
                            "-frames:v", "1", str(foto)], check=True, capture_output=True)
            cfg = self._cfg(estilo_corte=estilo)
            with patch.object(cortes, "carregar_config", return_value=cfg), \
                    patch.object(conclusao_tarefas, "BASE", pasta / "jobs"):
                final = cortes.gerar_corte(fonte, 0, 14, pergunta="PERGUNTA ORIGINAL??", foto=str(foto),
                                           transcricao_teste=palavras, usar_claude=False,
                                           pasta_saida=pasta / "render")
                self.assertTrue(projeto_edicao.pode_trocar_pergunta(final))
                with patch.object(cortes, "ia_json", side_effect=AssertionError("não pode chamar IA")), \
                        patch.object(cortes, "baixar_trecho", side_effect=AssertionError("não pode baixar")):
                    novo = projeto_edicao.trocar_pergunta(final, "o casimiro falou isso mesmo??")
                ficha = json.loads(novo.with_suffix(".json").read_text(encoding="utf-8"))
                self.assertEqual(ficha["pergunta"], "O CASIMIRO FALOU ISSO MESMO??")
                import ia_aprende                          # a troca vira exemplo do gosto do dono pra IA
                self.assertIn('por "O CASIMIRO FALOU ISSO MESMO??"', ia_aprende.gosto_para_prompt(ficha.get("perfil")))
                self.assertIn("PERGUNTA ORIGINAL??", ficha["perguntas_alternativas"])
                self.assertEqual(ficha["refeito_de"], final.name)
                self.assertAlmostEqual(cortes.duracao_video(novo), cortes.duracao_video(final), delta=0.3)
                self.assertTrue(novo.with_suffix(".srt").is_file())
                self.assertTrue(novo.with_suffix(".capa.jpg").is_file())
                receita = json.loads((novo.parent / ficha["projeto_edicao"] / "receita.json")
                                     .read_text(encoding="utf-8"))
                self.assertNotEqual(ficha["projeto_edicao"],
                                    json.loads(final.with_suffix(".json").read_text(encoding="utf-8"))["projeto_edicao"])
                if estilo == "clean":
                    self.assertTrue(any("CASIMIRO" in x[2] for x in receita["textos_extra"]))
                else:
                    self.assertTrue((novo.parent / ficha["projeto_edicao"] / receita["faixa"]).is_file()
                                    or (novo.parent / ficha["projeto_edicao"] / receita["topo"]).is_file())
                # a pergunta tem que mudar NA IMAGEM (não só na ficha)
                self.assertGreater(self._diferenca(final, novo), 2.0)
                # dá pra trocar de novo a partir do corte novo (a receita nova é completa)
                de_novo = projeto_edicao.trocar_pergunta(novo, "TERCEIRA VERSÃO??")
                self.assertTrue(de_novo.is_file())
                self.assertGreater(self._diferenca(novo, de_novo), 2.0)
                self.assertLess(self._diferenca(novo, novo), 0.01)
                self.assertTrue(final.is_file())          # o original continua inteiro

    @staticmethod
    def _diferenca(a, b, t=1.0):
        """Diferença média (0-255) entre os dois vídeos na metade de cima do quadro, onde fica a pergunta."""
        import numpy as np
        from PIL import Image
        quadros = []
        for arq in (a, b):
            png = Path(arq).with_suffix(".cmp.png")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", str(arq), "-frames:v", "1",
                            str(png)], check=True, capture_output=True)
            img = Image.open(png).convert("L")
            quadros.append(np.asarray(img.crop((0, 0, img.width, img.height // 2)), dtype="float32"))
            img.close()
            png.unlink()
        return float(np.abs(quadros[0] - quadros[1]).mean())

    def test_trocar_pergunta_clean(self):
        self._trocar("clean")

    def test_trocar_pergunta_com_faixa(self):
        self._trocar("faixa")

    def test_corte_antigo_nao_tem_troca_rapida(self):
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "a.mp4"
            v.write_bytes(b"0")
            v.with_suffix(".json").write_text(json.dumps({"pergunta": "X"}), encoding="utf-8")
            self.assertFalse(projeto_edicao.pode_trocar_pergunta(v))


if __name__ == "__main__":
    unittest.main()
