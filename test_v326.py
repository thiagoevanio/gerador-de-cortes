"""3.26: 📥 reels do Instagram (arquivo original, sem marca d'água), juntados pela extensão."""
import http.client
import json
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import instagram
import monitor


def _esperar(tid, limite=10):
    fim = time.time() + limite
    while time.time() < fim:
        t = next(x for x in instagram.resumo(10) if x["id"] == tid)
        if t["estado"] != "baixando":
            return t
        time.sleep(0.05)
    raise AssertionError("não terminou")


class Links(unittest.TestCase):
    def test_usuario(self):
        self.assertEqual(instagram.usuario_valido(" @fulano.de_tal/ "), "fulano.de_tal")
        for ruim in ("", "a b", "x" * 31, "explore", "../etc", "reels"):
            with self.assertRaises(ValueError):
                instagram.usuario_valido(ruim)

    def test_ids_unicos_na_ordem(self):
        ids = instagram.ids_dos_links(["/fulano/reel/AAAAA1/", "https://www.instagram.com/reel/BBBBB2/?x=1",
                                       "/fulano/reel/AAAAA1/", "/p/CCCCC3/", "/fulano/", "lixo"])
        self.assertEqual(ids, ["AAAAA1", "BBBBB2", "CCCCC3"])


class Baixar(unittest.TestCase):
    def setUp(self):
        instagram.TRABALHOS.clear()
        self.dir = tempfile.TemporaryDirectory()
        self.p = patch.object(instagram, "pasta_base", lambda: Path(self.dir.name))
        self.p.start()

    def tearDown(self):
        self.p.stop()
        self.dir.cleanup()

    def _baixar_falso(self, falhar=()):
        def baixar(rid, pasta):
            if rid in falhar:
                raise RuntimeError(falhar[rid])
            (pasta / f"{rid}.mp4").write_bytes(b"0")
            return {"id": rid, "arquivo": f"{rid}.mp4", "legenda": "oi", "data": "20261118"}
        return baixar

    def test_pula_os_ja_baixados_e_salva_indice(self):
        pasta = Path(self.dir.name) / "fulano"
        pasta.mkdir()
        (pasta / "AAAAA1.mp4").write_bytes(b"0")
        t = instagram.iniciar("fulano", ["/fulano/reel/AAAAA1/", "/fulano/reel/BBBBB2/"],
                              baixar=self._baixar_falso(), pausa=None)
        self.assertEqual((t["total"], t["pulados"]), (2, 1))
        fim = _esperar(t["id"])
        self.assertEqual((fim["estado"], fim["feitos"]), ("pronto", 1))
        self.assertIn("BBBBB2", json.loads((pasta / "reels.json").read_text(encoding="utf-8")))

    def test_para_quando_o_instagram_bloqueia(self):
        ids = [f"/fulano/reel/R{i:04d}x/" for i in range(8)]
        falhas = {f"R{i:04d}x": "ERROR: login required" for i in range(1, 8)}
        t = instagram.iniciar("fulano", ids, baixar=self._baixar_falso(falhas), pausa=None)
        fim = _esperar(t["id"])
        self.assertEqual(fim["feitos"], 1)
        self.assertEqual(fim["falhas"], 3)                  # parou na 3ª seguida
        self.assertIn("bloquear", fim["msg"])

    def test_um_reel_ruim_nao_para_os_outros(self):
        t = instagram.iniciar("fulano", ["/fulano/reel/AAAAA1/", "/fulano/reel/BBBBB2/"],
                              baixar=self._baixar_falso({"AAAAA1": "Unsupported"}), pausa=None)
        fim = _esperar(t["id"])
        self.assertEqual((fim["feitos"], fim["falhas"]), (1, 1))

    def test_um_perfil_por_vez_e_parar(self):
        trava = threading.Event()

        def lento(rid, pasta):
            trava.wait(5)
            return {"id": rid}
        t = instagram.iniciar("fulano", ["/fulano/reel/AAAAA1/", "/fulano/reel/BBBBB2/"], baixar=lento, pausa=None)
        with self.assertRaisesRegex(ValueError, "Já tem um perfil"):
            instagram.iniciar("outro", ["/outro/reel/CCCCC3/"], baixar=lento, pausa=None)
        self.assertTrue(instagram.parar(t["id"]))
        trava.set()
        fim = _esperar(t["id"])
        self.assertEqual(fim["msg"], "Parado por você.")

    def test_sem_links(self):
        with self.assertRaises(ValueError):
            instagram.iniciar("fulano", ["/fulano/", "nada"])


class Rota(unittest.TestCase):
    def setUp(self):
        instagram.TRABALHOS.clear()
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
        self.assertEqual(self._pedir("POST", "/instagram", {"usuario": "x"}, token=False)[0], 403)

    def test_inicia_e_status_mostra(self):
        with tempfile.TemporaryDirectory() as d, patch.object(instagram, "pasta_base", lambda: Path(d)), \
                patch.object(instagram, "_rodar", lambda *a: None):
            _, r = self._pedir("POST", "/instagram", {"usuario": "fulano", "links": ["/fulano/reel/AAAAA1/"]})
            self.assertTrue(r["ok"])
            _, s = self._pedir("GET", "/status", token=False)
        self.assertEqual(s["instagram"][0]["usuario"], "fulano")

    def test_usuario_invalido(self):
        _, r = self._pedir("POST", "/instagram", {"usuario": "../x", "links": ["/x/reel/AAAAA1/"]})
        self.assertFalse(r["ok"])


class Extensao(unittest.TestCase):
    def test_script_no_instagram_e_rota_liberada(self):
        m = json.loads(Path("extensao_chrome/manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(any("https://www.instagram.com/*" in c["matches"] and "instagram.js" in c["js"]
                            for c in m["content_scripts"]))
        self.assertIn('"instagram"', Path("extensao_chrome/background.js").read_text(encoding="utf-8"))
        self.assertIn("_instagram_reels", Path("interface.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
