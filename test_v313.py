"""3.13: atualizador seguro com git, aviso de música de fundo, capa escolhível, revisão rápida na
galeria (PC e celular) e a divisão do cortes.py (ia_cortes.py e render.py)."""
import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import acabamento
import atualizar
import audio_musica
import celular
import conclusao_tarefas
import cortes

TAXA = 16000


def _git(pasta, *args):
    subprocess.run(["git", *args], cwd=pasta, check=True, capture_output=True)


def _video(destino, segundos=12, audio="sine=frequency=440:sample_rate=48000"):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25",
                    "-f", "lavfi", "-i", audio, "-t", str(segundos), "-c:v", "libx264", "-c:a", "aac",
                    str(destino)], check=True, capture_output=True)
    return destino


def _frases(dur):
    """Tempos de 'palavras' em frases de 5, com pausa de 0,9s entre as frases."""
    ps, t = [], 0.0
    while t < dur - 1:
        for _ in range(5):
            ps.append({"t": "palavra", "ini": round(t, 2), "fim": round(t + 0.3, 2), "confianca": 0.9})
            t += 0.38
        t += 0.9
    return ps


class Atualizador(unittest.TestCase):
    def test_git_pull_e_nao_sobrescreve_mudanca_local(self):
        with tempfile.TemporaryDirectory() as d:
            origem, local = Path(d) / "origem", Path(d) / "local"
            origem.mkdir()
            _git(origem, "init", "-b", "main", "-q")
            for pasta in (origem,):
                _git(pasta, "config", "user.email", "teste@exemplo.com")
                _git(pasta, "config", "user.name", "Teste")
            (origem / "VERSAO.txt").write_text("1.0\n", encoding="utf-8")
            (origem / "requirements.txt").write_text("numpy\n", encoding="utf-8")
            _git(origem, "add", "-A")
            _git(origem, "commit", "-q", "-m", "v1.0")
            subprocess.run(["git", "clone", "-q", str(origem), str(local)], check=True, capture_output=True)
            (origem / "VERSAO.txt").write_text("1.1\n", encoding="utf-8")
            _git(origem, "commit", "-q", "-am", "v1.1")
            msgs = []
            with patch.object(atualizar, "PASTA", local):
                self.assertTrue(atualizar.em_git())
                self.assertEqual(atualizar.mudancas_locais(), [])
                tem, nova, url, notas = atualizar.verificar("")      # repositório privado: compara pelo git
                self.assertEqual((tem, nova, url), (True, "1.1", None))
                self.assertIn("v1.1", notas)
                atualizar.aplicar(None, "1.1", log=msgs.append)
                self.assertFalse(atualizar.verificar("")[0])         # já está em dia
                self.assertEqual((local / "VERSAO.txt").read_text(encoding="utf-8").strip(), "1.1")
                (local / "VERSAO.txt").write_text("minha mudança\n", encoding="utf-8")   # não salva no git
                (origem / "VERSAO.txt").write_text("1.2\n", encoding="utf-8")
                _git(origem, "commit", "-q", "-am", "v1.2")
                with self.assertRaises(RuntimeError) as erro:
                    atualizar.aplicar(None, "1.2", log=msgs.append)
                self.assertIn("VERSAO.txt", str(erro.exception))
            self.assertEqual((local / "VERSAO.txt").read_text(encoding="utf-8"), "minha mudança\n")

    def test_sem_git_usa_o_zip(self):
        with tempfile.TemporaryDirectory() as d, patch.object(atualizar, "PASTA", Path(d)):
            self.assertFalse(atualizar.em_git())


