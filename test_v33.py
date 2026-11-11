"""Testes da 3.3: economia de IA/CPU e funções religadas. Sem rede e sem IA de verdade."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cortes
import efeitos
import momentos


class Economia(unittest.TestCase):
    def test_grafico_mais_repetidos_nao_gasta_ia(self):
        info = {"title": "Vídeo", "uploader": "Canal", "duration": 600,
                "heatmap": [{"start_time": i * 10, "end_time": i * 10 + 10, "value": 1.0 if i == 30 else 0.1}
                            for i in range(60)]}
        with patch.object(momentos, "_info_url", return_value=info), \
                patch.object(momentos, "_baixar_audio", side_effect=AssertionError("não devia baixar")), \
                patch.object(cortes, "ia_json", side_effect=AssertionError("não devia chamar IA")), \
                patch.object(cortes, "carregar_config", return_value={}):
            achados, meta = momentos.achar_momentos("https://www.youtube.com/watch?v=x", 1, 60, log=lambda *_: None)
        self.assertEqual(len(achados), 1)
        self.assertIn("repetido", achados[0]["motivo"])

    def test_prompt_curto_por_padrao(self):
        pedidos = []
        with patch.object(cortes, "ia_json", side_effect=lambda p, **k: pedidos.append(p) or {}), \
                patch.object(cortes, "carregar_config", return_value={}):
            momentos._ranquear([(0, 90)], [[(1, "oi")]], {"titulo": "t", "canal": "c"}, 1, 60, lambda *_: None)
        self.assertNotIn("versoes", pedidos[0])
        self.assertNotIn("evidencia", pedidos[0])

    def test_prompt_detalhado_na_central(self):
        pedidos = []
        with patch.object(cortes, "ia_json", side_effect=lambda p, **k: pedidos.append(p) or {}), \
                patch.object(cortes, "carregar_config", return_value={}):
            momentos._ranquear([(0, 90)], [[(1, "oi")]], {"titulo": "t", "canal": "c"}, 1, 60,
                               lambda *_: None, completo=True)
        self.assertIn("versoes", pedidos[0])


class Revisor(unittest.TestCase):
    def test_corta_resto_de_frase_no_fim(self):
        palavras = [dict(t="Começo." if i == 52 else "palavra", ini=i * 0.5, fim=i * 0.5 + 0.4) for i in range(60)]
        _, fim = efeitos.ajustar_frase(palavras, [p["t"] for p in palavras], 30.0)
        self.assertGreater(fim, 0)          # terminou falando sem ponto → volta pro fim da última frase


class CacheIA(unittest.TestCase):
    def test_nova_tentativa_nao_paga_a_ia_de_novo(self):
        import subprocess
        import conclusao_tarefas
        cortes.checar_ffmpeg()
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            fonte = pasta / "fonte.mp4"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=25",
                            "-f", "lavfi", "-i", "sine=frequency=440", "-t", "3", "-c:v", "libx264",
                            "-c:a", "aac", str(fonte)], check=True)
            palavras = [dict(t=t, ini=i * .4, fim=i * .4 + .3) for i, t in enumerate(["Isso", "é", "um", "teste."])]
            cfg = dict(cortes.CONFIG_PADRAO, seguir_rosto=False, tirar_silencios=False, tirar_vicios=False,
                       layout="normal", revisor=False, serie=False, checar_inedito=False, efeito_gancho=False,
                       gancho_inicio=False, guardar_projeto_edicao=False, emojis_legenda=False)
            chamadas = []

            def ia_falsa(palavras, *a, **k):
                chamadas.append(1)
                return {"palavras": [p["t"] for p in palavras], "pergunta": "DEU CERTO??", "destaque": [],
                        "titulo": "Teste cache", "hashtags": [], "foto": 1, "nota": 8, "gancho": None}
            with patch.object(cortes, "carregar_config", return_value=cfg), \
                    patch.object(conclusao_tarefas, "BASE", pasta / "jobs"), \
                    patch.object(cortes, "pensar_com_ia", side_effect=ia_falsa), \
                    patch.object(cortes, "renderizar", side_effect=[RuntimeError("falha no render"), None]):
                with self.assertRaises(RuntimeError):      # 1ª tentativa: IA ok, render falha
                    cortes.gerar_corte(fonte, 0, 2, transcricao_teste=palavras, pasta_saida=pasta / "r",
                                       _job_id="job_cache")
                try:                                       # 2ª tentativa (a fila repete)
                    cortes.gerar_corte(fonte, 0, 2, transcricao_teste=palavras, pasta_saida=pasta / "r",
                                       _job_id="job_cache")
                except RuntimeError:
                    pass                                   # o render falso não cria o mp4; tudo bem aqui
            self.assertEqual(len(chamadas), 1)


class Falantes(unittest.TestCase):
    def test_volta_pro_movimento_quando_voz_inconclusiva(self):
        import identificacao_falante
        with patch.object(identificacao_falante, "associar",
                          side_effect=lambda v, a, b, m: ([None] * len(v), {"confiavel": False})), \
                patch.object(identificacao_falante, "vetores_voz", side_effect=lambda audio, tempos: [None] * len(tempos)):
            with tempfile.TemporaryDirectory() as d:
                import subprocess
                video = Path(d) / "v.mp4"
                # esquerda pisca nos primeiros 6s, direita nos 6s seguintes (como em test_midia)
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                                "color=gray:s=320x180:d=12,format=yuv420p", "-f", "lavfi", "-i",
                                "sine=d=12", "-filter_complex",
                                "[0:v]drawbox=x=40:y=95:w=60:h=20:color=white:t=fill:"
                                "enable='lt(t,6)*lt(mod(t,0.4),0.2)',"
                                "drawbox=x=220:y=95:w=60:h=20:color=white:t=fill:"
                                "enable='gte(t,6)*lt(mod(t,0.4),0.2)'[v]",
                                "-map", "[v]", "-map", "1:a", "-shortest", str(video)], check=True)
                segs = efeitos.falantes(video, (0.22, 0.45, 0.25, 0.25), (0.78, 0.45, 0.25, 0.25),
                                        palavras=[{"ini": 0, "fim": 12}])
        quem = {q for _, _, q in segs}
        self.assertTrue({"A", "B"} <= quem, segs)


if __name__ == "__main__":
    unittest.main()


class DuracaoYoutube(unittest.TestCase):
    def test_trilhas_de_tamanhos_diferentes_nao_derrubam_o_corte(self):
        import subprocess
        from qualidade import inspecionar
        cortes.checar_ffmpeg()
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "trecho.mp4"      # vídeo 10s + áudio 7s (como o trecho baixado do YouTube)
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:d=10",
                            "-f", "lavfi", "-i", "sine=d=7", "-c:v", "libx264", "-c:a", "aac", str(v)], check=True)
            self.assertAlmostEqual(cortes._duracao_util(v), 7, delta=0.3)
            curto = Path(d) / "saida.mp4"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(v), "-shortest", "-c", "copy", str(curto)], check=True)
            r = inspecionar(curto, 10, exigir_audio=True, aprofundar=False)   # esperado errado (10s)
            self.assertTrue(r["aprovado"], r)
            self.assertTrue(r["avisos"])


class ChatVod(unittest.TestCase):
    def _salvar(self, d, nome, texto):
        p = Path(d) / nome
        p.write_text(texto, encoding="utf-8")
        return p

    def test_le_os_formatos(self):
        import chat_vod
        with tempfile.TemporaryDirectory() as d:
            td = self._salvar(d, "td.json", json.dumps({"comments": [
                {"content_offset_seconds": 12.5, "commenter": {"name": "ana"}, "message": {"body": "KKKKK"}}]}))
            cd = self._salvar(d, "cd.json", json.dumps([{"time_in_seconds": 3, "author": {"name": "b"},
                                                         "message": "oi"}]))
            yt = self._salvar(d, "x.live_chat.json", json.dumps({"replayChatItemAction": {
                "videoOffsetTimeMsec": "61000", "actions": [{"addChatItemAction": {"item": {
                    "liveChatTextMessageRenderer": {"message": {"runs": [{"text": "que isso"}]},
                                                    "authorName": {"simpleText": "c"}}}}}]}}) + "\n")
            tx = self._salvar(d, "c.txt", "[0:01:05] dudu: caralho\n[1:00:00] eva: kkk\n")
            self.assertEqual(chat_vod.ler_arquivo(td), [(12.5, "ana", "KKKKK")])
            self.assertEqual(chat_vod.ler_arquivo(cd), [(3.0, "b", "oi")])
            self.assertEqual(chat_vod.ler_arquivo(yt), [(61.0, "c", "que isso")])
            self.assertEqual(chat_vod.ler_arquivo(tx)[1], (3600.0, "eva", "kkk"))

    def test_acha_o_pico_antes_da_reacao(self):
        import chat_vod
        import random
        rnd = random.Random(3)
        msgs = [(t + rnd.random(), f"u{rnd.randint(1, 40)}", "papo normal") for t in range(0, 1800, 4)]
        msgs += [(1000 + rnd.random() * 12, f"x{i}", "KKKKKKK CLIPA") for i in range(120)]   # explosão aos 1000s
        p = chat_vod.picos(sorted(msgs), 1800, 60, n=3)
        self.assertTrue(p)
        self.assertLess(p[0]["ini"], 1000)          # o trecho começa ANTES da reação
        self.assertGreater(p[0]["fim"], 1000)
        self.assertIn("clipa", p[0]["resumo"])

    def test_id_do_vod(self):
        import chat_vod
        self.assertEqual(chat_vod.id_vod_twitch("https://www.twitch.tv/videos/2290012345"), "2290012345")
        self.assertIsNone(chat_vod.id_vod_twitch("https://www.twitch.tv/gaules"))

    def test_twitch_pagina_pelo_segundo(self):
        import chat_vod
        paginas = [
            [{"data": {"video": {"comments": {"edges": [
                {"node": {"id": "1", "contentOffsetSeconds": 5, "commenter": {"login": "a"},
                          "message": {"fragments": [{"text": "oi"}]}}}], "pageInfo": {"hasNextPage": True}}}}}],
            [{"data": {"video": {"comments": {"edges": [
                {"node": {"id": "2", "contentOffsetSeconds": 9, "commenter": {"login": "b"},
                          "message": {"fragments": [{"text": "kkk"}]}}}], "pageInfo": {"hasNextPage": False}}}}}]]
        pedidos = []

        class Resp:
            def __init__(self, dados):
                self.dados = dados

            def read(self):
                return json.dumps(self.dados).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def abrir(req, timeout=0):
            pedidos.append(json.loads(req.data)[0]["variables"]["contentOffsetSeconds"])
            return Resp(paginas[len(pedidos) - 1])
        with patch("urllib.request.urlopen", side_effect=abrir):
            msgs = chat_vod.baixar_twitch("123", log=lambda *_: None)
        self.assertEqual(msgs, [(5.0, "a", "oi"), (9.0, "b", "kkk")])
        self.assertEqual(pedidos, [0, 6])


class MomentoExato(unittest.TestCase):
    def test_encaixa_nas_pausas_entre_frases(self):
        frases = [(10.0, 14.0, "a"), (15.0, 20.0, "b"), (21.0, 40.0, "c"), (42.0, 50.0, "d")]
        a, b = momentos.encaixar(16.3, 41.0, frases)      # IA mandou no meio da frase b
        self.assertEqual(a, 14.75)                         # 0,25s antes da frase b (dentro da pausa)
        self.assertEqual(b, 40.45)                         # fim da frase c + folga (antes da d)

    def test_ia_escolhe_pelos_numeros_das_frases(self):
        trechos = [(100, 190)]
        frases = [[(100.0, 104.0, "enrolação."), (104.5, 120.0, "Aí ele falou"), (121.0, 160.0, "e deu briga."),
                   (161.0, 189.0, "outra coisa")]]
        resposta = {"momentos": [{"frase_inicio": "F2", "frase_fim": 3, "inicio": 0, "fim": 0, "motivo": "x"}]}
        with patch.object(cortes, "ia_json", return_value=resposta), \
                patch.object(cortes, "carregar_config", return_value={}):
            r = momentos._ranquear(trechos, [[(x, t) for x, _, t in frases[0]]], {"titulo": "t", "canal": "c"},
                                   1, 60, lambda *_: None, frases=frases)
        self.assertEqual((r[0]["inicio"], r[0]["fim"]), (104.25, 160.45))


class Lote(unittest.TestCase):
    def test_tres_cortes_uma_chamada(self):
        import subprocess
        import conclusao_tarefas
        cortes.checar_ffmpeg()
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            fonte = pasta / "fonte.mp4"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=25",
                            "-f", "lavfi", "-i", "sine=frequency=440", "-t", "9", "-c:v", "libx264",
                            "-c:a", "aac", str(fonte)], check=True)
            palavras = [dict(t=t, ini=i * .4, fim=i * .4 + .3) for i, t in enumerate(["Isso", "é", "um", "teste."])]
            cfg = dict(cortes.CONFIG_PADRAO, seguir_rosto=False, tirar_silencios=False, tirar_vicios=False,
                       layout="normal", revisor=False, serie=False, checar_inedito=False, efeito_gancho=False,
                       gancho_inicio=False, guardar_projeto_edicao=False, emojis_legenda=False, ab_teste=False,
                       espanhol=False, ia_principal="claude")
            chamadas = []

            def ia(prompt, **k):
                chamadas.append(prompt)
                n = prompt.count("### CORTE")
                return {"cortes": [{"palavras": [p["t"] for p in palavras], "pergunta": f"CORTE {i}??",
                                    "titulo": f"Titulo {i}", "hashtags": [], "destaque": [], "foto": 1, "nota": 8}
                                   for i in range(n)]}
            with patch.object(cortes, "carregar_config", return_value=cfg), \
                    patch.object(conclusao_tarefas, "BASE", pasta / "jobs"), \
                    patch.object(cortes, "ia_json", side_effect=ia):
                cortes.aplicar_config(cfg)
                saidas = cortes.gerar_cortes_lote(fonte, [{"inicio": 0, "fim": 2}, {"inicio": 3, "fim": 5},
                                                          {"inicio": 6, "fim": 8}],
                                                  _job_ids=["l1", "l2", "l3"], transcricao_teste=palavras,
                                                  pasta_saida=pasta / "r", topo="frame")
                self.assertEqual(len(chamadas), 1)
                self.assertTrue(all(s and s.exists() for s in saidas))
                self.assertEqual(len({json.loads(s.with_suffix(".json").read_text())["pergunta"] for s in saidas}), 3)
                # de novo: tudo já pronto → nenhuma IA, nenhum render
                cortes.gerar_cortes_lote(fonte, [{"inicio": 0, "fim": 2}, {"inicio": 3, "fim": 5},
                                                 {"inicio": 6, "fim": 8}], _job_ids=["l1", "l2", "l3"],
                                         transcricao_teste=palavras, pasta_saida=pasta / "r")
                self.assertEqual(len(chamadas), 1)


class Longo(unittest.TestCase):
    def test_janela_abre_contexto(self):
        import longo
        self.assertEqual(longo.janela(600, 660, 240), (492.0, 732.0))      # 60% antes, 40% depois
        self.assertEqual(longo.janela(10, 70, 240), (0.0, 240.0))           # não passa do começo
        self.assertEqual(longo.janela(900, 960, 240, total=1000), (760.0, 1000.0))

    def test_curto_e_longo_do_mesmo_momento(self):
        import subprocess
        import conclusao_tarefas
        cortes.checar_ffmpeg()
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            fonte = pasta / "fonte.mp4"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25",
                            "-f", "lavfi", "-i", "sine=frequency=330", "-t", "40", "-c:v", "libx264",
                            "-c:a", "aac", str(fonte)], check=True)
            palavras = [dict(t=t, ini=i * .4, fim=i * .4 + .3) for i, t in enumerate(["Isso", "é", "um", "teste."])]
            cfg = dict(cortes.CONFIG_PADRAO, seguir_rosto=False, tirar_silencios=False, tirar_vicios=False,
                       layout="normal", revisor=False, serie=False, checar_inedito=False, efeito_gancho=False,
                       gancho_inicio=False, guardar_projeto_edicao=False, emojis_legenda=False, ab_teste=False,
                       espanhol=False, duracao_longo_seg=20, ia_principal="nenhuma")
            longas = [dict(t=f"palavra{i}", ini=i * .5, fim=i * .5 + .4) for i in range(30)]
            with patch.object(cortes, "carregar_config", return_value=cfg), \
                    patch.object(conclusao_tarefas, "BASE", pasta / "jobs"), \
                    patch.object(cortes, "transcrever", return_value=longas):
                cortes.aplicar_config(cfg)
                curto = cortes.gerar_corte(fonte, 15, 20, pergunta="TESTE??", transcricao_teste=palavras,
                                           usar_claude=False, pasta_saida=pasta / "r", formato="ambos")
            self.assertTrue(curto.exists())
            longos = list((pasta / "r" / "longos").glob("*.mp4"))
            self.assertEqual(len(longos), 1)
            w, h = cortes.info_video(longos[0])
            self.assertEqual((w, h), (1920, 1080))
            ficha = json.loads(longos[0].with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(ficha["tipo"], "longo")
            self.assertEqual(ficha["pergunta"], "TESTE??")              # reaproveitou o curto (0 IA)
            self.assertAlmostEqual(cortes.duracao_video(longos[0]), 20, delta=1.5)


class Compilacao(unittest.TestCase):
    def test_soma_cortes_ate_o_tamanho_alvo(self):
        import compilacao
        import resultados
        import datetime as dt
        agora = dt.datetime.now().isoformat(timespec="seconds")
        fichas = [(Path(f"c{i}.mp4"), {"titulo": f"t{i}", "duracao": 60, "nota": 10 - i, "criado": agora})
                  for i in range(12)]
        with patch.object(resultados, "fichas", return_value=fichas):
            r = compilacao.escolher(7, 5, alvo_seg=8 * 60)
        self.assertGreaterEqual(len(r), 6)          # 8 min de cortes de ~1 min
        self.assertLessEqual(len(r), 8)
        self.assertEqual(r[0][3]["titulo"], "t0")   # melhor nota primeiro


class PastaVigiada(unittest.TestCase):
    def test_video_novo_vira_tarefa_uma_vez(self):
        import os
        import time as _t
        import monitor
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "live.mp4"
            v.write_bytes(b"x" * 1000)
            velho = _t.time() - 120
            os.utime(v, (velho, velho))
            fila, estado = [], {}
            with patch.object(monitor, "salvar_estado"):
                monitor.verificar_pasta_vigiada({"pasta_vigiada": d}, estado, fila)
                monitor.verificar_pasta_vigiada({"pasta_vigiada": d}, estado, fila)
            self.assertEqual(len(fila), 1)
            self.assertEqual(fila[0]["tipo"], "yt_transcricao")
            self.assertEqual(fila[0]["base"]["fonte"], str(v))


class MelhoriasQualidade(unittest.TestCase):
    def test_1_edicao_unificada_sem_reencode_triplo(self):
        # Silêncios (mantém [0, 4] e [6, 12]) + vício em [1.0, 1.5] virtual + frase cortando 0.5s no início
        manter_sil = [(0.0, 4.0), (6.0, 12.0)]
        apos_vicio = efeitos.aplicar_remocao_em_mantidos(manter_sil, [(1.0, 1.5)])
        self.assertEqual(apos_vicio, [(0.0, 1.0), (1.5, 4.0), (6.0, 12.0)])
        apos_frase = efeitos.aplicar_remocao_em_mantidos(apos_vicio, [(0.0, 0.5)])
        self.assertEqual(apos_frase, [(0.5, 1.0), (1.5, 4.0), (6.0, 12.0)])

    def test_2_audio_estudio_zero_crossing_e_efeitos(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            boom = efeitos.gerar_boom(pasta)
            whoosh = efeitos.gerar_whoosh(pasta, duracao=0.45)
            pop = efeitos.gerar_pop(pasta)
            for arq in (boom, whoosh, pop):
                self.assertTrue(arq.is_file() and arq.stat().st_size > 2000)
            # Testa recorte de WAV com zero-crossing e micro-fade cosseno
            sr = 16000
            t = np.linspace(0, 2.0, sr * 2, endpoint=False, dtype=np.float32)
            seno = 0.5 * np.sin(2 * np.pi * 220 * t)
            wav_in = pasta / "in.wav"
            wav_out = pasta / "out.wav"
            import wave
            with wave.open(str(wav_in), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
                w.writeframes((seno * 32767).astype(np.int16).tobytes())
            efeitos.recortar_wav_mantidos(wav_in, wav_out, [(0.0, 0.7), (1.2, 1.9)])
            lido = cortes.ler_wav(wav_out)
            self.assertAlmostEqual(len(lido) / sr, 1.4, delta=0.05)

    def test_3_camera_smoothstep_e_foco_podcast(self):
        expr = efeitos.expr_crop_x([(0.0, 0.2), (1.5, 0.8)], 1920, 1080)
        # Deve usar curva smoothstep *(3-2*...) e não apenas reta simples
        self.assertIn("*(3-2*", expr)
        foco = efeitos.foco_podcast([(0.0, 4.2, "A"), (4.2, 5.5, "B"), (5.5, 10.0, "B")], minimo_solo=3.5)
        self.assertEqual(foco["foco_top"], [(0.0, 4.2)])
        self.assertEqual(foco["foco_bot"], [(5.5, 10.0)])

    def test_4_legenda_escala_ativa_e_correcao_longo(self):
        import longo
        with tempfile.TemporaryDirectory() as d:
            ass = Path(d) / "leg.ass"
            palavras = [{"t": "gaules", "ini": 0.0, "fim": 0.5}, {"t": "falou", "ini": 0.5, "fim": 1.0}]
            corrigidas = longo.aplicar_correcoes(palavras, {"gaules": "Gaules"})
            self.assertEqual(corrigidas, ["Gaules", "falou"])
            cortes.gerar_ass(palavras, corrigidas, ass, duracao=1.5, legenda=True)
            conteudo = ass.read_text(encoding="utf-8")
            self.assertIn("\\fscx114\\fscy114}GAULES{\\fscx100\\fscy100", conteudo)
            ass_l = Path(d) / "longo.ass"
            longo._ass_longo(palavras, corrigidas, ass_l, duracao=1.5)
            self.assertIn("\\fscx112\\fscy112}Gaules{\\fscx100\\fscy100", ass_l.read_text(encoding="utf-8"))

    def test_5_compilacao_cartao_dinamico_com_som(self):
        import compilacao
        from qualidade import inspecionar
        cortes.checar_ffmpeg()
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            png = compilacao._cartao("TOP 5 DA SEMANA", "01/11 a 02/11", pasta / "intro.png")
            mp4 = compilacao._segmento_cartao(png, compilacao.DURACAO_INTRO, pasta / "00.mp4")
            rel = inspecionar(mp4, compilacao.DURACAO_INTRO, exigir_audio=True, aprofundar=False)
            self.assertTrue(rel["aprovado"], rel)
            self.assertAlmostEqual(rel["duracao"], compilacao.DURACAO_INTRO, delta=0.25)


class Clean(unittest.TestCase):
    def _gerar(self, d, cfg_extra, **k):
        import subprocess
        import conclusao_tarefas
        pasta = Path(d)
        fonte = pasta / "fonte.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25",
                        "-f", "lavfi", "-i", "sine=frequency=440", "-t", "6", "-c:v", "libx264",
                        "-c:a", "aac", str(fonte)], check=True)
        palavras = [dict(t=t, ini=i * .4, fim=i * .4 + .3) for i, t in enumerate(["Isso", "é", "um", "teste."])]
        cfg = dict(cortes.CONFIG_PADRAO, seguir_rosto=False, tirar_silencios=False, tirar_vicios=False,
                   layout="normal", revisor=False, serie=False, checar_inedito=False, efeito_gancho=False,
                   gancho_inicio=False, guardar_projeto_edicao=True, emojis_legenda=False, espanhol=False,
                   **cfg_extra)
        with patch.object(cortes, "carregar_config", return_value=cfg), \
                patch.object(conclusao_tarefas, "BASE", pasta / "jobs"):
            cortes.aplicar_config(cfg)
            return cortes.gerar_corte(fonte, 0, 4, pergunta="ELE FEZ ISSO??", transcricao_teste=palavras,
                                      usar_claude=False, pasta_saida=pasta / "r", **k)

    def test_clean_tela_cheia_sem_faixa_com_texto(self):
        with tempfile.TemporaryDirectory() as d:
            saida = self._gerar(d, {"estilo_corte": "clean", "ab_teste": False})
            self.assertEqual(cortes.info_video(saida), (1080, 1920))
            ficha = json.loads(saida.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(ficha["estilo"], "clean")
            ass = next(Path(d, "r", "_edicao").rglob("receita.json"))
            receita = json.loads(ass.read_text(encoding="utf-8"))
            self.assertIsNone(receita["topo"])
            self.assertIsNone(receita["faixa"])
            self.assertTrue(any("ELE FEZ ISSO" in t[2] for t in receita["textos_extra"]))

    def test_faixa_continua_sendo_o_padrao(self):
        with tempfile.TemporaryDirectory() as d:
            saida = self._gerar(d, {"ab_teste": False})
            ficha = json.loads(saida.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(ficha["estilo"], "faixa")


class LiveMomentoCerto(unittest.TestCase):
    def _fonte(self, d, dur=100):
        import subprocess
        fonte = Path(d) / "live.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15",
                        "-f", "lavfi", "-i", "sine=frequency=300", "-t", str(dur), "-c:v", "libx264",
                        "-preset", "ultrafast", "-c:a", "aac", str(fonte)], check=True)
        return fonte

    def _palavras(self, dur=100):
        ps = []
        t, i = 0.0, 0
        while t < dur - 1:
            fim_frase = i % 10 == 9
            ps.append(dict(t=("Fim." if fim_frase else "palavra"), ini=round(t, 2), fim=round(t + 0.3, 2)))
            t += 0.4 + (0.8 if fim_frase else 0)
            i += 1
        return ps

    def _cfg(self):
        return dict(cortes.CONFIG_PADRAO, seguir_rosto=False, tirar_silencios=False, tirar_vicios=False,
                    layout="normal", revisor=False, serie=False, checar_inedito=False, efeito_gancho=False,
                    gancho_inicio=False, guardar_projeto_edicao=False, emojis_legenda=False, ab_teste=False,
                    espanhol=False, duracao_corte_seg=40)

    def test_ia_escolhe_o_trecho_na_mesma_chamada(self):
        import conclusao_tarefas
        with tempfile.TemporaryDirectory() as d:
            fonte, ps = self._fonte(d), self._palavras()
            pedidos = []

            def ia(prompt, **k):
                pedidos.append(prompt)
                return {"palavras": [p["t"] for p in ps], "pergunta": "E AÍ??", "titulo": "t", "hashtags": [],
                        "destaque": [], "nota": 8, "trecho": [20, 99]}
            cfg = dict(self._cfg(), ia_principal="claude")
            with patch.object(cortes, "carregar_config", return_value=cfg), \
                    patch.object(conclusao_tarefas, "BASE", Path(d) / "jobs"), \
                    patch.object(cortes, "ia_json", side_effect=ia):
                cortes.aplicar_config(cfg)
                saida = cortes.gerar_corte(fonte, 0, 100, transcricao_teste=ps, pasta_saida=Path(d) / "r",
                                           topo="frame", refinar=True, foco=60)
            self.assertEqual(len(pedidos), 1)                       # nenhuma chamada a mais
            self.assertIn('"trecho"', pedidos[0])
            esperado = ps[99]["fim"] - ps[20]["ini"]
            self.assertAlmostEqual(cortes.duracao_video(saida), esperado, delta=1.5)

    def test_sem_ia_corta_pelas_pausas_em_volta_do_lance(self):
        import conclusao_tarefas
        with tempfile.TemporaryDirectory() as d:
            fonte, ps = self._fonte(d), self._palavras()
            cfg = self._cfg()
            with patch.object(cortes, "carregar_config", return_value=cfg), \
                    patch.object(conclusao_tarefas, "BASE", Path(d) / "jobs"):
                cortes.aplicar_config(cfg)
                saida = cortes.gerar_corte(fonte, 0, 100, transcricao_teste=ps, pasta_saida=Path(d) / "r",
                                           usar_claude=False, pergunta="X??", refinar=True, foco=60)
            dur = cortes.duracao_video(saida)
            self.assertTrue(20 <= dur <= 60, dur)
            srt = saida.with_suffix(".srt").read_text(encoding="utf-8")
            primeira = srt.split("\n")[2]
            self.assertFalse(primeira.lower().startswith("fim"))   # não começa com resto de frase

    def test_escolha_local(self):
        ps = self._palavras()
        i0, i1 = efeitos.momento_do_trecho(ps, 60, 40)
        self.assertLess(ps[i0]["ini"], 60)
        self.assertGreater(ps[i1]["fim"], 60)
        self.assertTrue(ps[i1]["t"].endswith(".") or i1 == len(ps) - 1)
