"""Aba 📝 Legendar: escolhe um vídeo já editado no PC e só coloca a legenda (nada de cortar ou mudar
o formato). Passo a passo: escolher → (prévia com o estilo) → transcrever → revisar o texto →
queimar a legenda. O motor fica em legendar.py."""
from __future__ import annotations

import sys
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import legendar

FUNDO, CARTAO, CAMPO = "#16161A", "#222228", "#2E2E36"
TEXTO, CINZA, VERMELHO, VERDE = "#F2F2F2", "#9A9AA5", "#D90F0F", "#4ADE80"


class AbaLegendar:
    def __init__(self, app, aba):
        import templates_edicao as te
        self.app, self.aba = app, aba
        self.video = None
        self.palavras = None          # transcrição (com IA) pronta pra revisar
        self.ocupado = False
        self.t_previa = None          # segundo do quadro da prévia
        self._job = None
        self._img = None
        self.saida = None
        padrao = legendar.opcoes_padrao()

        esq = app._cartao(aba, side="left", fill="both", expand=True, padx=(0, 8), pady=8)
        dir_ = tk.Frame(aba, bg=FUNDO, width=360)
        dir_.pack(side="left", fill="both", pady=8)
        dir_.pack_propagate(False)

        # ---- 1. vídeo
        app._rotulo(esq, "1. Vídeo já editado", "Vertical, horizontal ou quadrado — o formato não muda.", top=2)
        lv = tk.Frame(esq, bg=CARTAO)
        lv.pack(fill="x", pady=(4, 0))
        app._botao(lv, "📂 Escolher vídeo", self.escolher).pack(side="left")
        self.lbl_video = tk.Label(lv, text="nenhum vídeo escolhido", bg=CARTAO, fg=CINZA, anchor="w",
                                  font=("Segoe UI", 9))
        self.lbl_video.pack(side="left", fill="x", expand=True, padx=(10, 0))

        # ---- 2. estilo
        app._rotulo(esq, "2. Estilo da legenda", "Os mesmos templates dos cortes. A prévia ao lado mostra no seu vídeo.")
        le = tk.Frame(esq, bg=CARTAO)
        le.pack(fill="x", pady=(4, 0))
        tk.Label(le, text="Template:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10)).pack(side="left")
        nomes = [n for n in te.TEMPLATES]
        self.v_tpl = tk.StringVar(value=padrao["template"] if padrao["template"] in nomes else te.PADRAO)
        cb = ttk.Combobox(le, textvariable=self.v_tpl, values=nomes, state="readonly", width=18)
        cb.pack(side="left", padx=(6, 10))
        cb.bind("<<ComboboxSelected>>", lambda e: self.mudou())
        self.lbl_desc = tk.Label(le, text="", bg=CARTAO, fg=CINZA, font=("Segoe UI", 8), anchor="w")
        self.lbl_desc.pack(side="left", fill="x", expand=True)

        grade = tk.Frame(esq, bg=CARTAO)
        grade.pack(fill="x", pady=(6, 0))
        self.v_margem = self._escala(grade, 0, "Posição (↑)", 10, 1500, padrao["margem"], passo=10)
        self.v_tam = self._escala(grade, 1, "Tamanho", 40, 140, padrao["tamanho"], passo=2)
        self.v_pal = self._escala(grade, 2, "Palavras por vez", 1, 6, padrao["palavras"])

        lc = tk.Frame(esq, bg=CARTAO)
        lc.pack(fill="x", pady=(6, 0))
        self.v_corrigir = tk.BooleanVar(value=True)
        self.v_enfase = tk.BooleanVar(value=True)
        self.v_muletas = tk.BooleanVar(value=True)
        self.v_marca = tk.BooleanVar(value=False)
        self.v_revisar = tk.BooleanVar(value=True)
        for i, (txt, var) in enumerate([("Corrigir nomes com IA", self.v_corrigir),
                                        ("Palavras-chave coloridas (IA)", self.v_enfase),
                                        ("Tirar \"hum/éé\" da legenda", self.v_muletas),
                                        ("Meu @ no vídeo", self.v_marca),
                                        ("Revisar o texto antes de queimar", self.v_revisar)]):
            ttk.Checkbutton(lc, text=txt, variable=var, command=self.mudou).grid(
                row=i // 3, column=i % 3, sticky="w", padx=(0, 12), pady=1)

        # ---- 3. ação
        la = tk.Frame(esq, bg=CARTAO)
        la.pack(fill="x", pady=(10, 0))
        self.b_acao = app._botao(la, "📝 LEGENDAR", self.acao, cor=VERMELHO, cor_txt="white", grande=True)
        self.b_acao.pack(side="left", fill="x", expand=True)
        self.b_cancelar = app._botao(la, "Descartar texto", self.descartar)
        self.b_abrir = app._botao(la, "▶ Abrir vídeo", lambda: self.saida and app._abrir(self.saida))
        self.b_pasta = app._botao(la, "📁 Pasta", lambda: self.saida and app._abrir(Path(self.saida).parent))
        self.barra = ttk.Progressbar(esq, mode="indeterminate", style="Horizontal.TProgressbar")
        self.lugar_barra = tk.Frame(esq, bg=CARTAO, height=12)       # a barra só aparece trabalhando
        self.lugar_barra.pack(fill="x", pady=(6, 0))

        # ---- revisão do texto
        self.lbl_rev = tk.Label(esq, text="", bg=CARTAO, fg=CINZA, font=("Segoe UI", 8), anchor="w", justify="left")
        self.lbl_rev.pack(fill="x", pady=(6, 0))
        self.texto = tk.Text(esq, bg=CAMPO, fg=TEXTO, insertbackground=TEXTO, relief="flat", wrap="word",
                             font=("Segoe UI", 10), undo=True, height=8, padx=8, pady=6)
        self.texto.pack(fill="both", expand=True, pady=(2, 0))
        self.texto.tag_configure("tempo", foreground=CINZA)
        self.texto.insert("1.0", "Escolha um vídeo e clique em LEGENDAR.\n\nCom \"Revisar o texto antes de "
                                 "queimar\" ligado, a transcrição aparece aqui — uma frase por linha — pra você "
                                 "corrigir o que quiser antes de a legenda entrar no vídeo.")
        self.texto.configure(state="disabled")

        # ---- direita: prévia + log
        topo_p = tk.Frame(dir_, bg=FUNDO)
        topo_p.pack(fill="x")
        tk.Label(topo_p, text="Prévia no seu vídeo", bg=FUNDO, fg=CINZA, font=("Segoe UI", 9, "bold")).pack(side="left")
        app._botao(topo_p, "↻ outro quadro", self.outro_quadro).pack(side="right")
        self.lbl_previa = tk.Label(dir_, bg="#0E0E11", text="(escolha um vídeo)", fg=CINZA, height=14)
        self.lbl_previa.pack(fill="x", pady=(4, 6))
        self.log = app._caixa_log(dir_, altura=8)
        self.log.pack(fill="both", expand=True)
        self.mudou(previa=False)

    # ------------------------------------------------------------ peças da tela
    def _escala(self, grade, col, txt, a, b, valor, passo=0):
        f = tk.Frame(grade, bg=CARTAO)
        f.grid(row=0, column=col, sticky="ew", padx=(0, 8))
        grade.grid_columnconfigure(col, weight=1)
        topo = tk.Frame(f, bg=CARTAO)
        topo.pack(fill="x")
        tk.Label(topo, text=txt, bg=CARTAO, fg=TEXTO, font=("Segoe UI", 9, "bold"), anchor="w").pack(
            side="left", fill="x", expand=True)
        var = tk.IntVar(value=max(a, min(b, int(valor))))
        if passo:
            for sinal, simbolo in ((-1, "▼"), (1, "▲")):
                tk.Button(topo, text=simbolo, bg=CAMPO, fg=TEXTO, relief="flat", bd=0, padx=6,
                          font=("Segoe UI", 8), cursor="hand2", activebackground=VERMELHO,
                          command=lambda s=sinal: (var.set(max(a, min(b, var.get() + s * passo))), self.mudou())
                          ).pack(side="left", padx=(2, 0))
        tk.Scale(f, from_=a, to=b, orient="horizontal", variable=var, bg=CARTAO, fg=TEXTO, troughcolor=CAMPO,
                 highlightthickness=0, activebackground=VERMELHO, sliderrelief="flat", font=("Segoe UI", 8),
                 command=lambda _v: self.mudou()).pack(fill="x")
        return var

    def opcoes(self):
        return {"template": self.v_tpl.get(), "margem": int(self.v_margem.get()), "tamanho": int(self.v_tam.get()),
                "palavras": int(self.v_pal.get()), "marca": bool(self.v_marca.get()),
                "corrigir": bool(self.v_corrigir.get()), "enfase": bool(self.v_enfase.get()),
                "sem_muletas": bool(self.v_muletas.get())}

    def escrever(self, txt):
        self.app._log(self.log, txt)

    def estado(self, ocupado, rotulo=None):
        self.ocupado = ocupado
        if ocupado:
            self.barra.pack(in_=self.lugar_barra, fill="x")
            self.barra.start(12)
        else:
            self.barra.stop()
            self.barra.pack_forget()
        self.b_acao.configure(state="disabled" if ocupado else "normal",
                              text=rotulo or ("🔥 QUEIMAR LEGENDA NO VÍDEO" if self.palavras else "📝 LEGENDAR"))
        if self.palavras and not ocupado:
            self.b_cancelar.pack(side="left", padx=(6, 0))
        else:
            self.b_cancelar.pack_forget()

    # ------------------------------------------------------------ ações
    def escolher(self):
        if self.ocupado:
            return
        arq = filedialog.askopenfilename(title="Vídeo pra legendar", filetypes=[
            ("Vídeos", " ".join("*" + e for e in legendar.EXTENSOES)), ("Todos", "*.*")])
        if not arq:
            return
        try:
            vi = legendar.info(arq)
        except Exception as e:
            return messagebox.showerror("Legendar", str(e))
        self.video, self.palavras, self.saida, self.t_previa = Path(arq), None, None, None
        formato = "vertical" if vi["altura"] > vi["largura"] else ("quadrado" if vi["altura"] == vi["largura"]
                                                                   else "horizontal")
        m, s = divmod(int(vi["duracao"]), 60)
        self.lbl_video.configure(
            text=f"{self.video.name}   ·   {vi['largura']}×{vi['altura']} {formato}   ·   {m}:{s:02d}   ·   "
                 f"{vi['fps']:g} fps" + ("" if vi["audio"] else "   ·   ⚠ SEM ÁUDIO"),
            fg=TEXTO if vi["audio"] else "#FF6B6B")
        for b in (self.b_abrir, self.b_pasta):
            b.pack_forget()
        self._mostrar_texto(None)
        self.estado(False)
        self.mudou()

    def mudou(self, previa=True):
        import templates_edicao as te
        self.lbl_desc.configure(text=(te.TEMPLATES.get(self.v_tpl.get()) or {}).get("descricao", "")[:70])
        if previa and self.video:
            if self._job:
                self.app.after_cancel(self._job)
            self._job = self.app.after(500, self.atualizar_previa)

    def outro_quadro(self):
        if not self.video:
            return
        import random
        dur = legendar.info(self.video)["duracao"]
        self.t_previa = random.uniform(dur * 0.1, dur * 0.9)
        self.atualizar_previa()

    def atualizar_previa(self):
        self._job = None
        if not self.video:
            return
        video, op, t, pal = self.video, self.opcoes(), self.t_previa, self.palavras

        def gerar():
            img = legendar.previa(video, op, palavras=pal, t=t, largura_saida=340)
            arq = Path(tempfile.gettempdir()) / "legendar_previa.png"
            img.save(arq)
            return arq

        def mostrar(arq):
            if arq and Path(arq).exists():
                self._img = tk.PhotoImage(file=str(arq))
                self.lbl_previa.configure(image=self._img, text="", height=self._img.height())
        self.app._em_segundo_plano(gerar, mostrar)

    def _mostrar_texto(self, conteudo):
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        self.lbl_rev.configure(fg=CINZA)
        if conteudo is None:
            self.lbl_rev.configure(text="")
            self.texto.insert("1.0", "Clique em LEGENDAR. A transcrição aparece aqui pra você revisar.")
            self.texto.configure(state="disabled")
            return
        self.texto.insert("1.0", conteudo)
        for i, linha in enumerate(conteudo.splitlines(), 1):
            fim = linha.find("]") + 1
            if linha.startswith("[") and fim:
                self.texto.tag_add("tempo", f"{i}.0", f"{i}.{fim}")
        self.lbl_rev.configure(text="Revise à vontade: uma frase por linha (não junte nem crie linhas). Mudou a "
                                    "quantidade de palavras? O tempo da frase é redividido sozinho.\nPra tirar uma "
                                    "frase, deixe só o [tempo]. Depois clique em QUEIMAR LEGENDA NO VÍDEO.")
        self.texto.edit_reset()

    def descartar(self):
        if self.ocupado:
            return
        self.palavras = None
        self._mostrar_texto(None)
        self.estado(False)
        self.mudou()

    def acao(self):
        if self.ocupado:
            return
        if not self.video:
            return messagebox.showinfo("Legendar", "Escolha o vídeo primeiro.")
        if self.palavras is None:
            self.transcrever()
        else:
            self.queimar()

    def _rodar(self, trabalho, depois, rotulo):
        self.estado(True, rotulo)

        def fn():
            antes = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = _Saida(self.escrever)
            try:
                return True, trabalho()
            except Exception as e:                       # noqa: BLE001 - erro vira mensagem na tela
                return False, str(e)
            finally:
                sys.stdout, sys.stderr = antes
        self.app._em_segundo_plano(fn, depois)

    def transcrever(self):
        video, op, revisar = self.video, self.opcoes(), bool(self.v_revisar.get())
        self.log.delete("1.0", "end")
        self.escrever(f"Legendando {video.name}...")

        def trabalho():
            pasta = Path(tempfile.mkdtemp(prefix="legendar_audio_"))
            try:
                pal = legendar.transcrever(video, pasta, self.escrever)
            finally:
                import shutil
                shutil.rmtree(pasta, ignore_errors=True)
            pal = legendar.melhorar_com_ia(pal, self.escrever, op["corrigir"], op["enfase"])
            if op["sem_muletas"]:
                pal = legendar.sem_muletas(pal)
            if revisar:
                return pal, None
            return pal, legendar.queimar(video, pal, op, log=self.escrever)

        def depois(r):
            ok, val = r if r else (False, "erro inesperado")
            if not ok:
                self.estado(False)
                self.escrever(f"❌ {val}")
                return messagebox.showerror("Legendar", val)
            pal, saida = val
            if saida:
                return self._pronto(saida)
            self.palavras = pal
            self._mostrar_texto(legendar.texto_para_revisar(pal))
            self.escrever(f"✅ Transcrição pronta ({len(pal)} palavras). Revise o texto e clique em QUEIMAR.")
            self.estado(False)
            self.mudou()
        self._rodar(trabalho, depois, "TRANSCREVENDO... AGUARDE")

    def queimar(self):
        try:
            pal = legendar.aplicar_revisao(self.palavras, self.texto.get("1.0", "end-1c"))
        except ValueError as e:
            return messagebox.showerror("Revisão do texto", str(e))
        if not pal:
            return messagebox.showerror("Legendar", "O texto ficou vazio — não sobrou legenda pra colocar.")
        video, op = self.video, self.opcoes()
        self._rodar(lambda: legendar.queimar(video, pal, op, log=self.escrever),
                    lambda r: self._pronto(r[1]) if r and r[0] else self._falhou(r), "LEGENDANDO... AGUARDE")

    def _falhou(self, r):
        msg = r[1] if r else "erro inesperado"
        self.estado(False)
        self.escrever(f"❌ {msg}")
        messagebox.showerror("Legendar", msg)

    def _pronto(self, saida):
        self.saida = Path(saida)
        self.palavras = None
        self.estado(False)
        self._mostrar_texto(None)
        self.lbl_rev.configure(text=f"✅ Salvo ao lado do original: {self.saida.name} (+ .srt)", fg=VERDE)
        for b in (self.b_abrir, self.b_pasta):
            b.pack(side="left", padx=(6, 0))


class _Saida:
    def __init__(self, func):
        self.func = func

    def write(self, txt):
        if txt and txt.strip():
            self.func(txt.rstrip())

    def flush(self):
        pass


def montar(app, aba):
    return AbaLegendar(app, aba)
