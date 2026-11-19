"""3.25: 🤖 IA corta os melhores momentos sozinha (extensão, vídeos do YouTube)."""
import http.client
import json
import queue
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import ia_youtube
import monitor

URL = "https://www.youtube.com/watch?v=wJ0_i2nFxUQ"


def _esperar(tid, limite=10):
    fim = time.time() + limite
    while time.time() < fim:
        t = next(x for x in ia_youtube.resumo(10) if x["id"] == tid)
        if t["estado"] != "trabalhando":
            return t
        time.sleep(0.05)
    raise AssertionError("o trabalho não terminou")


class Validar(unittest.TestCase):
    def test_so_link_do_youtube(self):
        for ruim in ("https://evil.com/watch?v=abc123", "javascript:alert(1)", "", None):
            with self.assertRaises(ValueError):
                ia_youtube.validar({"url": ruim})

    def test_limita_o_que_vem_da_pagina(self):
        p = ia_youtube.validar({"url": URL, "n": 99, "dur": 5000, "titulo": "x" * 999,
                                "comentarios": [{"t": "245", "n": 3, "textos": ["a" * 999] * 9}, {"t": "nan"}] * 30,
                                "picos": [{"t": 100}, "200", -5, "x"]})
        self.assertEqual((p["n"], p["dur"]), (5, 120))
        self.assertEqual(len(p["titulo"]), 150)
        self.assertLessEqual(len(p["comentarios"]), 20)
        self.assertEqual(len(p["comentarios"][0]["textos"]), 3)
        self.assertEqual(len(p["comentarios"][0]["textos"][0]), 200)
        self.assertEqual(p["picos"], [100.0, 200.0])


class Trabalho(unittest.TestCase):
    def setUp(self):
        ia_youtube.TRABALHOS.clear()

    def test_acha_e_manda_pra_fila_com_as_dicas(self):
        recebido, fila = {}, []

        def achar(url, n, dur, log=print, contexto_titulo="", dicas=None, usar_ia=False):
            recebido.update(url=url, n=n, dur=dur, dicas=dicas, usar_ia=usar_ia)
            log("transcrevendo candidato 1/8")
            return [{"inicio": 2010.0, "fim": 2075.3, "motivo": "a casa já tinha sido vendida", "nota_ia": 7},
                    {"inicio": 10, "fim": 12, "motivo": "curto demais"}], {}
        t = ia_youtube.iniciar({"url": URL, "n": 2, "dur": 60, "comentarios": [{"t": 2025, "n": 4, "textos": ["33:45 kkk"]}]},
                               lambda itens: (fila.extend(itens), {"ok": True})[1], achar=achar)
        fim = _esperar(t["id"])
        self.assertEqual(fim["estado"], "pronto")
        self.assertTrue(recebido["usar_ia"])                       # a IA sempre confere
        self.assertEqual(recebido["dicas"]["comentarios"][0]["t"], 2025)
        self.assertEqual(len(fila), 1)                              # o de 2 s não vai
        self.assertEqual(fila[0]["url"], URL)
        self.assertEqual(fim["momentos"][0]["nota"], 7)

    def test_um_por_vez(self):
        trava = threading.Event()

        def achar(*a, **k):
            trava.wait(5)
            return [], {}
        t = ia_youtube.iniciar({"url": URL}, lambda i: {"ok": True}, achar=achar)
        with self.assertRaisesRegex(ValueError, "já está trabalhando"):
            ia_youtube.iniciar({"url": URL}, lambda i: {"ok": True}, achar=achar)
        trava.set()
        self.assertEqual(_esperar(t["id"])["estado"], "sem_momentos")

    def test_erro_vira_mensagem(self):
        def achar(*a, **k):
            raise RuntimeError("Private video")
        t = ia_youtube.iniciar({"url": URL}, lambda i: {"ok": True}, achar=achar)
        fim = _esperar(t["id"])
        self.assertEqual(fim["estado"], "erro")
        self.assertIn("Private video", fim["msg"])


class Monitor(unittest.TestCase):
    def setUp(self):
        ia_youtube.TRABALHOS.clear()
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), monitor.Painel)
        self.porta = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.p = patch.object(monitor, "PORTA", self.porta)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        self.srv.shutdown()
        self.srv.server_close()

    def _pedir(self, metodo, rota, corpo=None, token=True):
        c = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=20)
        h = {"Host": f"localhost:{self.porta}", "Content-Type": "application/json"}
        if token:
            h["X-Cortes-Token"] = monitor.TOKEN_SESSAO
        c.request(metodo, rota, body=json.dumps(corpo) if corpo is not None else None, headers=h)
        r = c.getresponse()
        return r.status, json.loads(r.read().decode("utf-8"))

    def test_precisa_da_sessao(self):
        status, _ = self._pedir("POST", "/ia_momentos", {"url": URL}, token=False)
        self.assertEqual(status, 403)

    def test_rota_inicia_e_status_mostra(self):
        with patch.object(ia_youtube, "_rodar", lambda *a: None):
            status, r = self._pedir("POST", "/ia_momentos", {"url": URL, "n": 2})
        self.assertEqual(status, 200)
        self.assertTrue(r["ok"])
        _, s = self._pedir("GET", "/status", token=False)
        self.assertEqual(s["ia_momentos"][0]["id"], r["trabalho"]["id"])

    def test_link_invalido_avisa(self):
        _, r = self._pedir("POST", "/ia_momentos", {"url": "https://exemplo.com"})
        self.assertFalse(r["ok"])

    def test_lote_entra_na_fila(self):
        fila = []
        cmd = {"acao": "ia_lote", "resposta": queue.Queue(),
               "itens": [{"url": URL, "inicio": 2010, "fim": 2075, "motivo": "a casa vendida"}]}
        monitor.COMANDOS.put(cmd)
        monitor.tratar_comandos({}, {}, [], fila=fila)
        self.assertTrue(cmd["resposta"].get_nowait()["ok"])
        self.assertEqual(fila[0]["fonte"], URL)
        self.assertIn("a casa vendida", fila[0]["contexto"])


class Momentos(unittest.TestCase):
    def test_comentarios_viram_candidatos_e_ia_sempre_confere(self):
        import momentos
        codigo = Path(momentos.__file__).read_text(encoding="utf-8")
        self.assertIn("not usar_ia", codigo)
        self.assertIn('dicas.get("comentarios")', codigo)


class Extensao(unittest.TestCase):
    def test_botao_e_rota_liberada(self):
        yt = Path("extensao_chrome/youtube.js").read_text(encoding="utf-8")
        self.assertIn('UI.api("ia_momentos"', yt)
        self.assertIn("ACHAR E CORTAR SOZINHA", yt)
        self.assertIn('"ia_momentos"', Path("extensao_chrome/background.js").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