class DetectorDeMusica(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(1)
        self.ps = _frases(30)
        n = 30 * TAXA
        self.t = np.arange(n) / TAXA
        fala = np.zeros(n, dtype=np.float32)
        for p in self.ps:                      # "fala": harmônicos com o tom variando (entonação)
            a, b = int(p["ini"] * TAXA), int(p["fim"] * TAXA)
            tt = np.arange(b - a) / TAXA
            fase = 2 * np.pi * np.cumsum(150 * (1 + 0.15 * np.sin(2 * np.pi * 3 * tt))) / TAXA
            fala[a:b] = 0.25 * sum(np.sin(k * fase) / k for k in range(1, 8)) * (0.5 + 0.5 * np.sin(2 * np.pi * 4 * tt))
        self.fala = fala
        self.musica = (0.05 * sum(np.sin(2 * np.pi * f * self.t) for f in (220, 277.2, 329.6, 440))).astype(np.float32)

    def test_so_fala_ruido_e_musica(self):
        self.assertFalse(audio_musica.avaliar(self.fala, self.ps)["provavel"])
        ruido = 0.03 * self.rng.standard_normal(len(self.t)).astype(np.float32)
        self.assertFalse(audio_musica.avaliar(self.fala + ruido, self.ps)["provavel"])
        com = audio_musica.avaliar(self.fala + self.musica, self.ps)
        self.assertTrue(com["provavel"])
        self.assertEqual(com["confianca"], "alta")
        self.assertTrue(com["trechos"])
        self.assertTrue(audio_musica.avaliar(self.fala + 0.25 * self.musica, self.ps)["provavel"])

    def test_sem_audio_nao_quebra(self):
        self.assertFalse(audio_musica.avaliar(np.zeros(100, dtype=np.float32), [])["provavel"])
        self.assertIsNone(audio_musica.detectar(Path("nao_existe.mp4"), []))


class AvisoNoCorte(unittest.TestCase):
    """FFmpeg real, sem IA: a ficha do corte guarda o resultado do detector."""

    def _corte(self, audio):
        palavras = _frases(11)
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            fonte = _video(pasta / "fonte.mp4", 12, audio)
            cfg = dict(cortes.CONFIG_PADRAO, seguir_rosto=False, tirar_silencios=False, tirar_vicios=False,
                       layout="normal", revisor=False, serie=False, checar_inedito=False, ia_principal="nenhuma",
                       efeito_gancho=False, gancho_inicio=False, guardar_projeto_edicao=False, musica_fundo=False,
                       estilo_corte="clean", capa=False, final_corte="nada", aparar_ia=False, limpar_abertura=False)
            with patch.object(cortes, "carregar_config", return_value=cfg), \
                    patch.object(conclusao_tarefas, "BASE", pasta / "jobs"):
                final = cortes.gerar_corte(fonte, 0, 11.5, pergunta="TESTE DA MÚSICA??", transcricao_teste=palavras,
                                           usar_claude=False, pasta_saida=pasta / "render")
            return json.loads(final.with_suffix(".json").read_text(encoding="utf-8"))

    def test_trilha_continua_vira_aviso_e_ruido_nao(self):
        cortes.checar_ffmpeg()
        com = self._corte("sine=frequency=440:sample_rate=48000")
        self.assertTrue(com["musica_de_fundo"]["provavel"])
        sem = self._corte("anoisesrc=color=pink:amplitude=0.05:sample_rate=48000")
        self.assertFalse(sem["musica_de_fundo"]["provavel"])


class Capa(unittest.TestCase):
    def test_tempos_longe_do_fim_e_separados(self):
        tempos = acabamento.tempos_capa(40)
        self.assertEqual(len(tempos), 3)
        self.assertTrue(all(t <= 40 - 3.4 - 0.8 for t in tempos))
        self.assertTrue(all(abs(a - b) >= 1.5 for a in tempos for b in tempos if a != b))
        self.assertTrue(1 <= len(acabamento.tempos_capa(6)) <= 3)

    def test_opcoes_geradas(self):
        cortes.checar_ffmpeg()
        with tempfile.TemporaryDirectory() as d:
            v = _video(Path(d) / "v.mp4", 20)
            opcoes = acabamento.opcoes_capa(v, Path(d) / "capas", 20, pergunta="TESTE??", fonte=cortes.fonte,
                                            clean=True)
            self.assertEqual(len(opcoes), 3)
            self.assertTrue(all(Path(a).is_file() for _, a in opcoes))


class Galeria(unittest.TestCase):
    def _ficha(self):
        return {"titulo": "GTA 6: teste", "pergunta": "TESTE??", "nota": 6, "status": "novo",
                "resumo": "O youtuber explica a física dos carros.", "motivo_nota": "Bom, mas depende de contexto.",
                "musica_de_fundo": {"provavel": True, "confianca": "alta"}, "estilo": "clean"}

    def test_textos_de_revisao(self):
        import interface
        avisos = interface.App._avisos_revisao(self._ficha())
        self.assertTrue(any("música de fundo" in a for a in avisos))
        self.assertIn("física dos carros", interface.App._texto_revisao(self._ficha()))
        self.assertEqual(interface.App._avisos_revisao({}), [])
        self.assertTrue(interface.App._avisos_revisao({"ia": {"falhou": True}}))

    def test_cartao_e_escolha_de_capa_na_interface(self):
        import interface
        import postagem
        cortes.checar_ffmpeg()
        with tempfile.TemporaryDirectory() as d:
            v = _video(Path(d) / "corte.mp4", 20)
            postagem.salvar_ficha(v, self._ficha())
            app = interface.App()
            app.withdraw()
            try:
                with patch.object(app, "_carregar_galeria"):
                    app._desenhar_galeria([(v, postagem.ler_ficha(v))])
                    textos = []

                    def juntar(w):
                        for filho in w.winfo_children():
                            if isinstance(filho, interface.tk.Label):
                                textos.append(str(filho.cget("text")))
                            juntar(filho)
                    juntar(app.gal_interno)
                    self.assertTrue(any("música de fundo" in t for t in textos))
                    self.assertTrue(any("física dos carros" in t for t in textos))
                    app._escolher_capa(v, postagem.ler_ficha(v))
                    janela = None
                    fim = time.time() + 60
                    while time.time() < fim and janela is None:
                        app.update()
                        janela = next((w for w in app.winfo_children()
                                       if isinstance(w, interface.tk.Toplevel) and w.title() == "Escolha a capa"), None)
                        time.sleep(0.05)
                    self.assertIsNotNone(janela, "a janela de capas não abriu")
                    botoes = []

                    def achar(w):
                        for filho in w.winfo_children():
                            if isinstance(filho, interface.tk.Button):
                                botoes.append(filho)
                            achar(filho)
                    achar(janela)
                    self.assertGreaterEqual(len(botoes), 3)
                    botoes[1].invoke()
                    app.update()
                self.assertTrue(v.with_suffix(".capa.jpg").is_file())
                self.assertEqual(postagem.ler_ficha(v)["capa"], "corte.capa.jpg")
            finally:
                app.destroy()

    def test_celular_mostra_aviso_e_resumo(self):
        import postagem
        cortes.checar_ffmpeg()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            v = _video(base / "corte.mp4", 4)
            postagem.salvar_ficha(v, self._ficha())
            with patch.object(celular, "BASE", base):
                item = celular.listar()[0]
            self.assertTrue(item["musica"])
            self.assertIn("física", item["resumo"])
            self.assertIn("música de fundo?", celular.CORPO_APP)


class Divisao(unittest.TestCase):
    def test_modulos_novos_e_nomes_de_sempre(self):
        import ia_cortes
        import render
        for nome in ("ia_json", "pensar_com_ia", "pensar_lote", "claude_json", "IAS", "_validar_dados"):
            self.assertIs(getattr(cortes, nome), getattr(ia_cortes, nome))
        for nome in ("renderizar", "tem_audio", "info_video"):
            self.assertIs(getattr(cortes, nome), getattr(render, nome))
        self.assertLess(len(Path(cortes.__file__).read_text(encoding="utf-8").splitlines()), 2200)

    def test_troca_no_cortes_vale_dentro_do_modulo_novo(self):
        chamadas = []
        with patch.object(cortes, "ia_json", side_effect=lambda p, **k: chamadas.append(k) or {"pergunta": "X??"}), \
                patch.object(cortes, "IA_PRINCIPAL", "claude"), patch.object(cortes, "_guia_estilo", return_value=[]), \
                tempfile.TemporaryDirectory() as d:
            cortes.pensar_com_ia([{"t": "oi", "ini": 0, "fim": 0.3}], {"titulo": "t", "canal": "c"}, Path(d))
        self.assertEqual(len(chamadas), 1)


if __name__ == "__main__":
    unittest.main()
