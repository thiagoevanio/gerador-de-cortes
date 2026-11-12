"""3.14: Whisper sem consultar a internet a cada corte, escolha do modelo da IA local, formatos de faixa
(Balão e Neon + amostras), Tendências só nos canais digitados e a janelinha da live do robô."""
import http.client
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import contas
import cortes
import faixas
import tendencias


class WhisperLocal(unittest.TestCase):
    def setUp(self):
        self.cache = dict(cortes._modelo_cache)
        cortes._modelo_cache.clear()

    def tearDown(self):
        cortes._modelo_cache.clear()
        cortes._modelo_cache.update(self.cache)

    def test_ja_baixado_abre_sem_internet(self):
        chamadas = []

        def falso(nome, **kw):
            chamadas.append(kw.get("local_files_only", False))
            return object()
        with patch("faster_whisper.WhisperModel", falso), patch.object(cortes, "log") as log:
            cortes.carregar_whisper("small")
            cortes.carregar_whisper("small")          # 2º corte: nem carrega de novo
        self.assertEqual(chamadas, [True])
        self.assertIn("já estava no PC", log.call_args_list[0].args[0])

    def test_baixa_so_quando_falta(self):
        chamadas = []

        def falso(nome, **kw):
            chamadas.append(kw.get("local_files_only", False))
            if kw.get("local_files_only"):
                raise RuntimeError("não está no cache")
            return object()
        with patch("faster_whisper.WhisperModel", falso), patch.object(cortes, "log") as log:
            cortes.carregar_whisper("base")
        self.assertEqual(chamadas, [True, False])
        self.assertIn("só desta vez", log.call_args_list[0].args[0])


class ModeloLocal(unittest.TestCase):
    def test_lista_do_leve_ao_forte(self):
        tamanhos = [m["gb"] for m in contas.MODELOS_LOCAIS]
        self.assertEqual(tamanhos, sorted(tamanhos))
        self.assertLess(tamanhos[0], 4)
        self.assertGreaterEqual(tamanhos[-1], 8)

    def test_recomendado_pela_memoria(self):
        self.assertEqual(contas.modelo_recomendado(4), "qwen2.5:3b")
        self.assertEqual(contas.modelo_recomendado(8), "qwen2.5:3b")
        self.assertEqual(contas.modelo_recomendado(16), "gemma3:12b")
        self.assertEqual(contas.modelo_recomendado(64), "qwen2.5:14b")
        self.assertEqual(contas.modelo_recomendado(0), "qwen2.5:3b")      # não deu pra medir

    def test_nao_baixa_de_novo(self):
        log = []
        with patch.object(contas, "achar_ollama", return_value="ollama.exe"), \
             patch.object(contas, "_ligar_ollama", return_value=True), \
             patch.object(contas, "modelos_baixados", return_value=["qwen2.5:7b"]), \
             patch.object(cortes, "MODELO_LOCAL", "qwen2.5:7b"), \
             patch.object(contas, "rodar_mostrando") as rodar:
            self.assertTrue(contas.instalar_local(log.append))
        rodar.assert_not_called()
        self.assertIn("já está no PC", log[-1])

    def test_baixa_o_escolhido(self):
        log = []
        with patch.object(contas, "achar_ollama", return_value="ollama.exe"), \
             patch.object(contas, "_ligar_ollama", return_value=True), \
             patch.object(contas, "modelos_baixados", return_value=[]), \
             patch.object(cortes, "MODELO_LOCAL", "gemma3:12b"), \
             patch.object(contas, "rodar_mostrando", return_value=0) as rodar:
            self.assertTrue(contas.instalar_local(log.append))
        self.assertEqual(rodar.call_args.args[0], ["ollama.exe", "pull", "gemma3:12b"])
        self.assertIn("8,1 GB", " ".join(log))


