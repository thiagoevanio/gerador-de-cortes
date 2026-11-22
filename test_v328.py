"""3.28: 🎞 Supercut — os melhores lances num corte só, em contagem (#N … #1), com whoosh e flash na virada."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import conclusao_tarefas
import cortes
import supercut


class Escolha(unittest.TestCase):
    def test_melhores_em_ordem_crescente(self):
        ms = [{"inicio": 10, "nota_ia": 6}, {"inicio": 50, "nota_ia": 9}, {"inicio": 90, "nota_ia": 4},
              {"inicio": 130, "evidencias": {"avaliacao": {"nota": 8}}}, {"inicio": 170}]
        ordem = [m["inicio"] for m in supercut.escolher(ms, 3)]
        self.assertEqual(ordem, [10, 130, 50])          # 6, 8, 9: o melhor fecha o vídeo

    def test_janela_mais_agitada_comecando_no_respiro(self):
        sr = 16000
        rng = np.random.default_rng(0)
        audio = rng.normal(0, 0.02, sr * 30).astype("float32")
        audio[sr * 18: sr * 24] = rng.normal(0, 0.5, sr * 6)   # a reação: 18 s → 24 s
        a, b = supercut.melhor_janela(audio, 8)
        self.assertLessEqual(a, 18.2)
        self.assertGreaterEqual(b, 23.8)
        self.assertAlmostEqual(b - a, 8, delta=1.7)
        self.assertEqual(supercut.melhor_janela(audio[: sr * 5], 8), (0.0, 5.0))   # curto: inteiro


class Marcas(unittest.TestCase):
    def _pal(self):
        # 3 lances de 10 s (0, 10, 20), cada um com a 1ª fala 0,4 s depois do começo
        return [{"t": f"p{j}", "ini": round(s + 0.4 + j * 0.5, 2), "fim": round(s + 0.4 + j * 0.5 + 0.4, 2)}
                for s in (0, 10, 20) for j in range(19)]

    def test_marcas_viram_contagem(self):
        ps = supercut.marcar_palavras(self._pal(), [0.0, 10.0, 20.0])
        self.assertEqual([p["supercut"] for p in ps if p.get("supercut")], [1, 2, 3])
        self.assertEqual([t for _, t in supercut.viradas(ps)], [0.0, 10.0, 20.0])
        textos, tempos = supercut.contagem(ps, 3, 30.0, depois_do_gancho=3.6)
        self.assertEqual([t[2][-2:] for t in textos], ["#3", "#2", "#1"])
        self.assertEqual(textos[0][0], 3.6)               # o 1º selo espera a pergunta do gancho sair
        self.assertIn("&H0000E6FF&", textos[2][2])        # o #1 em amarelo
        self.assertEqual(tempos, [10.0, 20.0])            # whoosh nas viradas
        import legendas                                   # a legenda quebra na virada (não emenda os lances)
        blocos = legendas.blocos_legenda(ps, [p["t"] for p in ps], n=4)
        marcadas = {p["ini"] for p in ps if p.get("supercut")}
        self.assertEqual({b[0]["ini"] for b in blocos} & marcadas, marcadas)   # cada lance abre um bloco

    def test_marca_acompanha_corte_no_comeco(self):
        ps = supercut.marcar_palavras(self._pal(), [0.0, 10.0, 20.0])
        cortado = [dict(p, ini=round(p["ini"] - 3, 2), fim=round(p["fim"] - 3, 2)) for p in ps if p["ini"] >= 3]
        self.assertEqual([t for _, t in supercut.viradas(cortado)], [7.0, 17.0])   # o lance 1 perdeu a marca


def _clipe(destino, freq, segundos=12):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25",
                    "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000", "-t", str(segundos),
                    "-c:v", "libx264", "-g", "25", "-c:a", "aac", str(destino)], check=True, capture_output=True)
    return destino


class SupercutMontado(unittest.TestCase):
    def test_contagem_whoosh_e_sem_previa(self):
        cortes.checar_ffmpeg()
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            pecas = [(_clipe(pasta / f"c{i}.mp4", 300 + 200 * i), 1.0, 9.0) for i in range(3)]
            junto, marcas = supercut.juntar(pecas, pasta / "junto.mp4")
            self.assertEqual(marcas, [0.0, 8.0, 16.0])
            self.assertAlmostEqual(cortes.duracao_video(junto), 24, delta=0.3)
            palavras = [{"t": "palavra", "ini": round(0.3 + i * 0.5, 2), "fim": round(0.3 + i * 0.5 + 0.4, 2),
                         "confianca": 0.9} for i in range(46)]
            cfg = dict(cortes.CONFIG_PADRAO, seguir_rosto=False, tirar_silencios=False, tirar_vicios=False,
                       layout="normal", revisor=False, serie=True, checar_inedito=False, ia_principal="nenhuma",
                       efeito_gancho=False, gancho_inicio=True, guardar_projeto_edicao=True, musica_fundo=False,
                       estilo_corte="clean", template_edicao="Viral Dinâmico", legenda_margem=170)
            with patch.object(cortes, "carregar_config", return_value=cfg), \
                    patch.object(conclusao_tarefas, "BASE", pasta / "jobs"), supercut._ligado(marcas, 3):
                final = cortes.gerar_corte(junto, 0, 24, pergunta="OS 3 MELHORES LANCES??",
                                           transcricao_teste=palavras, usar_claude=False,
                                           pasta_saida=pasta / "render")
            ficha = json.loads(final.with_suffix(".json").read_text(encoding="utf-8"))
            receita = json.loads((final.parent / ficha["projeto_edicao"] / "receita.json").read_text(encoding="utf-8"))
            selos = [t for t in receita["textos_extra"] if t[3] == "Aviso"]
            self.assertEqual([s[2][-2:] for s in selos], ["#3", "#2", "#1"])
            whoosh = [s for s in receita["estilo_render"]["sfx"] if "whoosh" in s["arquivo"]]
            self.assertEqual(len(whoosh), 2)
            self.assertIsNone(receita.get("previa"))         # a contagem já é o gancho: sem prévia repetida
            self.assertAlmostEqual(cortes.duracao_video(final), 24, delta=1.0)


if __name__ == "__main__":
    unittest.main()