class Faixas(unittest.TestCase):
    def test_formatos_novos(self):
        self.assertIn("Balão", faixas.FORMATOS_FAIXA)
        self.assertIn("Neon", faixas.FORMATOS_FAIXA)
        for formato in ("Balão", "Neon"):
            img = getattr(faixas, faixas.FORMATOS_FAIXA[formato])("ELE FALOU ISSO AO VIVO?", ["VIVO?"], "canal")
            self.assertEqual(img.mode, "RGBA")
            self.assertGreater(img.getbbox()[3] - img.getbbox()[1], 150)          # desenhou algo

    def test_topo_com_balao(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            foto = Path(d) / "f.jpg"
            Image.new("RGB", (1280, 720), (90, 120, 160)).save(foto)
            with patch.object(cortes, "FAIXA_FORMATO", "Balão"):
                topo, faixa, y = faixas.montar_topo(foto, "QUE ISSO?", ["ISSO?"], "canal", Path(d))
            self.assertTrue(Path(faixa).exists())
            self.assertGreater(y, 0)

    def test_amostras_de_todos_os_formatos(self):
        import interface
        with tempfile.TemporaryDirectory() as d:
            amostras = interface.App.amostras_faixa(d)
            self.assertEqual(set(amostras), set(faixas.FORMATOS_FAIXA) | {"Reta"})
            self.assertTrue(all(Path(a).exists() for a in amostras.values()))


class TendenciasCanal(unittest.TestCase):
    def _ydl(self, url, flat=True, n=15):
        self.urls.append(url)
        if "/videos" in url:
            return {"channel_id": "UC" + "a" * 22, "channel": "Canal Certo",
                    "entries": [{"id": "abcdefghijk", "title": "vídeo do canal", "duration": 900}]}
        return {"channel_id": "UC" + "a" * 22, "duration": 900, "timestamp": __import__("time").time() - 3600,
                "view_count": 1000, "language": "pt"}

    def setUp(self):
        self.urls = []

    def test_nome_simples_vira_arroba(self):
        with patch.object(tendencias, "_ydl", self._ydl):
            v = tendencias.buscar_canal("canalcerto")
        self.assertTrue(self.urls[0].startswith("https://www.youtube.com/@canalcerto"))
        self.assertEqual(v[0]["origem_id"], "UC" + "a" * 22)

    def test_link_com_caminho(self):
        with patch.object(tendencias, "_ydl", self._ydl):
            tendencias.buscar_canal("youtube.com/@canalcerto/featured")
        self.assertEqual(self.urls[0], "https://www.youtube.com/@canalcerto/videos")

    def test_modo_canal_sem_assuntos_do_brasil(self):
        with patch.object(tendencias, "_ydl", self._ydl), \
             patch.object(tendencias, "buscar_assuntos") as assuntos, \
             patch.object(tendencias, "buscar_youtube") as busca_solta, \
             patch.object(tendencias, "_salvar"), patch.object(tendencias, "_ja_cortados", return_value=set()):
            r = tendencias.radar(["@canalcerto"], "semana", modo="canal", log=lambda t: None)
        assuntos.assert_not_called()
        busca_solta.assert_not_called()
        self.assertEqual([v["canal"] for v in r], ["Canal Certo"])

    def test_canal_que_falha_nao_derruba_os_outros(self):
        def ydl(url, flat=True, n=15):
            if "@sumiu" in url:
                raise RuntimeError("canal não existe")
            return self._ydl(url, flat, n)
        with patch.object(tendencias, "_ydl", ydl), patch.object(tendencias, "buscar_youtube", return_value=[]), \
             patch.object(tendencias, "_salvar"), patch.object(tendencias, "_ja_cortados", return_value=set()):
            r = tendencias.radar(["@sumiu", "@canalcerto"], "semana", modo="canal", log=lambda t: None)
            self.assertEqual(len(r), 1)
            with self.assertRaises(ValueError):
                tendencias.radar(["@sumiu"], "semana", modo="canal", log=lambda t: None)

    def test_interface_reconhece_canal(self):
        import interface
        self.assertTrue(interface.App.parece_canal(["@gaules", "https://www.youtube.com/@flow"]))
        self.assertFalse(interface.App.parece_canal(["futebol", "@gaules"]))
        self.assertFalse(interface.App.parece_canal([]))


class JanelinhaDaLive(unittest.TestCase):
    def test_pagina_mini(self):
        import monitor
        srv = ThreadingHTTPServer(("127.0.0.1", 0), monitor.Painel)
        porta = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with patch.object(monitor, "PORTA", porta):
                c = http.client.HTTPConnection("127.0.0.1", porta, timeout=10)
                c.request("GET", "/mini", headers={"Host": f"localhost:{porta}"})
                r = c.getresponse()
                html = r.read().decode("utf-8")
            self.assertEqual(r.status, 200)
            self.assertIn("player.twitch.tv", html)
            self.assertIn("player.kick.com", html)
            self.assertIn("youtube.com/embed", html)
            self.assertNotIn("__TOKEN_SESSAO__", html)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_estado_tem_video_do_youtube(self):
        import monitor

        class Termo:
            sensibilidade, eventos = "media", []

            def calor_pct(self):
                return 40

        class G:
            canal, plataforma, desde, cortes_feitos, pela_extensao = "flow", "youtube", 0, [], False
            meta, url, termometro = {"title": "ao vivo", "id": "abcdefghijk"}, "https://youtube.com/@flow/live", Termo()
        monitor.atualizar_estado({"ytlive:flow": G()}, [], {})
        live = monitor.ESTADO_PAINEL["lives"]["ytlive:flow"]
        self.assertEqual(live["video_id"], "abcdefghijk")
        self.assertEqual(live["url"], "https://youtube.com/@flow/live")

    def test_navegador_para_janela(self):
        import interface
        with patch("os.path.exists", side_effect=lambda p: p.endswith("msedge.exe")), \
             patch("shutil.which", return_value=None):
            self.assertTrue(interface.App.navegador_app().endswith("msedge.exe"))


if __name__ == "__main__":
    unittest.main()
