"""
Interface gráfica do Gerador de Cortes 9:16.
Abrir: dois cliques em 'interface.bat'

Abas:
  ✂ Corte        — cola o link, início e fim, gera o corte
  🤖 Automático  — canais da Twitch/YouTube e liga/desliga o monitor
  🎨 Visual      — posição/tamanho/cor da legenda, estilo da faixa (com prévia)
  🔑 Contas & IA — instala o que falta e conecta Claude e Codex
"""
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import traceback
from infraestrutura import salvar_json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

PASTA = Path(__file__).resolve().parent
os.chdir(PASTA)
sys.path.insert(0, str(PASTA))

import cortes   # noqa: E402  (só usa bibliotecas padrão na importação)
import contas   # noqa: E402
import desempenho   # noqa: E402

VERMELHO = "#D90F0F"
FUNDO = "#16161A"
CARTAO = "#222228"
CAMPO = "#2E2E36"
TEXTO = "#F2F2F2"
CINZA = "#9A9AA5"
AMARELO = "#FFD600"
VERDE = "#4ADE80"

CORES_LEGENDA = {"Amarelo": "#FFE600", "Verde neon": "#39FF14", "Ciano": "#00E5FF",
                 "Laranja": "#FF8A00", "Rosa": "#FF4FD8", "Vermelho": "#FF3030"}


def tendencias_fmt(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} mi".replace(".", ",")
    return f"{n / 1000:.1f} mil".replace(".", ",") if n >= 1000 else str(int(n))


class Saida:
    def __init__(self, func):
        self.func = func

    def write(self, txt):
        if txt:
            self.func(txt)

    def flush(self):
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gerador de Cortes 9:16")
        self.configure(bg=FUNDO)
        alt = min(700, self.winfo_screenheight() - 80)
        self.geometry(f"940x{alt}+{max(0, (self.winfo_screenwidth() - 940) // 2)}+10")
        self.minsize(820, 560)
        self.fila = queue.Queue()
        self.cfg = cortes.carregar_config()
        self.ultimo_video = None
        self.gerando = False
        self.monitor_proc = None
        self._previa_job = None
        self._estilo()
        self._topo()
        abas = ttk.Notebook(self)
        abas.pack(fill="both", expand=True, padx=10, pady=(6, 10))
        abas.bind("<<NotebookTabChanged>>", lambda e: self._aba_mudou(abas))
        self.aba_corte = tk.Frame(abas, bg=FUNDO)
        self.aba_legendar = tk.Frame(abas, bg=FUNDO)
        self.aba_galeria = tk.Frame(abas, bg=FUNDO)
        self.aba_tend = tk.Frame(abas, bg=FUNDO)
        self.aba_result = tk.Frame(abas, bg=FUNDO)
        self.aba_auto = tk.Frame(abas, bg=FUNDO)
        self.aba_visual = tk.Frame(abas, bg=FUNDO)
        self.aba_contas = tk.Frame(abas, bg=FUNDO)
        abas.add(self.aba_corte, text="  ✂ Corte  ")
        abas.add(self.aba_legendar, text="  📝 Legendar  ")
        abas.add(self.aba_galeria, text="  🖼 Galeria  ")
        abas.add(self.aba_tend, text="  🔥 Tendências  ")
        abas.add(self.aba_result, text="  📊 Resultados  ")
        abas.add(self.aba_auto, text="  🤖 Automático  ")
        abas.add(self.aba_visual, text="  🎨 Visual  ")
        abas.add(self.aba_contas, text="  🔑 Contas & IA  ")
        self._montar_corte()
        import aba_legendar                    # só legendar um vídeo já editado
        self.legendar = aba_legendar.montar(self, self.aba_legendar)
        self._montar_galeria()
        self._montar_tendencias()
        self._montar_resultados()
        self._montar_auto()
        self._montar_visual()
        self._montar_contas()
        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self.after(100, self._processar_fila)
        self.after(300, self._atualizar_status)
        self.after(400, self._atualizar_previa)

    # =========================================================
    # utilidades de visual
    # =========================================================
    def _estilo(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure("TNotebook", background=FUNDO, borderwidth=0)
        st.configure("TNotebook.Tab", background=CARTAO, foreground=CINZA, padding=(10, 6),
                     font=("Segoe UI", 10, "bold"), borderwidth=0)
        st.map("TNotebook.Tab", background=[("selected", VERMELHO)],
               foreground=[("selected", "white")])
        st.configure("TCheckbutton", background=CARTAO, foreground=TEXTO, font=("Segoe UI", 10))
        st.map("TCheckbutton", background=[("active", CARTAO)])
        st.configure("TRadiobutton", background=CARTAO, foreground=TEXTO, font=("Segoe UI", 10))
        st.map("TRadiobutton", background=[("active", CARTAO)])
        st.configure("TCombobox", fieldbackground=CAMPO, background=CAMPO, foreground=TEXTO,
                     arrowcolor=TEXTO)
        st.map("TCombobox", fieldbackground=[("readonly", CAMPO)], foreground=[("readonly", TEXTO)],
               selectbackground=[("readonly", CAMPO)], selectforeground=[("readonly", TEXTO)])
        self.option_add("*TCombobox*Listbox.background", CAMPO)
        self.option_add("*TCombobox*Listbox.foreground", TEXTO)
        st.configure("Horizontal.TProgressbar", background=VERMELHO, troughcolor=CAMPO,
                     bordercolor=FUNDO, lightcolor=VERMELHO, darkcolor=VERMELHO)

    def _topo(self):
        topo = tk.Frame(self, bg=VERMELHO)
        topo.pack(fill="x")
        tk.Frame(topo, bg=AMARELO, height=4).pack(fill="x", side="bottom")
        tk.Label(topo, text="✂  GERADOR DE CORTES 9:16", bg=VERMELHO, fg="white",
                 font=("Segoe UI", 15, "bold"), pady=9).pack(side="left", padx=16)
        self.lbl_ia = tk.Label(topo, text="", bg=VERMELHO, fg="white", font=("Segoe UI", 9, "bold"))
        self.lbl_ia.pack(side="right", padx=16)
        import atualizar
        self.b_versao = tk.Button(topo, text=f"v{atualizar.versao_atual()}  ⟳", command=self._janela_atualizar,
                                  bg="#A80C0C", fg="white", activebackground="#A80C0C", activeforeground="white",
                                  relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 9, "bold"), padx=10, pady=3)
        self.b_versao.pack(side="right")
        import editorial
        for txt, cmd in (("🎬 Central de edição", lambda: editorial.abrir(self)),
                         ("⚙ Qualidade", lambda: editorial.configurar(self))):
            tk.Button(topo, text=txt, command=cmd, bg="#B30F14", fg="white", activebackground="#8E0B0F",
                      activeforeground="white", relief="flat", bd=0, cursor="hand2",
                      font=("Segoe UI", 9, "bold"), padx=10, pady=3).pack(side="left", padx=(12, 0))
        self.after(4000, self._checar_atualizacao_silencioso)

    def _checar_atualizacao_silencioso(self):
        import atualizar
        repo = self.cfg.get("github_repo", "").strip()
        if not repo and not atualizar.em_git():
            return

        def rodar():
            try:
                return atualizar.verificar(repo)
            except Exception:
                return None

        def mostrar(r):
            if r and r[0]:
                self._nova_versao = r
                self.b_versao.configure(text=f"⬆ NOVA VERSÃO v{r[1]}", bg=AMARELO, fg="#16161a",
                                        activebackground=AMARELO)
        self._em_segundo_plano(rodar, mostrar)

    def _janela_atualizar(self):
        import atualizar
        from tkinter import simpledialog
        repo = self.cfg.get("github_repo", "").strip()
        if not repo and not atualizar.em_git():        # no git, o GitHub já está ligado à pasta
            repo = simpledialog.askstring(
                "Atualizações", f"Versão instalada: {atualizar.versao_atual()}\n\n"
                "Pra atualizar sozinho, coloque o seu repositório do GitHub onde você publica as versões\n"
                "(ex: seuusuario/gerador-de-cortes). Deixe vazio pra cancelar.", parent=self) or ""
            repo = repo.strip()
            if not repo:
                return
            self.cfg["github_repo"] = repo
            self._salvar_cfg()
        try:
            tem, nova, url, notas = atualizar.verificar(repo)
        except Exception as e:
            if messagebox.askyesno("Atualizações", f"Não consegui verificar ({str(e)[:120]}).\n\n"
                                   f"Trocar o repositório ({repo})?"):
                self.cfg["github_repo"] = ""
                self._salvar_cfg()
                self._janela_atualizar()
            return
        if not tem:
            return messagebox.showinfo("Atualizações", f"Você já está na versão mais nova ({atualizar.versao_atual()}).")
        if not messagebox.askyesno("Nova versão!", f"Versão {nova} disponível (você tem {atualizar.versao_atual()}).\n\n"
                                   f"{notas[:500]}\n\nAtualizar agora? Suas configurações, contas e cortes não são mexidos."):
            return
        msgs = []
        try:
            atualizar.aplicar(url, nova, log=msgs.append)
            messagebox.showinfo("Atualizado", "\n".join(msgs))
        except Exception as e:
            messagebox.showerror("Atualização", f"Deu erro: {str(e)[:200]}")

    def _cartao(self, pai, **pack):
        c = tk.Frame(pai, bg=CARTAO, padx=16, pady=8)
        c.pack(**pack)
        return c

    def _rotulo(self, pai, txt, dica=None, top=8):
        tk.Label(pai, text=txt, bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10, "bold"),
                 anchor="w").pack(fill="x", pady=(top, 0))
        if dica:
            tk.Label(pai, text=dica, bg=CARTAO, fg=CINZA, font=("Segoe UI", 8),
                     anchor="w").pack(fill="x")

    def _campo(self, pai):
        return tk.Entry(pai, bg=CAMPO, fg=TEXTO, insertbackground=TEXTO, relief="flat",
                        font=("Segoe UI", 11), highlightthickness=1,
                        highlightbackground="#3A3A44", highlightcolor=VERMELHO)

    def _botao(self, pai, txt, cmd, cor="#34343E", cor_txt=TEXTO, grande=False):
        return tk.Button(pai, text=txt, command=cmd, bg=cor, fg=cor_txt, activebackground=cor,
                         activeforeground=cor_txt, relief="flat", cursor="hand2", bd=0,
                         font=("Segoe UI", 12 if grande else 9, "bold"),
                         padx=12, pady=9 if grande else 5, disabledforeground="#777")

    def _caixa_log(self, pai, altura=8):
        t = tk.Text(pai, bg="#0E0E11", fg="#C8C8D0", relief="flat", height=altura,
                    font=("Consolas", 9), wrap="word", padx=8, pady=6)
        t.tag_configure("ok", foreground=VERDE)
        t.tag_configure("erro", foreground="#FF6B6B")
        return t

    def _log(self, caixa, txt):
        """Pode ser chamado de qualquer thread."""
        self.fila.put(("log", caixa, txt))

    def _em_segundo_plano(self, func, depois=None):
        def rodar():
            try:
                r = func()
            except Exception:
                r = None
                traceback.print_exc()
            if depois:
                self.fila.put(("call", depois, r))
        threading.Thread(target=rodar, daemon=True).start()

    def _processar_fila(self):
        try:
            while True:
                item = self.fila.get_nowait()
                if item[0] == "log":
                    _, caixa, txt = item
                    tag = "ok" if "✅" in txt else ("erro" if "❌" in txt else None)
                    if caixa is not self.log_corte and not txt.endswith("\n"):
                        txt += "\n"
                    caixa.insert("end", txt, tag)
                    caixa.see("end")
                elif item[0] == "call":
                    item[1](item[2])
        except queue.Empty:
            pass
        self.after(100, self._processar_fila)

    def _salvar_cfg(self):
        """Salva só as opções GLOBAIS (IA, chaves...). As de perfil são salvas na aba Visual."""
        base = cortes.carregar_config()
        for k, v in self.cfg.items():
            if k not in cortes.CHAVES_PERFIL and k not in ("perfis", "perfil_em_uso"):
                base[k] = v
        cortes.salvar_config(base)
        self.cfg["perfis"] = base.get("perfis", {})

    def _abrir(self, caminho):
        if os.name == "nt":
            os.startfile(caminho)
        else:
            subprocess.Popen(["xdg-open", str(caminho)])

    # =========================================================
    # ABA: CORTE
    # =========================================================
    def _montar_corte(self):
        esq = self._cartao(self.aba_corte, side="left", fill="both", expand=True,
                           padx=(0, 8), pady=8)
        dir_ = tk.Frame(self.aba_corte, bg=FUNDO, width=330)
        dir_.pack(side="left", fill="both", pady=8)
        dir_.pack_propagate(False)

        self._rotulo(esq, "Link do vídeo", "YouTube, VOD da Twitch ou um vídeo do seu PC", top=2)
        l1 = tk.Frame(esq, bg=CARTAO)
        l1.pack(fill="x", pady=(3, 0))
        self.e_link = self._campo(l1)
        self.e_link.pack(side="left", fill="x", expand=True, ipady=5)
        self._botao(l1, "📁 Vídeo do PC", self._escolher_video).pack(side="left", padx=(8, 0))
        self.chat_arquivo = None
        self.b_chat = self._botao(l1, "💬 Chat", self._escolher_chat)
        self.b_chat.pack(side="left", padx=(6, 0))

        # modo automático: a IA acha os melhores momentos
        auto = tk.Frame(esq, bg=CARTAO)
        auto.pack(fill="x", pady=(8, 0))
        self.v_achar = tk.BooleanVar(value=False)
        ttk.Checkbutton(auto, text="🔎 Achar os melhores momentos sozinho",
                        variable=self.v_achar, command=self._modo_achar).pack(side="left")
        self.v_qtd = tk.IntVar(value=3)
        self.v_durc = tk.IntVar(value=65)
        for txt, var, a_, b_ in [("cortes:", self.v_qtd, 1, 8), ("seg:", self.v_durc, 20, 120)]:
            tk.Label(auto, text=txt, bg=CARTAO, fg=CINZA, font=("Segoe UI", 9)).pack(side="left", padx=(10, 2))
            tk.Spinbox(auto, from_=a_, to=b_, textvariable=var, width=4, bg=CAMPO, fg=TEXTO,
                       buttonbackground=CAMPO, relief="flat", insertbackground=TEXTO).pack(side="left")

        tempos = tk.Frame(esq, bg=CARTAO)
        tempos.pack(fill="x")
        for i, (nome, attr, ex) in enumerate([("Início", "e_ini", "ex: 12:30"),
                                              ("Fim", "e_fim", "ex: 13:20")]):
            col = tk.Frame(tempos, bg=CARTAO)
            col.pack(side="left", fill="x", expand=True, padx=(0, 10) if i == 0 else 0)
            self._rotulo(col, nome, ex, top=4)
            e = self._campo(col)
            e.pack(fill="x", ipady=4, pady=(2, 0))
            setattr(self, attr, e)

        self._rotulo(esq, "Pergunta da faixa", "Vazio = a IA cria", top=6)
        self.e_perg = self._campo(esq)
        self.e_perg.pack(fill="x", ipady=4, pady=(2, 0))

        self._rotulo(esq, "Foto do topo", "Vazio = automático (veja o estilo abaixo)", top=6)
        l2 = tk.Frame(esq, bg=CARTAO)
        l2.pack(fill="x", pady=(2, 0))
        self.e_foto = self._campo(l2)
        self.e_foto.pack(side="left", fill="x", expand=True, ipady=4)
        self._botao(l2, "Escolher...", self._escolher_foto).pack(side="left", padx=(8, 0))

        opc = tk.Frame(esq, bg=CARTAO)
        opc.pack(fill="x", pady=(8, 2))
        self.v_leg = tk.BooleanVar(value=True)
        self.v_inteiro = tk.BooleanVar(value=False)
        ttk.Checkbutton(opc, text="Legenda no vídeo", variable=self.v_leg).pack(side="left")
        ttk.Checkbutton(opc, text="Vídeo inteiro",
                        variable=self.v_inteiro).pack(side="left", padx=12)
        self.v_perfil_corte = tk.StringVar(value="Automático (pelo canal)")
        self.cb_perfil_corte = ttk.Combobox(opc, textvariable=self.v_perfil_corte, state="readonly", width=19,
                                            values=["Automático (pelo canal)"] + cortes.nomes_perfis())
        self.cb_perfil_corte.pack(side="right")
        tk.Label(opc, text="Perfil:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10)).pack(side="right", padx=4)
        l3 = tk.Frame(esq, bg=CARTAO)
        l3.pack(fill="x", pady=(4, 2))
        tk.Label(l3, text="Topo:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10)).pack(side="left")
        self.v_topo = tk.StringVar(value="Automático")
        ttk.Combobox(l3, textvariable=self.v_topo, state="readonly", width=22,
                     values=["Automático", "Estilo thumbnail ✨", "Frame escolhido pela IA"]
                     ).pack(side="left", padx=(6, 14))
        tk.Label(l3, text="Transcrição:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10)).pack(side="left")
        self.modelos_whisper = {"Automática ⭐ (small no corte)": "auto", "base (rápida)": "base",
                                "small (mais precisa)": "small", "turbo (máxima, lenta)": "turbo"}
        self.v_modelo = tk.StringVar(value="Automática ⭐ (small no corte)")
        ttk.Combobox(l3, textvariable=self.v_modelo, state="readonly", width=26,
                     values=list(self.modelos_whisper)).pack(side="left", padx=6)
        l4 = tk.Frame(esq, bg=CARTAO)
        l4.pack(fill="x", pady=(4, 2))
        tk.Label(l4, text="Formato:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10)).pack(side="left")
        self.formatos_corte = {"Curto 9:16 (Shorts/TikTok)": "curto", "Longo 16:9 (YouTube normal)": "longo",
                               "Os dois ⭐": "ambos"}
        self.v_formato_corte = tk.StringVar(value="Curto 9:16 (Shorts/TikTok)")
        ttk.Combobox(l4, textvariable=self.v_formato_corte, state="readonly", width=28,
                     values=list(self.formatos_corte)).pack(side="left", padx=6)
        tk.Label(l4, text="o longo abre o contexto em volta do momento (3–8 min)", bg=CARTAO, fg=CINZA,
                 font=("Segoe UI", 8)).pack(side="left", padx=4)

        self.b_gerar = self._botao(esq, "GERAR CORTE", self._gerar, cor=VERMELHO,
                                   cor_txt="white", grande=True)
        self.b_gerar.pack(fill="x", pady=(8, 4))
        self.barra = ttk.Progressbar(esq, mode="determinate", style="Horizontal.TProgressbar")
        self.barra.pack(fill="x")

        # direita: log + botões
        rod = tk.Frame(dir_, bg=FUNDO)
        rod.pack(fill="x", side="bottom", pady=(8, 0))
        self.b_abrir_video = self._botao(rod, "▶ Abrir último corte", self._abrir_video)
        self.b_abrir_video.pack(side="left", fill="x", expand=True)
        self.b_abrir_video.configure(state="disabled")
        self._botao(rod, "📁 Pasta dos cortes", self._abrir_pasta).pack(side="left", fill="x",
                                                                       expand=True, padx=(6, 0))
        self.log_corte = self._caixa_log(dir_)
        self.log_corte.pack(fill="both", expand=True)
        self.log_corte.insert("end", "Cole o link, coloque início e fim e clique em GERAR CORTE.\n")

    def _escolher_video(self):
        f = filedialog.askopenfilename(title="Escolha o vídeo", filetypes=[
            ("Vídeos", "*.mp4 *.mkv *.mov *.ts *.webm *.avi"), ("Todos", "*.*")])
        if f:
            self.e_link.delete(0, "end")
            self.e_link.insert(0, f)

    def _escolher_chat(self):
        """Chat da live (opcional): TwitchDownloader, chat-downloader, yt-dlp ou texto. Com o chat,
        o 'achar momentos' usa onde o chat explodiu (sem gastar IA)."""
        if self.chat_arquivo:
            self.chat_arquivo = None
            self.b_chat.configure(text="💬 Chat")
            return
        f = filedialog.askopenfilename(title="Arquivo de chat da live (opcional)", filetypes=[
            ("Chat", "*.json *.txt"), ("Todos", "*.*")])
        if f:
            import chat_vod
            try:
                n = len(chat_vod.ler_arquivo(f))
            except (OSError, ValueError) as e:
                return messagebox.showerror("Chat", f"Não consegui ler esse arquivo: {e}")
            if not n:
                return messagebox.showwarning("Chat", "Não achei mensagens com tempo nesse arquivo.")
            self.chat_arquivo = f
            self.b_chat.configure(text=f"💬 {n} msgs ✕")

    def _escolher_foto(self):
        f = filedialog.askopenfilename(title="Escolha a foto", filetypes=[
            ("Imagens", "*.jpg *.jpeg *.png *.webp"), ("Todos", "*.*")])
        if f:
            self.e_foto.delete(0, "end")
            self.e_foto.insert(0, f)

    def _abrir_video(self):
        if self.ultimo_video and Path(self.ultimo_video).exists():
            self._abrir(self.ultimo_video)

    def _abrir_pasta(self):
        p = PASTA / "cortes_prontos"
        p.mkdir(exist_ok=True)
        self._abrir(p)

    def _modo_achar(self):
        estado = "disabled" if self.v_achar.get() else "normal"
        self.e_ini.configure(state=estado)
        self.e_fim.configure(state=estado)
        self.b_gerar.configure(text="ACHAR MOMENTOS E GERAR CORTES" if self.v_achar.get() else "GERAR CORTE")

    def _gerar(self):
        if self.gerando:
            return
        link = self.e_link.get().strip().strip('"')
        achar = self.v_achar.get()
        ini, fim = self.e_ini.get().strip(), self.e_fim.get().strip()
        tempo_ok = lambda t: bool(re.fullmatch(r"\d+(:\d{1,2}){0,2}(\.\d+)?", t))  # noqa: E731
        if not link:
            return messagebox.showwarning("Falta o link", "Cole o link do vídeo ou escolha um arquivo.")
        if not achar:
            if not (tempo_ok(ini) and tempo_ok(fim)):
                return messagebox.showwarning("Tempo inválido", "Use o formato 12:30 ou 1:02:30.")
            if cortes.parse_tempo(fim) <= cortes.parse_tempo(ini):
                return messagebox.showwarning("Tempo inválido", "O fim tem que ser depois do início.")
        if contas.faltando_bibliotecas() or not contas.tem_ffmpeg():
            return messagebox.showwarning("Falta instalar", "Vá na aba 'Contas & IA' e clique em "
                                          "INSTALAR TUDO.")
        topo = {"Estilo thumbnail ✨": "thumbnail", "Frame escolhido pela IA": "frame"}.get(
            self.v_topo.get(), "auto")
        opcoes = dict(foto=self.e_foto.get().strip().strip('"') or None,
                      pergunta=self.e_perg.get().strip() or None, legenda=self.v_leg.get(),
                      modo="inteiro" if self.v_inteiro.get() else "cortado", topo=topo)
        modelo = self.modelos_whisper.get(self.v_modelo.get(), "auto")
        formato = self.formatos_corte.get(self.v_formato_corte.get(), "curto")
        chat_arq = self.chat_arquivo
        perfil = None if self.v_perfil_corte.get().startswith("Automático") else self.v_perfil_corte.get()
        opcoes["perfil"] = perfil
        try:
            qtd, durc = int(self.v_qtd.get()), int(self.v_durc.get())
        except (tk.TclError, ValueError):
            qtd, durc = 3, 60
        self.gerando = True
        self.b_gerar.configure(text="TRABALHANDO... AGUARDE", state="disabled", bg="#7A0A0A")
        self.barra.configure(mode="indeterminate")
        self.barra.start(12)
        self.log_corte.delete("1.0", "end")

        def trabalho():
            sys.stdout = sys.stderr = Saida(lambda t: self._log(self.log_corte, t))
            try:
                cortes.MODELO_WHISPER = modelo
                if not achar:
                    return True, str(cortes.gerar_corte(link, ini, fim, formato=formato, **opcoes))
                import momentos
                achados, meta = momentos.achar_momentos(link, qtd, durc, log=print, chat_arquivo=chat_arq)
                extra = {} if re.match(r"^https?://", link) else {"meta": meta}
                if len(achados) >= 2 and cortes.carregar_config().get("ia_lote", True):
                    saidas = cortes.gerar_cortes_lote(
                        link, [{"inicio": m["inicio"], "fim": m["fim"], "contexto": m.get("motivo", "")}
                               for m in achados], formato=formato, **opcoes, **extra)
                    feitos = [str(x) for x in saidas if x]
                else:
                    feitos = []
                    for i, m in enumerate(achados, 1):
                        print(f"\n===== Corte {i} de {len(achados)} =====")
                        r = cortes.gerar_corte(link, m["inicio"], m["fim"], formato=formato, **opcoes, **extra)
                        if r:
                            feitos.append(str(r))
                if not feitos:
                    return False, "não encontrei momentos bons"
                return True, feitos[-1]
            except BaseException as e:
                print(traceback.format_exc()[-1200:])
                return False, str(e) or e.__class__.__name__
        self._em_segundo_plano(trabalho, self._fim_corte)

    def _fim_corte(self, resultado):
        ok, info = resultado or (False, "erro desconhecido")
        self.gerando = False
        self.barra.stop()
        self.barra.configure(mode="determinate")
        self.barra["value"] = 0
        self.b_gerar.configure(state="normal", bg=VERMELHO)
        self._modo_achar()
        if ok:
            self.ultimo_video = info
            self.b_abrir_video.configure(state="normal")
            self._log(self.log_corte, f"\n✅ CORTE PRONTO!\n{Path(info).name}\n")
        else:
            self._log(self.log_corte, f"\n❌ Deu erro: {info}\n")

    # =========================================================
    # ABA: GALERIA (revisar, postar, refazer, descartar)
    # =========================================================
    def _montar_galeria(self):
        topo = tk.Frame(self.aba_galeria, bg=CARTAO, padx=12, pady=8)
        topo.pack(fill="x", pady=(8, 6))
        tk.Label(topo, text="Mostrar:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10)).pack(side="left")
        self.v_filtro = tk.StringVar(value="Para revisar")
        cb = ttk.Combobox(topo, textvariable=self.v_filtro, state="readonly", width=14,
                          values=["Para revisar", "Postados", "Longos 16:9", "Compilações", "Todos"])
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._carregar_galeria())
        self._botao(topo, "⟳ Atualizar", self._carregar_galeria).pack(side="left", padx=4)
        self._botao(topo, "📱 Celular", self._abrir_celular).pack(side="left", padx=4)
        tk.Label(topo, text="Conta do YouTube do perfil:", bg=CARTAO, fg=TEXTO,
                 font=("Segoe UI", 10)).pack(side="left", padx=(14, 4))
        self.v_perfil_gal = tk.StringVar(value="Padrão")
        self.cb_perfil_gal = ttk.Combobox(topo, textvariable=self.v_perfil_gal, state="readonly", width=16,
                                          values=cortes.nomes_perfis())
        self.cb_perfil_gal.pack(side="left")
        self.cb_perfil_gal.bind("<<ComboboxSelected>>", lambda e: self._carregar_galeria())
        self.b_yt = self._botao(topo, "▶ Conectar YouTube", self._conectar_youtube)
        self.b_yt.pack(side="right")

        corpo = tk.Frame(self.aba_galeria, bg=FUNDO)
        corpo.pack(fill="both", expand=True)
        self.can_gal = tk.Canvas(corpo, bg=FUNDO, highlightthickness=0)
        barra = ttk.Scrollbar(corpo, orient="vertical", command=self.can_gal.yview)
        self.can_gal.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.can_gal.pack(side="left", fill="both", expand=True)
        self.gal_interno = tk.Frame(self.can_gal, bg=FUNDO)
        self._gal_janela = self.can_gal.create_window((0, 0), window=self.gal_interno, anchor="nw")
        self.gal_interno.bind("<Configure>", lambda e: self.can_gal.configure(
            scrollregion=self.can_gal.bbox("all")))
        self.can_gal.bind("<Configure>", lambda e: self.can_gal.itemconfigure(self._gal_janela, width=e.width))
        self.bind_all("<MouseWheel>", self._rolar)
        self.lbl_gal = tk.Label(self.aba_galeria, text="", bg=FUNDO, fg=CINZA, font=("Segoe UI", 9),
                                anchor="w")
        self.lbl_gal.pack(fill="x", pady=(4, 0))
        self._miniaturas = {}
        self._aba_atual = ""

    def _aba_mudou(self, abas):
        nome = abas.tab(abas.select(), "text")
        self._aba_atual = "galeria" if "Galeria" in nome else "tend" if "Tendências" in nome else \
            "result" if "Resultados" in nome else "contas" if "Contas" in nome else ""
        if self._aba_atual == "galeria":
            self._carregar_galeria()
        elif self._aba_atual == "tend" and not getattr(self, "_tend_carregado", False):
            self._tend_carregado = True
            self._mostrar_radar_cache()
        elif self._aba_atual == "result":
            self._carregar_resultados()

    def _lista_cortes(self):
        base = PASTA / "cortes_prontos"
        if not base.exists():
            return []
        vids = [v for v in base.rglob("*.mp4")
                if not any(p in v.parts for p in ("_trabalho", "_descartados", ".miniaturas", "_edicao"))]
        return sorted(vids, key=lambda v: v.stat().st_mtime, reverse=True)

    def _carregar_galeria(self):
        import postagem
        filtro = self.v_filtro.get()
        itens = []
        for v in self._lista_cortes():
            f = postagem.ler_ficha(v)
            postado = f.get("status") == "postado" or f.get("tiktok")
            if filtro == "Para revisar" and postado:
                continue
            if filtro == "Postados" and not postado:
                continue
            if filtro == "Compilações" and f.get("tipo") != "compilacao":
                continue
            if filtro == "Longos 16:9" and f.get("tipo") != "longo":
                continue
            itens.append((v, f))
        pg = self.v_perfil_gal.get()
        self.b_yt.configure(text="✔ conectado" if postagem.youtube_conectado(pg) else "▶ Conectar YouTube")
        self.lbl_gal.configure(text=f"{len(itens)} corte(s). Dica: aprovar no YouTube agenda no próximo "
                                    f"horário livre — o YouTube publica sozinho, mesmo com o PC desligado.")

        def miniaturas():
            pasta = PASTA / "cortes_prontos" / ".miniaturas"
            pasta.mkdir(parents=True, exist_ok=True)
            for v, _ in itens:
                capa = v.with_suffix(".capa.jpg")
                marca = int(max(v.stat().st_mtime, capa.stat().st_mtime if capa.exists() else 0))
                m = pasta / (v.stem[:60] + f"_{marca}.jpg")
                if not m.exists():
                    if capa.exists():                 # a capa (escolhida ou automática) vira a miniatura
                        try:
                            from PIL import Image
                            Image.open(capa).convert("RGB").resize((90, 160)).save(m, quality=85)
                        except Exception:
                            pass
                    if not m.exists():
                        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1.5", "-i", str(v),
                                        "-frames:v", "1", "-vf", "scale=90:160", str(m)],
                                       creationflags=cortes.SEM_JANELA)
                self._miniaturas[v] = m
            return itens
        self._em_segundo_plano(miniaturas, self._desenhar_galeria)

    def _desenhar_galeria(self, itens):
        for w in self.gal_interno.winfo_children():
            w.destroy()
        if not itens:
            tk.Label(self.gal_interno, text="Nenhum corte aqui ainda.", bg=FUNDO, fg=CINZA,
                     font=("Segoe UI", 11)).pack(pady=40)
            return
        try:
            from PIL import Image, ImageTk
        except ImportError:
            Image = None
        self._fotos_gal = []
        for i, (v, f) in enumerate(itens[:80]):
            card = tk.Frame(self.gal_interno, bg=CARTAO, padx=8, pady=8)
            card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=4, pady=4)
            self.gal_interno.grid_columnconfigure(i % 2, weight=1)
            m = self._miniaturas.get(v)
            if Image and m and Path(m).exists():
                foto = ImageTk.PhotoImage(Image.open(m))
                self._fotos_gal.append(foto)
                tk.Label(card, image=foto, bg=CARTAO, cursor="hand2").pack(side="left")
            info = tk.Frame(card, bg=CARTAO)
            info.pack(side="left", fill="both", expand=True, padx=(10, 0))
            tk.Label(info, text=f.get("titulo") or v.stem, bg=CARTAO, fg=TEXTO, wraplength=280,
                     justify="left", font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
            detalhes = v.parent.name if v.parent.name != "cortes_prontos" else ""
            if f.get("nota") is not None:
                detalhes += f"  ·  nota {f['nota']:g}/10"
            import resultados
            vistas = resultados.views_de(f)
            selos = []
            if vistas:
                selos.append(f"👁 {tendencias_fmt(vistas)}")
            if f.get("variante"):
                selos.append(f"A/B: {f['variante']}")
            if f.get("idioma") == "es":
                selos.append("🌎 espanhol")
            if f.get("tipo") == "compilacao":
                selos.append("🎬 compilação")
            if f.get("tipo") == "longo":
                selos.append(f"🖥 longo 16:9 ({int((f.get('duracao') or 0) // 60)} min)")
            if f.get("parte"):
                selos.append(f"📺 parte {f['parte']}")
            if f.get("layout") in ("podcast", "jogo"):
                selos.append("🎙 podcast" if f["layout"] == "podcast" else "🎮 jogo")
            if f.get("status") == "aprovado":
                selos.append("✓ aprovado no celular")
            if f.get('sincronia') and not f['sincronia'].get('confirmado'):
                selos.append('⚠ sincronização estimada')
            if f.get('palavras_revisar'):
                selos.append(f"⚠ {f['palavras_revisar']} palavra(s) para revisar")
            if f.get("parecidos"):
                selos.append(f"⚠ {f['parecidos']} parecido(s) no YouTube")
            if f.get("perfil") and f["perfil"] != "Padrão":
                selos.append(f"perfil: {f['perfil']}")
            if selos:
                detalhes += ("  ·  " if detalhes else "") + "  ·  ".join(selos)
            tk.Label(info, text=detalhes, bg=CARTAO, fg=CINZA, font=("Segoe UI", 8), anchor="w",
                     wraplength=300, justify="left").pack(fill="x")
            for aviso in self._avisos_revisao(f):
                tk.Label(info, text=aviso, bg=CARTAO, fg=AMARELO, font=("Segoe UI", 8, "bold"), anchor="w",
                         wraplength=300, justify="left").pack(fill="x")
            revisao = self._texto_revisao(f)
            if revisao:
                tk.Label(info, text=revisao, bg=CARTAO, fg=TEXTO, font=("Segoe UI", 8), anchor="w",
                         wraplength=300, justify="left").pack(fill="x", pady=(2, 0))
            st = "NOVO"
            cor = AMARELO
            if f.get("status") == "postado":
                q = f.get("youtube_quando", "")
                st, cor = (f"YOUTUBE ✓ {q[8:10]}/{q[5:7]} {q[11:16]}" if q else "YOUTUBE ✓"), VERDE
            if f.get("tiktok"):
                st += "  ·  TIKTOK ✓"
                cor = VERDE
            tk.Label(info, text=st, bg=CARTAO, fg=cor, font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", pady=(2, 4))
            bts = tk.Frame(info, bg=CARTAO)
            bts.pack(fill="x", side="bottom")
            for txt, fn in [("▶", lambda v=v: self._abrir(v)), ("YouTube", lambda v=v: self._postar_yt(v)),
                            ("TikTok", lambda v=v: self._postar_tt(v)), ("✏", lambda v=v, f=f: self._refazer(v, f)),
                            ("📈", lambda v=v: self._views_manual(v)),
                            ("🖼", lambda v=v, f=f: self._escolher_capa(v, f)),
                            ("Legenda", lambda v=v: __import__("editorial").editar_legenda(self, v)),
                            ("🗑", lambda v=v: self._descartar(v))]:
                b = self._botao(bts, txt, fn, cor=VERMELHO if txt in ("YouTube", "TikTok") else "#34343E",
                                cor_txt="white")
                b.configure(padx=7, pady=3)
                b.pack(side="left", padx=(0, 4))

    @staticmethod
    def _avisos_revisao(f):
        """Avisos que pedem atenção antes de postar."""
        avisos = []
        musica = f.get("musica_de_fundo") or {}
        if musica.get("provavel"):
            avisos.append(f"🎵 Parece ter música de fundo (confiança {musica.get('confianca', '?')}): "
                          "música com direitos pode mutar ou bloquear no YouTube. Confira.")
        if (f.get("ia") or {}).get("falhou"):
            avisos.append("🤖 A IA não respondeu neste corte: pergunta e título feitos no PC. Revise.")
        return avisos

    @staticmethod
    def _texto_revisao(f):
        """O que a IA viu no trecho e por que deu a nota (revisão em segundos)."""
        partes = []
        if f.get("resumo"):
            partes.append("💬 " + str(f["resumo"])[:170])
        if f.get("motivo_nota"):
            partes.append("📊 " + str(f["motivo_nota"])[:120])
        return "\n".join(partes)

    def _escolher_capa(self, v, f):
        """Mostra 3 opções de capa (+ a atual) e salva a escolhida como <corte>.capa.jpg."""
        import acabamento
        import postagem
        import shutil
        import tempfile
        pasta = Path(tempfile.mkdtemp(prefix="capas_"))
        self.lbl_gal.configure(text="Gerando opções de capa...")

        def gerar():
            dur = cortes.duracao_video(v)
            return acabamento.opcoes_capa(v, pasta, dur, pergunta=f.get("pergunta"), fonte=cortes.fonte,
                                          clean=f.get("estilo") == "clean")

        def mostrar(opcoes):
            self.lbl_gal.configure(text="")
            atual = v.with_suffix(".capa.jpg")
            lista = ([("atual", atual)] if atual.exists() else []) + [(f"{t:.0f}s", a) for t, a in (opcoes or [])]
            if not lista:
                shutil.rmtree(pasta, ignore_errors=True)
                return messagebox.showwarning("Capa", "Não consegui tirar quadros desse vídeo.")
            from PIL import Image, ImageTk
            jan = tk.Toplevel(self)
            jan.title("Escolha a capa")
            jan.configure(bg=FUNDO, padx=14, pady=12)
            jan.transient(self)
            tk.Label(jan, text="Clique na capa que você quer usar (TikTok/Reels e miniatura da galeria)",
                     bg=FUNDO, fg=TEXTO, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 8))
            linha = tk.Frame(jan, bg=FUNDO)
            linha.pack()
            jan._fotos = []

            def escolher(arq):
                if Path(arq).resolve() != atual.resolve():
                    shutil.copy2(arq, atual)
                ficha = postagem.ler_ficha(v)
                ficha["capa"] = atual.name
                postagem.salvar_ficha(v, ficha)
                jan.destroy()
                self._carregar_galeria()

            for rotulo, arq in lista:
                col = tk.Frame(linha, bg=FUNDO)
                col.pack(side="left", padx=6)
                foto = ImageTk.PhotoImage(Image.open(arq).convert("RGB").resize((180, 320)))
                jan._fotos.append(foto)
                tk.Button(col, image=foto, relief="flat", bg=CARTAO, activebackground=AMARELO, cursor="hand2",
                          command=lambda a=arq: escolher(a)).pack()
                tk.Label(col, text=rotulo, bg=FUNDO, fg=CINZA, font=("Segoe UI", 9)).pack()
            jan.bind("<Destroy>", lambda e: shutil.rmtree(pasta, ignore_errors=True) if e.widget is jan else None)
        self._em_segundo_plano(gerar, mostrar)

    def _ajuda_youtube(self):
        if messagebox.askyesno("Configurar o YouTube (uma vez só)",
                               "Pra postar sozinho, o YouTube pede um arquivo 'client_secret.json':\n\n"
                               "1. Abra console.cloud.google.com e crie um projeto\n"
                               "2. 'APIs e serviços' → Biblioteca → ative 'YouTube Data API v3'\n"
                               "    e também 'YouTube Analytics API' (pros números e a retenção)\n"
                               "3. 'Tela de consentimento OAuth' → Externo → preencha nome e e-mail →\n"
                               "    coloque seu e-mail em 'Usuários de teste' → depois 'Publicar app'\n"
                               "    (assim o login não expira a cada 7 dias)\n"
                               "4. 'Credenciais' → Criar → 'ID do cliente OAuth' → 'App para computador'\n"
                               "5. Baixe o JSON\n\n"
                               "Já baixou? Clique SIM pra escolher o arquivo."):
            f = filedialog.askopenfilename(title="Escolha o arquivo JSON baixado",
                                           filetypes=[("JSON", "*.json")])
            if f:
                import shutil
                shutil.copy(f, PASTA / "client_secret.json")
                return True
        return False

    def _abrir_celular(self):
        """Galeria no celular: liga o servidorzinho e mostra endereço + PIN + QR code."""
        import celular
        try:
            if not self.cfg.get("pin_celular"):          # PIN fixo: não muda a cada vez que abre
                import secrets
                self.cfg["pin_celular"] = f"{secrets.randbelow(10000):04d}"
                self._salvar_cfg()
            url, pin = celular.iniciar(self.cfg["pin_celular"])
        except OSError as e:
            return messagebox.showerror("Celular", f"Não consegui ligar a galeria do celular:\n{e}")
        jan = tk.Toplevel(self)
        jan.title("Galeria no celular")
        jan.configure(bg=FUNDO, padx=20, pady=16)
        jan.resizable(False, False)
        tk.Label(jan, text="📱 Abra no celular (mesmo Wi-Fi do PC)", bg=FUNDO, fg=TEXTO,
                 font=("Segoe UI", 12, "bold")).pack()
        pasta_qr = PASTA / "cortes_prontos" / ".miniaturas"
        pasta_qr.mkdir(parents=True, exist_ok=True)
        qr = celular.qr_png(url, pasta_qr / "qr_celular.png")
        if qr:
            from PIL import Image, ImageTk
            jan._qr = ImageTk.PhotoImage(Image.open(qr))
            tk.Label(jan, image=jan._qr, bg=FUNDO).pack(pady=10)
            tk.Label(jan, text="Aponte a câmera do celular pro QR code", bg=FUNDO, fg=CINZA,
                     font=("Segoe UI", 9)).pack()
        e = tk.Entry(jan, font=("Consolas", 14), justify="center", bg=CAMPO, fg=TEXTO, relief="flat",
                     readonlybackground=CAMPO, width=26)
        e.insert(0, url)
        e.configure(state="readonly")
        e.pack(pady=(10, 4), ipady=4)
        tk.Label(jan, text=f"PIN:  {pin}", bg=FUNDO, fg=AMARELO, font=("Segoe UI", 22, "bold")).pack(pady=4)
        tk.Label(jan, text="• Lá dá pra assistir, aprovar, baixar pro TikTok, copiar a legenda e agendar no YouTube.\n"
                           "• Se o Windows perguntar sobre o Firewall, marque 'Redes privadas' e clique Permitir.\n"
                           "• Fica ligado enquanto o programa estiver aberto. Funciona só dentro da sua casa (Wi-Fi).",
                 bg=FUNDO, fg=CINZA, font=("Segoe UI", 9), justify="left").pack(pady=(8, 0))

    def _conectar_youtube(self):
        import postagem
        if not postagem.youtube_configurado() and not self._ajuda_youtube():
            return
        perfil = self.v_perfil_gal.get()
        self.lbl_gal.configure(text=f"Abrindo o navegador pra autorizar o canal do perfil '{perfil}'...")

        def rodar():
            try:
                postagem.conectar_youtube(log=lambda t: None, perfil=perfil)
                return f"✅ YouTube conectado ao perfil '{perfil}'!"
            except Exception as e:
                return f"❌ {e}"
        self._em_segundo_plano(rodar, lambda r: (self.lbl_gal.configure(text=r or ""), self._carregar_galeria()))

    def _postar_yt(self, v):
        import postagem
        if not postagem.youtube_configurado() and not self._ajuda_youtube():
            return
        ficha = postagem.ler_ficha(v)
        perfil = ficha.get("perfil") or "Padrão"
        horarios = postagem.horarios_do_perfil(perfil)
        quando = postagem.proximo_horario(horarios, perfil=perfil)
        extra = "" if postagem.youtube_conectado(perfil) else \
            f"\n\n(o perfil '{perfil}' ainda não tem conta conectada — vai abrir o navegador)"
        alerta = "".join("\n\n⚠ " + a for a in self._avisos_revisao(ficha))
        if not messagebox.askyesno("Agendar no YouTube", f"Agendar no canal do perfil '{perfil}' para "
                                   f"{quando:%d/%m às %H:%M}?\n(sobe agora como privado e o YouTube publica "
                                   f"sozinho na hora){extra}{alerta}"):
            return
        self.lbl_gal.configure(text="Enviando pro YouTube...")

        def rodar():
            msgs = []
            try:
                postagem.postar_youtube(v, horarios, perfil=perfil,
                                        log=lambda t: (msgs.append(t), self.fila.put(
                                            ("call", lambda x: self.lbl_gal.configure(text=x), t))))
                return msgs[-1] if msgs else "✅ Enviado"
            except Exception as e:
                return f"❌ Erro ao postar: {str(e)[:200]}"
        self._em_segundo_plano(rodar, lambda r: (self.lbl_gal.configure(text=r or ""), self._carregar_galeria()))

    def _views_manual(self, v):
        from tkinter import simpledialog
        import resultados
        n = simpledialog.askstring("Views do TikTok", "Quantas visualizações esse corte teve no TikTok?\n"
                                   "(pode escrever 12500, 12,5 mil ou 12.5K)", parent=self)
        if not n:
            return
        num = resultados._numero(n.replace("mil", "K").replace(" ", ""))
        if num <= 0:
            return messagebox.showwarning("Views", "Não entendi o número.")
        resultados.views_manual(v, "tiktok", num)
        self._carregar_galeria()

    def _postar_tt(self, v):
        import postagem

        def copiar(t):
            self.clipboard_clear()
            self.clipboard_append(t)
        postagem.ajudar_tiktok(v, copiar)
        messagebox.showinfo("TikTok", "✅ Legenda copiada!\n\nNa página do TikTok que abriu:\n"
                            "1. Arraste o vídeo (a pasta com ele já está aberta)\n"
                            "2. Clique na descrição e aperte Ctrl+V\n3. Publicar")
        self._carregar_galeria()

    def _escolher_pergunta(self, ficha, rapido):
        """Janela do ✏: as perguntas alternativas que a IA já mandou (1 clique) ou uma escrita à mão."""
        alternativas = [q for q in (ficha.get("perguntas_alternativas") or []) if isinstance(q, str) and q.strip()]
        jan = tk.Toplevel(self)
        jan.title("Refazer com outra pergunta")
        jan.configure(bg=CARTAO, padx=16, pady=14)
        jan.transient(self)
        jan.grab_set()
        resultado = {"pergunta": None}
        tk.Label(jan, text="Pergunta atual:", bg=CARTAO, fg=CINZA, font=("Segoe UI", 9)).pack(anchor="w")
        tk.Label(jan, text=ficha.get("pergunta", ""), bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10, "bold"),
                 wraplength=460, justify="left").pack(anchor="w", pady=(0, 10))

        def escolher(texto):
            resultado["pergunta"] = (texto or "").strip() or None
            jan.destroy()
        if alternativas:
            tk.Label(jan, text="Alternativas que a IA já criou (sem gastar IA):", bg=CARTAO, fg=CINZA,
                     font=("Segoe UI", 9)).pack(anchor="w")
            for q in alternativas[:4]:
                ttk.Button(jan, text=q, command=lambda q=q: escolher(q)).pack(fill="x", pady=2)
        tk.Label(jan, text="Ou escreva outra:", bg=CARTAO, fg=CINZA, font=("Segoe UI", 9)).pack(anchor="w",
                                                                                           pady=(10, 0))
        campo = self._campo(jan)
        campo.configure(width=52)
        campo.insert(0, ficha.get("pergunta", ""))
        campo.pack(fill="x", ipady=3, pady=(2, 8))
        campo.bind("<Return>", lambda e: escolher(campo.get()))
        tk.Label(jan, text=("Rápido: reaproveita a edição pronta (não baixa nem usa IA)." if rapido else
                            "Este corte é antigo: vai ser refeito do zero (baixa e usa a IA de novo)."),
                 bg=CARTAO, fg=CINZA, font=("Segoe UI", 9)).pack(anchor="w")
        linha = tk.Frame(jan, bg=CARTAO)
        linha.pack(fill="x", pady=(8, 0))
        ttk.Button(linha, text="Usar a escrita", command=lambda: escolher(campo.get())).pack(side="right")
        ttk.Button(linha, text="Cancelar", command=jan.destroy).pack(side="right", padx=(0, 8))
        self.wait_window(jan)
        return resultado["pergunta"]

    def _refazer(self, v, ficha):
        import projeto_edicao
        rapido = projeto_edicao.pode_trocar_pergunta(v)
        if not rapido and not ficha.get("fonte"):
            return messagebox.showinfo("Refazer", "Esse corte é antigo e não tem os dados pra refazer.")
        nova = self._escolher_pergunta(ficha, rapido)
        if not nova or nova == ficha.get("pergunta"):
            return
        if rapido:
            self.lbl_gal.configure(text="Refazendo só a pergunta... (acompanhe na aba Corte)")

            def trocar():
                sys.stdout = sys.stderr = Saida(lambda t: self._log(self.log_corte, t))
                try:
                    novo = projeto_edicao.trocar_pergunta(v, nova)
                    if novo:
                        for ext in (".mp4", ".json", ".txt", ".srt", ".capa.jpg", ".qualidade.json",
                                    ".transcricao.json"):
                            v.with_suffix(ext).unlink(missing_ok=True)
                    return "✅ Pergunta trocada (sem gastar IA)!"
                except Exception as e:
                    return f"❌ Não consegui trocar a pergunta: {str(e)[:200]}"
            return self._em_segundo_plano(trocar, lambda r: (self.lbl_gal.configure(text=r or ""),
                                                             self._carregar_galeria()))
        fonte = ficha["fonte"]
        if not re.match(r"^https?://", fonte) and not Path(fonte).exists():
            return messagebox.showwarning("Refazer", "O vídeo original não existe mais (a gravação foi apagada).")
        self.lbl_gal.configure(text="Refazendo o corte... (acompanhe na aba Corte)")
        op = dict(ficha.get("opcoes", {}))
        try:                                    # a troca ensina o gosto do dono pra IA
            import ia_aprende
            ia_aprende.registrar_troca_pergunta(ficha.get("perfil"), ficha.get("pergunta"), nova,
                                                da_lista=nova in (ficha.get("perguntas_alternativas") or []))
        except Exception:
            pass

        def rodar():
            sys.stdout = sys.stderr = Saida(lambda t: self._log(self.log_corte, t))
            try:
                novo = cortes.gerar_corte(fonte, ficha["inicio"], ficha["fim"], pergunta=nova,
                                          pasta_saida=v.parent, nota_minima=0, perfil=ficha.get("perfil"),
                                          foto=op.get("foto"), legenda=op.get("legenda", True),
                                          modo=op.get("modo", "cortado"), topo=op.get("topo", "auto"))
                if novo:
                    for ext in (".mp4", ".json", ".txt", ".srt", ".capa.jpg", ".qualidade.json", ".transcricao.json"):
                        v.with_suffix(ext).unlink(missing_ok=True)
                return "✅ Corte refeito!"
            except Exception as e:
                return f"❌ Não consegui refazer: {str(e)[:200]}"
        self._em_segundo_plano(rodar, lambda r: (self.lbl_gal.configure(text=r or ""), self._carregar_galeria()))

    def _descartar(self, v):
        if not messagebox.askyesno("Descartar", "Mover este corte para a pasta _descartados?"):
            return
        destino = PASTA / "cortes_prontos" / "_descartados"
        destino.mkdir(parents=True, exist_ok=True)
        for ext in (".mp4", ".json", ".txt", ".srt", ".capa.jpg", ".qualidade.json", ".transcricao.json"):
            arq = v.with_suffix(ext)
            if arq.exists():
                alvo = destino / arq.name
                if alvo.exists():
                    alvo.unlink()
                arq.replace(alvo)
        self._carregar_galeria()

    def _rolar(self, e):
        alvo = {"galeria": getattr(self, "can_gal", None), "tend": getattr(self, "can_tend", None),
                "contas": getattr(self, "can_contas", None)}.get(self._aba_atual)
        if alvo and not isinstance(e.widget, tk.Text):      # a caixa de mensagens rola sozinha
            alvo.yview_scroll(-e.delta // 120, "units")

    def _lista_rolavel(self, pai, bg=FUNDO):
        corpo = tk.Frame(pai, bg=bg)
        corpo.pack(side="left", fill="both", expand=True)
        can = tk.Canvas(corpo, bg=bg, highlightthickness=0)
        barra = ttk.Scrollbar(corpo, orient="vertical", command=can.yview)
        can.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        can.pack(side="left", fill="both", expand=True)
        interno = tk.Frame(can, bg=bg)
        janela = can.create_window((0, 0), window=interno, anchor="nw")
        interno.bind("<Configure>", lambda e: can.configure(scrollregion=can.bbox("all")))
        can.bind("<Configure>", lambda e: can.itemconfigure(janela, width=e.width))
        return can, interno

    # =========================================================
    # ABA: TENDÊNCIAS (vídeos bombando agora no YouTube)
    # =========================================================
    def _montar_tendencias(self):
        import tendencias
        canais = self._ler_canais()
        topo = tk.Frame(self.aba_tend, bg=CARTAO, padx=12, pady=8)
        topo.pack(fill="x", pady=(8, 6))
        tk.Label(topo, text="Pesquisar:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10, "bold")).pack(side="left")
        self.e_nichos = self._campo(topo)
        self.e_nichos.insert(0, ", ".join(canais.get("tendencias_nichos", tendencias.NICHOS_PADRAO)))
        self.e_nichos.pack(side="left", fill="x", expand=True, padx=6, ipady=3)
        self.v_periodo = tk.StringVar(value={"hoje": "Hoje", "mes": "Mês"}.get(canais.get("tendencias_periodo"), "Semana"))
        ttk.Combobox(topo, textvariable=self.v_periodo, state="readonly", width=8,
                     values=["Hoje", "Semana", "Mês"]).pack(side="left", padx=4)
        self.v_busca_modo = tk.StringVar(value={"canal": "Só nos canais", "descoberta": "Descoberta"}.get(canais.get("tendencias_modo"), "Assunto"))
        cb_modo = ttk.Combobox(topo, textvariable=self.v_busca_modo, state="readonly", width=13,
                               values=["Assunto", "Só nos canais", "Descoberta"])
        cb_modo.pack(side="left", padx=4)
        cb_modo.bind("<<ComboboxSelected>>", lambda e: self._dica_modo_tend())
        self.b_radar = self._botao(topo, "🔎 BUSCAR EM ALTA", self._buscar_radar, cor=VERMELHO, cor_txt="white")
        self.b_radar.pack(side="left", padx=(6, 0))
        self.lbl_modo_tend = tk.Label(self.aba_tend, text="", bg=FUNDO, fg=CINZA, font=("Segoe UI", 8), anchor="w")
        self.lbl_modo_tend.pack(fill="x", padx=12)
        self._dica_modo_tend()

        filtros = tk.Frame(self.aba_tend, bg=CARTAO, padx=12, pady=4)
        filtros.pack(fill="x")
        self.v_dur_min_tend = tk.IntVar(value=int(canais.get("tendencias_filtros", {}).get("duracao_min", 360)//60))
        self.v_dur_max_tend = tk.IntVar(value=int(canais.get("tendencias_filtros", {}).get("duracao_max", 21600)//60))
        self.v_idioma_tend = tk.StringVar(value={"pt":"Português","es":"Espanhol","en":"Inglês"}.get(canais.get("tendencias_filtros", {}).get("idioma"), "Qualquer"))
        tk.Label(filtros, text="Duração em minutos:", bg=CARTAO, fg=TEXTO).pack(side="left")
        tk.Spinbox(filtros, from_=1, to=360, textvariable=self.v_dur_min_tend, width=5).pack(side="left")
        tk.Label(filtros, text="até", bg=CARTAO, fg=TEXTO).pack(side="left", padx=4)
        tk.Spinbox(filtros, from_=1, to=360, textvariable=self.v_dur_max_tend, width=5).pack(side="left")
        ttk.Combobox(filtros, textvariable=self.v_idioma_tend, values=["Qualquer", "Português", "Espanhol", "Inglês"], state="readonly", width=12).pack(side="left", padx=8)
        corpo = tk.Frame(self.aba_tend, bg=FUNDO)
        corpo.pack(fill="both", expand=True)
        lado = tk.Frame(corpo, bg=CARTAO, width=270, padx=10, pady=8)
        lado.pack(side="right", fill="y", padx=(8, 0))
        lado.pack_propagate(False)
        self.can_tend, self.tend_interno = self._lista_rolavel(corpo)
        tk.Label(lado, text="📈 Em alta no Brasil", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 11, "bold"),
                 anchor="w").pack(fill="x")
        self.lst_assuntos = tk.Text(lado, bg=CAMPO, fg=TEXTO, relief="flat", height=12, width=28,
                                    font=("Segoe UI", 9), wrap="word", padx=6, pady=4)
        self.lst_assuntos.pack(fill="x", pady=(4, 8))
        self.v_usar_assuntos = tk.BooleanVar(value=self.cfg.get("usar_assuntos", True))
        ttk.Checkbutton(lado, text="A IA usa esses assuntos nos\ntítulos e hashtags",
                        variable=self.v_usar_assuntos, command=self._salvar_opcoes_tend).pack(anchor="w")
        tk.Frame(lado, bg="#33333C", height=1).pack(fill="x", pady=8)
        tk.Label(lado, text="🤖 No automático", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10, "bold"),
                 anchor="w").pack(fill="x")
        self.v_tend_auto = tk.BooleanVar(value=canais.get("tendencias_auto", False))
        ttk.Checkbutton(lado, text="Cortar sozinho os vídeos\nmais em alta", variable=self.v_tend_auto,
                        command=self._salvar_opcoes_tend).pack(anchor="w", pady=(4, 0))
        lq = tk.Frame(lado, bg=CARTAO)
        lq.pack(fill="x", pady=(4, 0))
        tk.Label(lq, text="por dia:", bg=CARTAO, fg=CINZA, font=("Segoe UI", 9)).pack(side="left")
        self.v_tend_qtd = tk.IntVar(value=canais.get("tendencias_por_dia", 2))
        tk.Spinbox(lq, from_=1, to=10, textvariable=self.v_tend_qtd, width=4, bg=CAMPO, fg=TEXTO,
                   buttonbackground=CAMPO, relief="flat", command=self._salvar_opcoes_tend).pack(side="left", padx=4)
        tk.Label(lado, text="(precisa do monitor ligado)", bg=CARTAO, fg=CINZA, font=("Segoe UI", 8),
                 anchor="w").pack(fill="x")
        self.lbl_tend = tk.Label(self.aba_tend, text="Clique em BUSCAR EM ALTA pra achar os vídeos que estão bombando.",
                                 bg=FUNDO, fg=CINZA, font=("Segoe UI", 9), anchor="w")
        self.lbl_tend.pack(fill="x", side="bottom", pady=(4, 0))
        self._thumbs_tend = {}

    DICAS_MODO_TEND = {
        "Assunto": "Assunto: procura no YouTube inteiro pelos temas digitados (separe por vírgula).",
        "Só nos canais": "Só nos canais: digite os canais separados por vírgula (@nome, link ou nome exato) — "
                         "só aparecem vídeos deles, nada aleatório.",
        "Descoberta": "Descoberta: o que está em alta no Brasil + os temas digitados.",
    }

    def _dica_modo_tend(self):
        self.lbl_modo_tend.configure(text=self.DICAS_MODO_TEND.get(self.v_busca_modo.get(), ""))
        self.b_radar.configure(text="🔎 BUSCAR NOS CANAIS" if self.v_busca_modo.get() == "Só nos canais"
                               else "🔎 BUSCAR EM ALTA")

    @staticmethod
    def parece_canal(termos):
        """Os termos digitados são canais (@nome ou link do canal)?"""
        return bool(termos) and all(t.startswith("@") or "youtube.com/" in t.lower() for t in termos)

    def _salvar_opcoes_tend(self):
        dados = self._ler_canais()
        try:
            dados["tendencias_por_dia"] = int(self.v_tend_qtd.get())
        except (tk.TclError, ValueError):
            pass
        dados["tendencias_auto"] = self.v_tend_auto.get()
        dados["tendencias_nichos"] = [n.strip() for n in self.e_nichos.get().split(",") if n.strip()]
        try:
            minimo, maximo = self.v_dur_min_tend.get()*60, self.v_dur_max_tend.get()*60
            if 5 <= minimo <= maximo <= 21600:
                dados['tendencias_filtros'] = dict(duracao_min=minimo, duracao_max=maximo,
                    idioma={"Português":"pt", "Espanhol":"es", "Inglês":"en"}.get(self.v_idioma_tend.get()))
        except (ValueError, tk.TclError):
            pass
        dados["tendencias_modo"] = {"Só nos canais": "canal", "Descoberta": "descoberta"}.get(self.v_busca_modo.get(), "assunto")
        dados["tendencias_periodo"] = {"Hoje": "hoje", "Mês": "mes"}.get(self.v_periodo.get(), "semana")
        salvar_json(PASTA / "canais.json", dados)
        self.cfg["usar_assuntos"] = self.v_usar_assuntos.get()
        self._salvar_cfg()

    def _mostrar_radar_cache(self):
        import tendencias
        videos, assuntos, quando = tendencias.ultimo_radar()
        self._desenhar_assuntos(assuntos)
        if videos:
            self._desenhar_radar(videos)
            import datetime as _dt
            self.lbl_tend.configure(text=f"Última busca: {_dt.datetime.fromtimestamp(quando):%d/%m %H:%M}. "
                                         "Clique em BUSCAR EM ALTA pra atualizar.")

    def _desenhar_assuntos(self, assuntos):
        self.lst_assuntos.configure(state="normal")
        self.lst_assuntos.delete("1.0", "end")
        for a in assuntos[:20]:
            trafego = f"  {tendencias_fmt(a['trafego'])}+" if a.get("trafego") else ""
            self.lst_assuntos.insert("end", f"• {a['termo']}{trafego}\n")
        if not assuntos:
            self.lst_assuntos.insert("end", "(aparece depois da primeira busca)")
        self.lst_assuntos.configure(state="disabled")

    def _buscar_radar(self):
        import tendencias
        self._salvar_opcoes_tend()
        nichos = [n.strip() for n in self.e_nichos.get().split(",") if n.strip()]
        if self.v_busca_modo.get() != "Só nos canais" and self.parece_canal(nichos):
            self.v_busca_modo.set("Só nos canais")          # digitou @canal ou link: busca só nele
            self._dica_modo_tend()
            self._salvar_opcoes_tend()
        periodo = {"Hoje": "hoje", "Mês": "mes"}.get(self.v_periodo.get(), "semana")
        modo = {"Só nos canais": "canal", "Descoberta": "descoberta"}.get(self.v_busca_modo.get(), "assunto")
        try:
            filtros = dict(duracao_min=self.v_dur_min_tend.get()*60, duracao_max=self.v_dur_max_tend.get()*60,
                           idioma={"Português":"pt", "Espanhol":"es", "Inglês":"en"}.get(self.v_idioma_tend.get()))
            if filtros['duracao_min'] > filtros['duracao_max']: raise ValueError()
        except (ValueError, tk.TclError):
            return messagebox.showerror("Filtros", "Verifique o intervalo de duração.")
        self.b_radar.configure(state="disabled", text="BUSCANDO...")
        self.lbl_tend.configure(text="Procurando... (leva 1 a 2 minutos: olha cada vídeo de perto)")

        def rodar():
            try:
                return tendencias.radar(nichos, periodo, modo=modo, filtros=filtros, log=lambda t: self.fila.put(
                    ("call", lambda x: self.lbl_tend.configure(text=x.strip()), t)))
            except Exception as e:
                self.fila.put(("call", lambda x: self.lbl_tend.configure(text=x), f"❌ {str(e)[:200]}"))
                return None

        def fim(videos):
            self.b_radar.configure(state="normal")
            self._dica_modo_tend()
            _, assuntos, _ = tendencias.ultimo_radar()
            self._desenhar_assuntos(assuntos)
            if videos is not None:
                self._desenhar_radar(videos)
                self.lbl_tend.configure(text=f"✅ {len(videos)} vídeos em alta — do mais quente pro menos quente.")
        self._em_segundo_plano(rodar, fim)

    def _desenhar_radar(self, videos):
        import tendencias
        for w in self.tend_interno.winfo_children():
            w.destroy()
        if not videos:
            tk.Label(self.tend_interno, text=("Nenhum vídeo desses canais no período. Tente 'Mês' ou aumente a duração máxima."
                      if self.v_busca_modo.get() == "Só nos canais" else "Nada encontrado. Tente outros nichos."), bg=FUNDO, fg=CINZA,
                     font=("Segoe UI", 11)).pack(pady=40)
            return
        self._labels_thumb = {}
        for i, v in enumerate(videos[:30]):
            card = tk.Frame(self.tend_interno, bg=CARTAO, padx=8, pady=7)
            card.pack(fill="x", padx=4, pady=3)
            lt = tk.Label(card, bg="#000", width=20, height=5)
            lt.pack(side="left")
            self._labels_thumb[v["id"]] = lt
            info = tk.Frame(card, bg=CARTAO)
            info.pack(side="left", fill="both", expand=True, padx=(10, 0))
            topo = tk.Frame(info, bg=CARTAO)
            topo.pack(fill="x")
            tk.Label(topo, text=f"#{i + 1}", bg=CARTAO, fg=AMARELO, font=("Segoe UI", 12, "bold")).pack(side="left")
            tk.Label(topo, text=v["titulo"], bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10, "bold"), anchor="w",
                     wraplength=380, justify="left").pack(side="left", fill="x", padx=(6, 0))
            dur = v.get("duracao") or 0
            partes = [v.get("canal", ""), f"👁 {tendencias.formatar(v.get('views') or 0)}"]
            if v.get("horas"):
                h = v["horas"]
                partes.append(f"há {int(h)}h" if h < 48 else f"há {int(h // 24)} dias")
            if dur:
                partes.append(f"{dur // 3600}h{dur % 3600 // 60:02d}" if dur >= 3600 else f"{dur // 60} min")
            tk.Label(info, text="  ·  ".join(p for p in partes if p), bg=CARTAO, fg=CINZA,
                     font=("Segoe UI", 9), anchor="w").pack(fill="x")
            tk.Label(info, text="   ".join(v.get("motivos", [])), bg=CARTAO, fg=VERDE if v["nota"] > 40 else AMARELO,
                     font=("Segoe UI", 9, "bold"), anchor="w", wraplength=400, justify="left").pack(fill="x", pady=(2, 4))
            bts = tk.Frame(info, bg=CARTAO)
            bts.pack(fill="x")
            for txt, fn, cor in [("✂ Cortar melhores momentos", lambda v=v: self._cortar_tendencia(v), VERMELHO),
                                 ("▶ Abrir", lambda v=v: __import__("webbrowser").open(v["url"]), "#34343E"),
                                 ("📋 Link", lambda v=v: (self.clipboard_clear(), self.clipboard_append(v["url"])), "#34343E")]:
                b = self._botao(bts, txt, fn, cor=cor, cor_txt="white")
                b.configure(padx=8, pady=3)
                b.pack(side="left", padx=(0, 5))
        self._baixar_thumbs(videos[:30])

    def _baixar_thumbs(self, videos):
        import tempfile
        import urllib.request
        pasta = Path(tempfile.gettempdir()) / "cortes_thumbs"
        pasta.mkdir(exist_ok=True)

        def baixar():
            prontos = {}
            for v in videos:
                arq = pasta / f"{v['id']}.jpg"
                if not arq.exists():
                    try:
                        req = urllib.request.Request(v["thumb"], headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=10) as r:
                            arq.write_bytes(r.read())
                    except Exception:
                        continue
                prontos[v["id"]] = arq
            return prontos

        def mostrar(prontos):
            try:
                from PIL import Image, ImageTk
            except ImportError:
                return
            for vid, arq in (prontos or {}).items():
                lt = getattr(self, "_labels_thumb", {}).get(vid)
                if not lt or not lt.winfo_exists():
                    continue
                try:
                    foto = ImageTk.PhotoImage(Image.open(arq).convert("RGB").resize((160, 90)))
                except Exception:
                    continue
                self._thumbs_tend[vid] = foto
                lt.configure(image=foto, width=160, height=90)
        self._em_segundo_plano(baixar, mostrar)

    def _cortar_tendencia(self, v):
        self.e_link.delete(0, "end")
        self.e_link.insert(0, v["url"])
        self.v_achar.set(True)
        self._modo_achar()
        nb = [w for w in self.winfo_children() if w.winfo_class() == "TNotebook"][0]
        nb.select(self.aba_corte)
        self._gerar()

    # =========================================================
    # ABA: RESULTADOS (números + o que funciona no seu canal)
    # =========================================================
    def _montar_resultados(self):
        r = self.aba_result
        cards = tk.Frame(r, bg=FUNDO)
        cards.pack(fill="x", pady=(8, 6))
        self.res_cards = {}
        for i, (chave, titulo) in enumerate([("cortes", "Cortes feitos"), ("postados", "Postados"),
                                             ("views", "Views no total"), ("views30", "Views em 30 dias"),
                                             ("inscritos", "Inscritos (YouTube)")]):
            c = tk.Frame(cards, bg=CARTAO, padx=12, pady=8)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))
            cards.grid_columnconfigure(i, weight=1)
            tk.Label(c, text=titulo, bg=CARTAO, fg=CINZA, font=("Segoe UI", 9), anchor="w").pack(fill="x")
            lbl = tk.Label(c, text="—", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 18, "bold"), anchor="w")
            lbl.pack(fill="x")
            self.res_cards[chave] = lbl

        meio = tk.Frame(r, bg=FUNDO)
        meio.pack(fill="both", expand=True)
        esq = tk.Frame(meio, bg=CARTAO, padx=12, pady=8)
        esq.pack(side="left", fill="both", expand=True)
        dir_ = tk.Frame(meio, bg=CARTAO, padx=12, pady=8, width=330)
        dir_.pack(side="left", fill="y", padx=(6, 0))
        dir_.pack_propagate(False)

        tk.Label(esq, text="Views por dia (últimos 14 dias, pela data de postagem)", bg=CARTAO, fg=TEXTO,
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
        self.grafico = tk.Canvas(esq, bg=CARTAO, height=150, highlightthickness=0)
        self.grafico.pack(fill="x", pady=(4, 6))
        self.grafico.bind("<Configure>", lambda e: self._desenhar_grafico())
        tk.Label(esq, text="🧠 O que funciona no seu canal", bg=CARTAO, fg=TEXTO,
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
        self.txt_aprend = tk.Text(esq, bg=CAMPO, fg=TEXTO, relief="flat", height=6, font=("Segoe UI", 9),
                                  wrap="word", padx=8, pady=6)
        self.txt_aprend.pack(fill="both", expand=True, pady=(4, 4))
        self.v_usar_aprend = tk.BooleanVar(value=self.cfg.get("usar_aprendizado", True))
        ttk.Checkbutton(esq, text="A IA usa esse aprendizado nas próximas perguntas e títulos",
                        variable=self.v_usar_aprend, command=self._salvar_opcao_aprend).pack(anchor="w")

        tk.Label(dir_, text="🎯 Monetização do TikTok", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10, "bold"),
                 anchor="w").pack(fill="x")
        lf = tk.Frame(dir_, bg=CARTAO)
        lf.pack(fill="x", pady=(4, 0))
        tk.Label(lf, text="Seus seguidores:", bg=CARTAO, fg=CINZA, font=("Segoe UI", 9)).pack(side="left")
        self.e_seguidores = self._campo(lf)
        self.e_seguidores.configure(width=9)
        self.e_seguidores.insert(0, str(self.cfg.get("tiktok_seguidores", 0)))
        self.e_seguidores.pack(side="left", padx=6)
        self.e_seguidores.bind("<FocusOut>", lambda e: self._carregar_resultados())
        self.barra_seg = ttk.Progressbar(dir_, maximum=10000, style="Horizontal.TProgressbar")
        self.barra_seg.pack(fill="x", pady=(4, 0))
        self.lbl_seg = tk.Label(dir_, text="", bg=CARTAO, fg=CINZA, font=("Segoe UI", 8), anchor="w")
        self.lbl_seg.pack(fill="x")
        self.barra_v30 = ttk.Progressbar(dir_, maximum=100000, style="Horizontal.TProgressbar")
        self.barra_v30.pack(fill="x", pady=(4, 0))
        self.lbl_v30 = tk.Label(dir_, text="", bg=CARTAO, fg=CINZA, font=("Segoe UI", 8), anchor="w")
        self.lbl_v30.pack(fill="x")
        tk.Label(dir_, text="🏆 Top cortes", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10, "bold"),
                 anchor="w").pack(fill="x", pady=(10, 0))
        self.txt_top = tk.Text(dir_, bg=CAMPO, fg=TEXTO, relief="flat", height=6, font=("Segoe UI", 9),
                               wrap="word", padx=6, pady=4)
        self.txt_top.pack(fill="x", pady=(4, 0))
        tk.Label(dir_, text="📺 Por canal de origem", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10, "bold"),
                 anchor="w").pack(fill="x", pady=(8, 0))
        self.txt_canais_res = tk.Text(dir_, bg=CAMPO, fg=TEXTO, relief="flat", height=4, font=("Segoe UI", 9),
                                      wrap="word", padx=6, pady=4)
        self.txt_canais_res.pack(fill="both", expand=True, pady=(4, 0))

        bts = tk.Frame(r, bg=FUNDO)
        bts.pack(fill="x", pady=(6, 0))
        self._botao(bts, "⟳ Atualizar números do YouTube", self._atualizar_youtube_res, cor=VERMELHO,
                    cor_txt="white").pack(side="left")
        self._botao(bts, "📥 Importar relatório do TikTok", self._importar_tiktok).pack(side="left", padx=6)
        self._botao(bts, "🎬 Gerar compilação da semana", self._gerar_compilacao).pack(side="left")
        self._botao(bts, "🎬 Compilação de um canal", lambda: self._gerar_compilacao(por_canal=True)).pack(
            side="left", padx=6)
        self.lbl_res = tk.Label(bts, text="", bg=FUNDO, fg=CINZA, font=("Segoe UI", 9), anchor="w")
        self.lbl_res.pack(side="left", padx=10, fill="x", expand=True)
        self._dados_res = None

    def _salvar_opcao_aprend(self):
        self.cfg["usar_aprendizado"] = self.v_usar_aprend.get()
        self._salvar_cfg()

    def _carregar_resultados(self):
        import resultados
        try:
            seg = int(re.sub(r"\D", "", self.e_seguidores.get()) or 0)
        except ValueError:
            seg = 0
        if seg != self.cfg.get("tiktok_seguidores"):
            self.cfg["tiktok_seguidores"] = seg
            self._salvar_cfg()
        d = resultados.resumo()
        self._dados_res = d
        insc = sum(c.get("inscritos", 0) for c in d["canais_youtube"].values())
        for chave, valor in [("cortes", d["cortes"]), ("postados", d["postados"]), ("views", d["views"]),
                             ("views30", d["views30"]), ("inscritos", insc)]:
            self.res_cards[chave].configure(text=tendencias_fmt(valor) if valor else ("0" if chave != "inscritos" else "—"))
        self.barra_seg["value"] = min(10000, seg)
        self.lbl_seg.configure(text=f"{tendencias_fmt(seg)} de 10 mil seguidores" + ("  ✅" if seg >= 10000 else ""))
        tt = d["tiktok_views30"]
        self.barra_v30["value"] = min(100000, tt)
        self.lbl_v30.configure(text=f"{tendencias_fmt(tt)} de 100 mil views no TikTok (30 dias)" + ("  ✅" if tt >= 100000 else ""))
        self.txt_top.configure(state="normal")
        self.txt_top.delete("1.0", "end")
        for i, (m, f, v) in enumerate(d["top"][:6], 1):
            self.txt_top.insert("end", f"{i}. 👁 {tendencias_fmt(v)} — {f.get('titulo', m.stem)[:50]}\n")
        if not d["top"]:
            self.txt_top.insert("end", "Ainda sem números. Poste e clique em 'Atualizar números'.")
        self.txt_top.configure(state="disabled")
        self.txt_canais_res.configure(state="normal")
        self.txt_canais_res.delete("1.0", "end")
        for c, info in d["por_canal"]:
            self.txt_canais_res.insert("end", f"• {c}: {info['cortes']} corte(s), 👁 {tendencias_fmt(info['views'])}\n")
        self.txt_canais_res.configure(state="disabled")
        a = resultados.gerar_aprendizado()
        self.txt_aprend.configure(state="normal")
        self.txt_aprend.delete("1.0", "end")
        for plataforma,dados in a.get('por_plataforma',{'youtube':a}).items():
            self.txt_aprend.insert('end',f"[{plataforma.upper()}] {dados.get('cortes_com_numeros',0)} medições comparáveis.\n")
            for linha in dados.get('linhas',[]):self.txt_aprend.insert('end','• '+linha+'\n')
            if dados.get('bons'):self.txt_aprend.insert('end','• Exemplos observados: '+' | '.join(dados['bons'][:3])+'\n')
            if not dados.get('linhas'):self.txt_aprend.insert('end','Ainda sem evidência suficiente: mínimo de 5 vídeos medidos por grupo (o robô mede sozinho a cada 3h com o YouTube conectado).\n')
        try:                                            # horário inteligente, por perfil
            import postagem
            for perfil in cortes.nomes_perfis():
                rk = resultados.melhores_horarios(perfil)
                if rk:
                    top = ", ".join(f"{h:02d}h (índice {m:.2f}x)" for h, m, _ in rk[:3])
                    ligado = cortes.carregar_config(perfil).get("horario_inteligente")
                    agenda = ", ".join(postagem.horarios_do_perfil(perfil)) if ligado else "desligado"
                    self.txt_aprend.insert("end", f"• ⏰ {perfil}: melhores horas {top} — agenda: {agenda}\n")
        except Exception:
            pass
        for r in d["ab"]:
            ganhou = f" → venceu: {r['vencedora']}" if r.get("vencedora") else " (ainda sem vencedor)"
            self.txt_aprend.insert("end", f"• A/B [{r.get('plataforma','youtube')}]: '{r['a']}' {tendencias_fmt(r['views_a'])} x "
                                          f"'{r['b']}' {tendencias_fmt(r['views_b'])}{ganhou}\n")
        self.txt_aprend.configure(state="disabled")
        self._desenhar_grafico()

    def _desenhar_grafico(self):
        c = self.grafico
        c.delete("all")
        d = self._dados_res
        if not d:
            return
        w, h = max(200, c.winfo_width()), int(c.cget("height"))
        dias = list(d["por_dia"].items())
        maximo = max([v for _, v in dias] + [1])
        larg = (w - 20) / len(dias)
        for i, (dia, v) in enumerate(dias):
            x0 = 10 + i * larg + 3
            alt = (h - 34) * v / maximo
            c.create_rectangle(x0, h - 20 - alt, x0 + larg - 6, h - 20, fill=VERMELHO if v else "#3A3A44",
                               outline="")
            if v:
                c.create_text(x0 + (larg - 6) / 2, h - 26 - alt, text=tendencias_fmt(v), fill=TEXTO,
                              font=("Segoe UI", 7))
            c.create_text(x0 + (larg - 6) / 2, h - 8, text=dia[8:10] + "/" + dia[5:7], fill=CINZA,
                          font=("Segoe UI", 7))

    def _atualizar_youtube_res(self):
        import postagem
        import resultados
        if not postagem.perfis_conectados():
            return messagebox.showinfo("YouTube", "Conecte o YouTube primeiro (aba Galeria → Conectar YouTube).")
        self.lbl_res.configure(text="Buscando os números no YouTube...")

        def rodar():
            msgs = []
            try:
                resultados.atualizar_youtube(log=lambda t: msgs.append(t))
            except Exception as e:
                msgs.append(f"❌ {str(e)[:200]}")
            return " ".join(m for m in msgs if m.strip())[-300:]
        self._em_segundo_plano(rodar, lambda r: (self.lbl_res.configure(text=r or ""), self._carregar_resultados()))

    def _importar_tiktok(self):
        import resultados
        messagebox.showinfo("Relatório do TikTok", "No computador, abra o TikTok Studio → Análises → "
                            "Conteúdo e clique em 'Baixar dados' (CSV ou Excel).\nDepois escolha o arquivo.")
        f = filedialog.askopenfilename(title="Relatório do TikTok", filetypes=[("Planilha", "*.csv *.xlsx"), ("Todos", "*.*")])
        if not f:
            return
        msgs = []
        try:
            resultados.importar_tiktok(f, log=msgs.append)
        except Exception as e:
            msgs.append(f"❌ Não consegui ler o arquivo: {str(e)[:150]}")
        self.lbl_res.configure(text=" ".join(msgs))
        self._carregar_resultados()

    def _gerar_compilacao(self, por_canal=False):
        import compilacao
        from tkinter import simpledialog
        canal = None
        if por_canal:
            canais = sorted({f.get("canal") for _, f in __import__("resultados").fichas() if f.get("canal")})
            canal = simpledialog.askstring("Compilação de um canal", "De qual canal/streamer?\n\n"
                                           + ", ".join(canais[:20]), parent=self)
            if not canal or not canal.strip():
                return
            canal = canal.strip()
        minutos = cortes.carregar_config().get("compilacao_minutos", 8)
        if not messagebox.askyesno("Compilação", f"Montar a compilação {'de ' + canal if canal else 'da semana'} "
                                   f"(horizontal, uns {minutos} min, pro YouTube normal)?\n\nUsa o trecho original "
                                   "deitado quando consegue. Leva alguns minutos."):
            return
        self.lbl_res.configure(text="Montando a compilação...")

        def rodar():
            msgs = []
            try:
                saida = compilacao.gerar_compilacao(log=msgs.append, canal=canal)
            except Exception as e:
                return f"❌ {str(e)[:200]}"
            return msgs[-1] if msgs else ("✅ pronto" if saida else "")
        self._em_segundo_plano(rodar, lambda r: self.lbl_res.configure(text=r or ""))

    # =========================================================
    # ABA: AUTOMÁTICO
    # =========================================================
    def _montar_auto(self):
        esq = self._cartao(self.aba_auto, side="left", fill="both", expand=True, padx=(0, 8), pady=8)
        dir_ = tk.Frame(self.aba_auto, bg=FUNDO, width=380)
        dir_.pack(side="left", fill="both", pady=8)
        dir_.pack_propagate(False)

        canais = self._ler_canais()
        grade = tk.Frame(esq, bg=CARTAO)
        grade.pack(fill="x")

        def caixa(col, linha, titulo, dica, valores):
            f = tk.Frame(grade, bg=CARTAO)
            f.grid(row=linha, column=col, sticky="nsew", padx=(0, 10) if col == 0 else 0, pady=(0, 4))
            grade.grid_columnconfigure(col, weight=1)
            tk.Label(f, text=titulo, bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
            tk.Label(f, text=dica, bg=CARTAO, fg=CINZA, font=("Segoe UI", 8), anchor="w").pack(fill="x")
            t = tk.Text(f, height=2, width=20, bg=CAMPO, fg=TEXTO, insertbackground=TEXTO,
                        relief="flat", font=("Segoe UI", 10))
            t.pack(fill="x", pady=(2, 0))
            t.insert("1.0", "\n".join(valores))
            return t

        self.t_twitch = caixa(0, 0, "Twitch (ao vivo)", "nome por linha (gaules:alta = mais sensível)",
                              [c for c in canais.get("twitch", []) if "nome_do_canal" not in c])
        self.t_kick = caixa(0, 1, "Kick (ao vivo)", "só o nome, um por linha", canais.get("kick", []))
        self.t_yt = caixa(1, 0, "YouTube (vídeos novos)", "link do canal, ex: youtube.com/@canal",
                          [c for c in canais.get("youtube", []) if "NomeDoCanal" not in c])
        self.t_ytlive = caixa(1, 1, "YouTube (lives)", "link do canal — grava quando entrar ao vivo",
                              canais.get("youtube_lives", []))

        nums = tk.Frame(esq, bg=CARTAO)
        nums.pack(fill="x", pady=(6, 0))
        self.v_dur = tk.IntVar(value=canais.get("duracao_corte_seg", 65))
        self.v_nyt = tk.IntVar(value=canais.get("cortes_por_video_youtube", 2))
        self.v_nlive = tk.IntVar(value=canais.get("max_cortes_por_live", 6))
        for txt, var, a, b in [("Duração do corte (s)", self.v_dur, 20, 180),
                               ("Cortes por vídeo", self.v_nyt, 1, 6),
                               ("Máx. cortes por live", self.v_nlive, 1, 30)]:
            col = tk.Frame(nums, bg=CARTAO)
            col.pack(side="left", fill="x", expand=True)
            tk.Label(col, text=txt, bg=CARTAO, fg=TEXTO, font=("Segoe UI", 9, "bold")).pack(anchor="w")
            tk.Spinbox(col, from_=a, to=b, textvariable=var, width=7, bg=CAMPO, fg=TEXTO,
                       buttonbackground=CAMPO, relief="flat", font=("Segoe UI", 11),
                       insertbackground=TEXTO).pack(anchor="w", pady=(3, 0))
        chk = tk.Frame(esq, bg=CARTAO)
        chk.pack(fill="x", pady=(6, 0))
        self.v_auto_leg = tk.BooleanVar(value=canais.get("legenda", True))
        self.v_apagar = tk.BooleanVar(value=canais.get("apagar_gravacao_depois", True))
        self.v_ultimo = tk.BooleanVar(value=canais.get("pegar_ultimo_video_ao_iniciar", False))
        ttk.Checkbutton(chk, text="Legenda nos cortes", variable=self.v_auto_leg).pack(anchor="w")
        ttk.Checkbutton(chk, text="Apagar gravação da live depois de cortar (economiza espaço)",
                        variable=self.v_apagar).pack(anchor="w")
        ttk.Checkbutton(chk, text="Ao ligar, já cortar o último vídeo de cada canal do YouTube",
                        variable=self.v_ultimo).pack(anchor="w")
        self.v_clips = tk.BooleanVar(value=canais.get("clips_twitch", True))
        ttk.Checkbutton(chk, text="Cortar também os clips mais vistos do dia (Twitch)",
                        variable=self.v_clips).pack(anchor="w")
        self.v_ext_gravar = tk.BooleanVar(value=canais.get("extensao_gravar_ao_abrir", True))
        ttk.Checkbutton(chk, text="Extensão: começar a gravar quando eu abrir uma live no Chrome",
                        variable=self.v_ext_gravar).pack(anchor="w")
        self.v_comp_auto = tk.BooleanVar(value=canais.get("compilacao_auto", False))
        ttk.Checkbutton(chk, text="🎬 Domingo à noite: compilação TOP 5 da semana (YouTube normal)",
                        variable=self.v_comp_auto).pack(anchor="w")
        lm = tk.Frame(chk, bg=CARTAO)
        lm.pack(fill="x")
        self.v_madrugada = tk.BooleanVar(value=canais.get("modo_madrugada", False))
        ttk.Checkbutton(lm, text="🌙 Cortes automáticos só entre", variable=self.v_madrugada).pack(side="left")
        self.e_mad_ini = self._campo(lm)
        self.e_mad_ini.configure(width=6)
        self.e_mad_ini.insert(0, canais.get("madrugada_inicio", "01:00"))
        self.e_mad_ini.pack(side="left", padx=4)
        tk.Label(lm, text="e", bg=CARTAO, fg=TEXTO).pack(side="left")
        self.e_mad_fim = self._campo(lm)
        self.e_mad_fim.configure(width=6)
        self.e_mad_fim.insert(0, canais.get("madrugada_fim", "07:00"))
        self.e_mad_fim.pack(side="left", padx=4)
        self.v_desligar = tk.BooleanVar(value=canais.get("desligar_pc_ao_terminar", False))
        ttk.Checkbutton(lm, text="e desligar o PC ao terminar", variable=self.v_desligar).pack(side="left", padx=(6, 0))
        lf = tk.Frame(chk, bg=CARTAO)
        lf.pack(fill="x", pady=(4, 0))
        tk.Label(lf, text="Formato do robô:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10)).pack(side="left")
        self.formatos_robo = {"Curto 9:16": "curto", "Longo 16:9": "longo", "Os dois ⭐": "ambos"}
        atual_fmt = cortes.carregar_config().get("formato_corte", "curto")
        self.v_formato_robo = tk.StringVar(value=next((k for k, v in self.formatos_robo.items() if v == atual_fmt),
                                                      "Curto 9:16"))
        ttk.Combobox(lf, textvariable=self.v_formato_robo, state="readonly", width=12,
                     values=list(self.formatos_robo)).pack(side="left", padx=(6, 14))
        lp = lf          # mesma linha (cabe em tela de notebook)
        tk.Label(lp, text="📂 Pasta vigiada:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10)).pack(side="left")
        self.e_vigiada = self._campo(lp)
        self.e_vigiada.insert(0, canais.get("pasta_vigiada", ""))
        self.e_vigiada.pack(side="left", fill="x", expand=True, padx=4, ipady=1)
        b_v = self._botao(lp, "📁", self._escolher_vigiada)
        b_v.configure(padx=6, pady=1)
        b_v.pack(side="left")
        lt = tk.Frame(chk, bg=CARTAO)
        lt.pack(fill="x", pady=(4, 0))
        self.v_tempo_real = tk.BooleanVar(value=canais.get("tempo_real", True))
        ttk.Checkbutton(lt, text="⚡ Live: cortar na hora (termômetro)", variable=self.v_tempo_real).pack(side="left")
        tk.Label(lt, text="Sensibilidade:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10)).pack(side="left", padx=(10, 4))
        self.v_sens = tk.StringVar(value={"baixa": "Baixa", "alta": "Alta"}.get(canais.get("sensibilidade"), "Média"))
        ttk.Combobox(lt, textvariable=self.v_sens, state="readonly", width=7,
                     values=["Baixa", "Média", "Alta"]).pack(side="left")
        tk.Label(lt, text="Nota mín.:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10)).pack(side="left", padx=(10, 4))
        self.v_nota_live = tk.IntVar(value=int(canais.get("nota_minima_live", 6)))
        tk.Spinbox(lt, from_=0, to=9, textvariable=self.v_nota_live, width=3, bg=CAMPO, fg=TEXTO,
                   buttonbackground=CAMPO, relief="flat", insertbackground=TEXTO).pack(side="left")
        lt2 = tk.Frame(chk, bg=CARTAO)
        lt2.pack(fill="x")
        self.v_aprovar = tk.BooleanVar(value=canais.get("tempo_real_aprovar", False))
        ttk.Checkbutton(lt2, text="Pedir minha aprovação na extensão", variable=self.v_aprovar).pack(side="left")
        self.v_mini_auto = tk.BooleanVar(value=canais.get("janelinha_auto", True))
        ttk.Checkbutton(lt2, text="📺 Abrir a live numa janelinha quando entrar ao vivo",
                        variable=self.v_mini_auto).pack(side="left", padx=(10, 0))
        self.v_diag = tk.BooleanVar(value=canais.get("modo_diagnostico", False))
        ttk.Checkbutton(lt2, text="🩺 Modo diagnóstico", variable=self.v_diag).pack(side="left", padx=(10, 4))
        b = self._botao(lt2, "ver", self._ver_diagnostico)
        b.configure(padx=6, pady=1)
        b.pack(side="left")
        bts = tk.Frame(esq, bg=CARTAO)
        bts.pack(fill="x", pady=(8, 2))
        self._botao(bts, "💾 Salvar canais", self._salvar_canais).pack(side="left")
        self.b_monitor = self._botao(bts, "▶ LIGAR MONITOR", self._alternar_monitor,
                                     cor=VERMELHO, cor_txt="white", grande=True)
        self.b_monitor.pack(side="right")
        # mesma linha do Salvar (cabe em tela de notebook 1366x768)
        self._botao(bts, "📺 Janelinha da live", self._abrir_mini).pack(side="left", padx=(6, 0))
        self._botao(bts, "🖥 Painel 4 lives", self._abrir_painel).pack(side="left", padx=(6, 0))
        self._botao(bts, "🧩 Extensão", self._ajuda_extensao).pack(side="left", padx=(6, 0))

        self.lbl_mon = tk.Label(dir_, text="● Monitor desligado", bg=FUNDO, fg=CINZA,
                                font=("Segoe UI", 10, "bold"), anchor="w")
        self.lbl_mon.pack(fill="x", pady=(0, 4))
        rod = tk.Frame(dir_, bg=FUNDO)
        rod.pack(fill="x", side="bottom", pady=(8, 0))
        self._botao(rod, "📁 Pasta dos cortes", self._abrir_pasta).pack(fill="x")
        self.log_auto = self._caixa_log(dir_)
        self.log_auto.pack(fill="both", expand=True)
        self.log_auto.insert("end", "Coloque os canais, salve e ligue o monitor.\n"
                                    "Pode minimizar a janela: ele continua trabalhando.\n")

    def _escolher_vigiada(self):
        d = filedialog.askdirectory(title="Pasta onde você vai colocar os vídeos pra cortar")
        if d:
            self.e_vigiada.delete(0, "end")
            self.e_vigiada.insert(0, d)

    def _ler_canais(self):
        arq = PASTA / "canais.json"
        try:
            return json.loads(arq.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"twitch": [], "youtube": []}

    def _salvar_canais(self, avisar=True):
        dados = self._ler_canais()
        dados["twitch"] = [l.strip().rstrip("/").split("/")[-1] for l in
                           self.t_twitch.get("1.0", "end").splitlines() if l.strip()]
        dados["youtube"] = [l.strip() for l in self.t_yt.get("1.0", "end").splitlines() if l.strip()]
        dados["kick"] = [l.strip().rstrip("/").split("/")[-1] for l in
                         self.t_kick.get("1.0", "end").splitlines() if l.strip()]
        dados["youtube_lives"] = [l.strip() for l in self.t_ytlive.get("1.0", "end").splitlines() if l.strip()]
        dados["clips_twitch"] = self.v_clips.get()
        dados["extensao_gravar_ao_abrir"] = self.v_ext_gravar.get()
        dados["compilacao_auto"] = self.v_comp_auto.get()
        dados["modo_madrugada"] = self.v_madrugada.get()
        dados["desligar_pc_ao_terminar"] = self.v_desligar.get()
        dados["tempo_real"] = self.v_tempo_real.get()
        dados["sensibilidade"] = {"Baixa": "baixa", "Alta": "alta"}.get(self.v_sens.get(), "media")
        dados["tempo_real_aprovar"] = self.v_aprovar.get()
        dados["janelinha_auto"] = self.v_mini_auto.get()
        dados["modo_diagnostico"] = self.v_diag.get()
        dados["pasta_vigiada"] = self.e_vigiada.get().strip().strip('"')
        try:
            dados["nota_minima_live"] = max(0, min(9, int(self.v_nota_live.get())))
        except (tk.TclError, ValueError):
            pass
        base = cortes.carregar_config()
        base["formato_corte"] = self.formatos_robo.get(self.v_formato_robo.get(), "curto")
        cortes.salvar_config(base)
        self.cfg["formato_corte"] = base["formato_corte"]
        for chave, campo in (("madrugada_inicio", self.e_mad_ini), ("madrugada_fim", self.e_mad_fim)):
            if re.fullmatch(r"\d{1,2}:\d{2}", campo.get().strip()):
                dados[chave] = campo.get().strip().zfill(5)
        try:
            dados["duracao_corte_seg"] = int(self.v_dur.get())
            dados["cortes_por_video_youtube"] = int(self.v_nyt.get())
            dados["max_cortes_por_live"] = int(self.v_nlive.get())
        except (tk.TclError, ValueError):
            messagebox.showwarning("Número inválido", "Confira os números (duração e quantidades).")
            return False
        dados["legenda"] = self.v_auto_leg.get()
        dados["apagar_gravacao_depois"] = self.v_apagar.get()
        dados["pegar_ultimo_video_ao_iniciar"] = self.v_ultimo.get()
        salvar_json(PASTA / "canais.json", dados)
        if avisar:
            self._log(self.log_auto, "✅ Canais salvos.")
        return True

    def _alternar_monitor(self):
        if self.monitor_proc and self.monitor_proc.poll() is None:
            if (PASTA / "parar.flag").exists():           # já pediu pra parar: força
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.monitor_proc.pid)],
                               creationflags=cortes.SEM_JANELA, capture_output=True)
                self._log(self.log_auto, "Monitor encerrado à força.")
                return
            (PASTA / "parar.flag").write_text("1")
            self._log(self.log_auto, "Parando... (se estiver gerando um corte, espera ele terminar)")
            self.b_monitor.configure(text="■ FORÇAR PARADA")
            return
        if not self._salvar_canais(avisar=False):
            return
        dados = self._ler_canais()
        if not any(dados.get(k) for k in ("twitch", "youtube", "kick", "youtube_lives")):
            if not messagebox.askyesno("Sem canais", "Nenhum canal na lista. Ligar mesmo assim?\n"
                                       "(o painel e o botão CORTAR da extensão vão funcionar, "
                                       "mas nada será cortado sozinho)"):
                return
        if contas.faltando_bibliotecas() or not contas.tem_ffmpeg():
            return messagebox.showwarning("Falta instalar", "Vá na aba 'Contas & IA' e instale o que falta.")
        self._salvar_cfg()
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        self.monitor_proc = subprocess.Popen(
            [contas.python_console(), "-u", str(PASTA / "monitor.py")], cwd=str(PASTA),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", env=env, creationflags=cortes.SEM_JANELA)
        self.b_monitor.configure(text="■ DESLIGAR MONITOR", bg="#555")
        self.lbl_mon.configure(text="● Monitor LIGADO", fg=VERDE)

        def ler():
            for linha in self.monitor_proc.stdout:
                self._log(self.log_auto, linha.rstrip())
                if "está AO VIVO" in linha:          # a opção é lida na thread da janela
                    self.fila.put(("call", lambda _x: self.v_mini_auto.get() and self._abrir_mini(sozinho=True), None))
            return None
        self._em_segundo_plano(ler, self._monitor_parou)

    def _ver_diagnostico(self):
        import detector
        pasta = PASTA / "diagnostico"
        arquivos = sorted(pasta.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True) if pasta.exists() else []
        if not arquivos:
            return messagebox.showinfo("Diagnóstico", "Ainda não tem diagnóstico.\n\nMarque '🩺 Modo diagnóstico', "
                                       "ligue o monitor e deixe uma live rodando uns 30 minutos. Cada pico fica "
                                       "anotado na pasta 'diagnostico' (é esse arquivo que você me manda pra calibrar).")
        textos = []
        for f in arquivos[:3]:
            try:
                textos.append(f"📄 {f.name}\n{detector.resumo_diagnostico(f)}")
            except Exception as e:
                textos.append(f"📄 {f.name}: não consegui ler ({e})")
        messagebox.showinfo("Diagnóstico das lives", "\n\n".join(textos)[:2500])
        self._abrir(pasta)

    @staticmethod
    def navegador_app():
        """Edge ou Chrome (abrem a página como janela de aplicativo, sem abas nem barra)."""
        import shutil
        nomes = [shutil.which("msedge"), shutil.which("chrome")]
        for base in (os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", ""),
                     os.environ.get("LOCALAPPDATA", "")):
            if base:
                nomes += [os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                          os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")]
        return next((n for n in nomes if n and os.path.exists(n)), None)

    def _abrir_mini(self, sozinho=False):
        """Abre a live (a que o robô está gravando) numa janela pequena no canto direito da tela."""
        if not (self.monitor_proc and self.monitor_proc.poll() is None):
            if not sozinho:
                messagebox.showinfo("Robô desligado", "Ligue o monitor primeiro (botão LIGAR MONITOR). "
                                    "A janelinha mostra a live que ele estiver gravando.")
            return
        if sozinho and time.time() - getattr(self, "_mini_aberta_em", 0) < 120:
            return                                   # já abriu agora há pouco (outro canal entrou junto)
        self._mini_aberta_em = time.time()
        url = "http://localhost:8765/mini"
        larg, alt = 480, 360
        x = max(0, self.winfo_screenwidth() - larg - 10)
        y = max(0, self.winfo_screenheight() - alt - 60)
        exe = self.navegador_app()
        if exe:
            subprocess.Popen([exe, f"--app={url}", f"--window-size={larg},{alt}", f"--window-position={x},{y}"],
                             creationflags=cortes.SEM_JANELA)
        else:
            import webbrowser
            webbrowser.open(url)
        self._log(self.log_auto, "📺 Janelinha da live aberta (pode arrastar pra onde quiser).")

    def _abrir_painel(self):
        if not (self.monitor_proc and self.monitor_proc.poll() is None):
            messagebox.showinfo("Monitor desligado", "Ligue o monitor primeiro (botão LIGAR MONITOR).")
            return
        import webbrowser
        webbrowser.open("http://localhost:8765")

    def _ajuda_extensao(self):
        messagebox.showinfo("Extensão do Chrome", "Instalar (uma vez):\n"
                            "1. No Chrome, abra:  chrome://extensions\n"
                            "2. Ligue o 'Modo do desenvolvedor' (canto de cima, à direita)\n"
                            "3. Clique em 'Carregar sem compactação' e escolha a pasta\n"
                            "    'extensao_chrome' (vou abrir ela agora)\n"
                            "   (já tinha instalado? clique no ↻ dela pra atualizar)\n\n"
                            "Com o monitor ligado, abra uma live na Twitch ou na Kick:\n"
                            "• ela já começa a gravar sozinha\n"
                            "• quando o chat explodir, o painel pisca: '🔥 CORTAR?'\n"
                            "• ✂ CORTAR (Alt+C) com 30s / 60s / 90s, ou ⏱ marcar (Alt+M) o começo\n"
                            "• depois de cortar, escreva o que aconteceu (opcional) — a IA usa\n"
                            "• o Chrome avisa quando o corte fica pronto\n\n"
                            "No YouTube: ⏱ Início, ⏱ Fim e ✂ GERAR (Alt+I, Alt+F, Alt+G), e a aba\n"
                            "Momentos mostra os trechos mais revistos e os minutos citados nos comentários.\n"
                            "🤖 ACHAR E CORTAR SOZINHA: a IA escolhe os melhores momentos e manda gerar.\n\n"
                            "🤖 Aba Bot: pergunte 'vale cortar agora?', peça título ou os melhores\n"
                            "momentos. Usa a IA de Contas & IA (sem IA, responde com os números do chat).\n"
                            "Clique no ícone da extensão pra ver as lives, os cortes prontos e as opções.")
        self._abrir(PASTA / "extensao_chrome")

    def _monitor_parou(self, _):
        (PASTA / "parar.flag").unlink(missing_ok=True)
        self.b_monitor.configure(text="▶ LIGAR MONITOR", bg=VERMELHO)
        self.lbl_mon.configure(text="● Monitor desligado", fg=CINZA)
        self._log(self.log_auto, "Monitor desligado.")

    # =========================================================
    # ABA: VISUAL
    # =========================================================
    def _montar_visual(self):
        esq = self._cartao(self.aba_visual, side="left", fill="both", expand=True, padx=(0, 8), pady=8)
        dir_ = tk.Frame(self.aba_visual, bg=FUNDO)
        dir_.pack(side="left", fill="y", pady=8)
        self.perfil_visual = self.cfg.get("perfil_ativo", "Padrão")
        if self.perfil_visual not in cortes.nomes_perfis():
            self.perfil_visual = "Padrão"
        self.cfg_perfil = cortes.carregar_config(self.perfil_visual)
        cp = self.cfg_perfil
        self._carregando = True

        def rot(pai, txt):
            tk.Label(pai, text=txt, bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10, "bold")).pack(side="left")

        # ---- perfil
        lp = tk.Frame(esq, bg=CARTAO)
        lp.pack(fill="x")
        rot(lp, "Perfil:")
        self.v_perfil = tk.StringVar(value=self.perfil_visual)
        self.cb_perfil = ttk.Combobox(lp, textvariable=self.v_perfil, state="readonly", width=20,
                                      values=cortes.nomes_perfis())
        self.cb_perfil.pack(side="left", padx=6)
        self.cb_perfil.bind("<<ComboboxSelected>>", lambda e: self._trocar_perfil(self.v_perfil.get()))
        for txt, fn in [("＋ Novo", lambda: self._novo_perfil(False)), ("Duplicar", lambda: self._novo_perfil(True)),
                        ("🗑", self._apagar_perfil)]:
            b = self._botao(lp, txt, fn)
            b.configure(padx=8, pady=3)
            b.pack(side="left", padx=(0, 4))
        lc = tk.Frame(esq, bg=CARTAO)
        lc.pack(fill="x", pady=(5, 0))
        tk.Label(lc, text="Canais deste perfil:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 9)).pack(side="left")
        self.e_canais_perfil = self._campo(lc)
        self.e_canais_perfil.pack(side="left", fill="x", expand=True, padx=6, ipady=2)
        self.e_canais_perfil.bind("<KeyRelease>", lambda e: self._mudou_visual())
        self.lbl_canais_perfil = tk.Label(esq, text="", bg=CARTAO, fg=CINZA, font=("Segoe UI", 8), anchor="w")
        self.lbl_canais_perfil.pack(fill="x")
        tk.Frame(esq, bg="#33333C", height=1).pack(fill="x", pady=(4, 2))

        # ---- legenda (3 controles lado a lado)
        grade = tk.Frame(esq, bg=CARTAO)
        grade.pack(fill="x")

        def escala(col, txt, a_, b_, passo=0):
            f = tk.Frame(grade, bg=CARTAO)
            f.grid(row=0, column=col, sticky="ew", padx=(0, 8))
            grade.grid_columnconfigure(col, weight=1)
            topo_e = tk.Frame(f, bg=CARTAO)
            topo_e.pack(fill="x")
            tk.Label(topo_e, text=txt, bg=CARTAO, fg=TEXTO, font=("Segoe UI", 9, "bold"), anchor="w").pack(
                side="left", fill="x", expand=True)
            var = tk.IntVar()
            if passo:                                  # ajuste fino: ▼ desce, ▲ sobe (de 'passo' em 'passo')
                def mexer(d):
                    var.set(max(a_, min(b_, var.get() + d)))
                    self._mudou_visual()
                for sinal, simbolo in ((-1, "▼"), (1, "▲")):
                    tk.Button(topo_e, text=simbolo, command=lambda s=sinal: mexer(s * passo), bg=CAMPO, fg=TEXTO,
                              relief="flat", bd=0, padx=6, font=("Segoe UI", 8), cursor="hand2",
                              activebackground=VERMELHO).pack(side="left", padx=(2, 0))
            tk.Scale(f, from_=a_, to=b_, orient="horizontal", variable=var, bg=CARTAO, fg=TEXTO,
                     troughcolor=CAMPO, highlightthickness=0, activebackground=VERMELHO, sliderrelief="flat",
                     font=("Segoe UI", 8), command=lambda _v: self._mudou_visual()).pack(fill="x")
            return var
        self.v_margem = escala(0, "Posição da legenda (↑)", 10, 1500, passo=10)
        self.v_tam = escala(1, "Tamanho da legenda", 50, 120)
        self.v_pal = escala(2, "Palavras por vez", 1, 5)

        l = tk.Frame(esq, bg=CARTAO)
        l.pack(fill="x", pady=(4, 0))
        rot(l, "Cor da palavra:")
        self.v_cor = tk.StringVar()
        cb = ttk.Combobox(l, textvariable=self.v_cor, state="readonly", width=11, values=list(CORES_LEGENDA))
        cb.pack(side="left", padx=(6, 14))
        cb.bind("<<ComboboxSelected>>", lambda e: self._mudou_visual())
        rot(l, "Cor da faixa:")
        self.v_estilo = tk.StringVar()
        cb2 = ttk.Combobox(l, textvariable=self.v_estilo, state="readonly", width=16,
                           values=list(cortes.ESTILOS_FAIXA))
        cb2.pack(side="left", padx=6)
        cb2.bind("<<ComboboxSelected>>", lambda e: self._mudou_visual())

        lt = tk.Frame(esq, bg=CARTAO)
        lt.pack(fill="x", pady=(6, 0))
        rot(lt, "Template de edição:")
        import templates_edicao
        self.v_template = tk.StringVar()
        cbt = ttk.Combobox(lt, textvariable=self.v_template, state="readonly", width=24,
                           values=templates_edicao.nomes())
        cbt.pack(side="left", padx=(6, 8))
        cbt.bind("<<ComboboxSelected>>", lambda e: self._mudou_visual())
        self.lbl_template = tk.Label(esq, text="", bg=CARTAO, fg=CINZA, font=("Segoe UI", 8), anchor="w",
                                     justify="left", wraplength=430)
        self.lbl_template.pack(fill="x")

        l5 = tk.Frame(esq, bg=CARTAO)
        l5.pack(fill="x", pady=(6, 0))
        rot(l5, "Estilo do corte:")
        self.estilos_corte = {"Com faixa (foto + faixa)": "faixa", "Clean (sem faixa)": "clean"}
        self.v_estilo_corte = tk.StringVar()
        cbe = ttk.Combobox(l5, textvariable=self.v_estilo_corte, state="readonly", width=22,
                           values=list(self.estilos_corte))
        cbe.pack(side="left", padx=(6, 14))
        cbe.bind("<<ComboboxSelected>>", lambda e: self._mudou_visual())
        self.v_texto_gancho = tk.BooleanVar()
        ttk.Checkbutton(l5, text="Pergunta em texto no início",
                        variable=self.v_texto_gancho, command=self._mudou_visual).pack(side="left")
        l4 = tk.Frame(esq, bg=CARTAO)
        l4.pack(fill="x", pady=(6, 0))
        rot(l4, "Formato da faixa:")
        self.formatos = {"Rasgada (papel)": "Rasgada", "Pincelada": "Pincelada",
                         "Fita adesiva": "Fita", "Adesivo": "Adesivo", "Balão de fala": "Balão",
                         "Neon": "Neon", "Plantão (jornal)": "Plantão", "Explosão (HQ)": "Explosão",
                         "Diagonal (esporte)": "Diagonal", "Reta (clássica)": "Reta"}
        self.v_formato = tk.StringVar()
        cb3 = ttk.Combobox(l4, textvariable=self.v_formato, state="readonly", width=15, values=list(self.formatos))
        cb3.pack(side="left", padx=(6, 14))
        cb3.bind("<<ComboboxSelected>>", lambda e: self._mudou_visual())
        b_fx = self._botao(l4, "👁 Ver formatos", self._ver_formatos_faixa)
        b_fx.configure(padx=6, pady=1)
        b_fx.pack(side="left", padx=(0, 10))
        self.v_selo = tk.BooleanVar()
        ttk.Checkbutton(l4, text="Selo com o nome do canal", variable=self.v_selo,
                        command=self._mudou_visual).pack(side="left")

        ef = tk.Frame(esq, bg=CARTAO)
        ef.pack(fill="x", pady=(8, 0))
        tk.Label(ef, text="Efeitos e versões:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.v_rosto, self.v_sil, self.v_gancho = tk.BooleanVar(), tk.BooleanVar(), tk.BooleanVar()
        self.v_ganchoi, self.v_vicios, self.v_audio, self.v_1080 = (tk.BooleanVar() for _ in range(4))
        self.v_ab, self.v_es, self.v_inedito = tk.BooleanVar(), tk.BooleanVar(), tk.BooleanVar()
        self.v_musica = tk.BooleanVar()
        for linha in [[("Seguir o rosto", self.v_rosto), ("Tirar silêncios", self.v_sil),
                       ("Zoom + boom no gancho", self.v_gancho), ("Gancho no 1º segundo", self.v_ganchoi)],
                      [("Tirar é/tipo/né", self.v_vicios), ("Áudio no padrão", self.v_audio),
                       ("Baixar em 1080p", self.v_1080), ("Checar se é inédito", self.v_inedito)],
                      [("Teste A/B (gera versão B com outra pergunta)", self.v_ab),
                       ("Versão em espanhol (2º canal)", self.v_es)],
                      [("Música de fundo (pasta musicas/, abaixa quando falam)", self.v_musica)]]:
            fr = tk.Frame(ef, bg=CARTAO)
            fr.pack(fill="x")
            for txt, var in linha:
                ttk.Checkbutton(fr, text=txt, variable=var, command=self._mudou_visual).pack(side="left", padx=(0, 10))
        self.finais = {"Chamada (cartaz no fim)": "cta", "Loop (emenda no replay)": "loop", "Nada": "nada"}
        self.zonas = {"Todas as plataformas": "todas", "TikTok": "tiktok", "Reels": "reels", "Shorts": "shorts",
                      "Desligada": "nenhuma"}
        self.v_final, self.v_zona = tk.StringVar(), tk.StringVar()
        fz = tk.Frame(ef, bg=CARTAO)
        fz.pack(fill="x", pady=(4, 0))
        for rotulo, var, opcoes, larg in [("Final do corte:", self.v_final, self.finais, 22),
                                          ("Mostrar botões do app:", self.v_zona, self.zonas, 19)]:
            tk.Label(fz, text=rotulo, bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10)).pack(side="left")
            cb = ttk.Combobox(fz, textvariable=var, state="readonly", width=larg, values=list(opcoes))
            cb.pack(side="left", padx=(6, 12))
            cb.bind("<<ComboboxSelected>>", lambda e: self._mudou_visual())

        qf = tk.Frame(esq, bg=CARTAO)
        qf.pack(fill="x", pady=(8, 0))
        tk.Label(qf, text="Qualidade (sem gastar IA):", bg=CARTAO, fg=TEXTO,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        fl = tk.Frame(qf, bg=CARTAO)
        fl.pack(fill="x")
        tk.Label(fl, text="Layout:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10)).pack(side="left")
        self.layouts = {"Automático (detecta)": "auto", "Normal (foto em cima)": "normal",
                        "Podcast (2 pessoas)": "podcast", "Jogo + facecam": "jogo"}
        self.v_layout = tk.StringVar()
        cbl = ttk.Combobox(fl, textvariable=self.v_layout, state="readonly", width=20, values=list(self.layouts))
        cbl.pack(side="left", padx=(6, 12))
        cbl.bind("<<ComboboxSelected>>", lambda e: self._mudou_visual())
        self.v_animada, self.v_emojis, self.v_revisor = tk.BooleanVar(), tk.BooleanVar(), tk.BooleanVar()
        self.v_revia, self.v_serie, self.v_hint = tk.BooleanVar(), tk.BooleanVar(), tk.BooleanVar()
        for txt, var in [("Legenda animada", self.v_animada), ("Emojis na legenda", self.v_emojis)]:
            ttk.Checkbutton(fl, text=txt, variable=var, command=self._mudou_visual).pack(side="left", padx=(0, 10))
        for linha in [[("Revisor automático", self.v_revisor), ("Revisão com IA (+1 imagem)", self.v_revia)],
                      [("Corte em série (parte 1/2 em vídeos longos)", self.v_serie),
                       ("Horário inteligente", self.v_hint)]]:
            fr = tk.Frame(qf, bg=CARTAO)
            fr.pack(fill="x")
            for txt, var in linha:
                ttk.Checkbutton(fr, text=txt, variable=var, command=self._mudou_visual).pack(side="left", padx=(0, 10))

        linha_m = tk.Frame(esq, bg=CARTAO)
        linha_m.pack(fill="x", pady=(8, 0))
        tk.Label(linha_m, text="Seu @:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10)).pack(side="left")
        self.e_marca = self._campo(linha_m)
        self.e_marca.configure(width=15)
        self.e_marca.pack(side="left", padx=(4, 10), ipady=2)
        self.e_marca.bind("<KeyRelease>", lambda e: self._mudou_visual())
        tk.Label(linha_m, text="Nota mín.:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10)).pack(side="left")
        self.v_nota = tk.IntVar()
        tk.Spinbox(linha_m, from_=0, to=9, textvariable=self.v_nota, width=3, bg=CAMPO, fg=TEXTO,
                   buttonbackground=CAMPO, relief="flat", insertbackground=TEXTO,
                   command=self._mudou_visual).pack(side="left", padx=(4, 10))
        tk.Label(linha_m, text="Postar às:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10)).pack(side="left")
        self.e_horarios = self._campo(linha_m)
        self.e_horarios.configure(width=17)
        self.e_horarios.pack(side="left", padx=4, ipady=2)
        self.e_horarios.bind("<KeyRelease>", lambda e: self._mudou_visual())

        rod = tk.Frame(esq, bg=CARTAO)
        rod.pack(fill="x", pady=(8, 0))
        self._botao(rod, "Voltar ao padrão", self._visual_padrao).pack(side="left")
        tk.Label(rod, text="  Tudo é salvo sozinho, no perfil escolhido acima.", bg=CARTAO, fg=CINZA,
                 font=("Segoe UI", 8)).pack(side="left")

        tk.Label(dir_, text="Prévia", bg=FUNDO, fg=CINZA, font=("Segoe UI", 9, "bold")).pack()
        self.previa = tk.Label(dir_, bg=FUNDO)
        self.previa.pack()
        self._preencher_visual()

    def _preencher_visual(self):
        cp = self.cfg_perfil
        self._carregando = True
        self.v_margem.set(cp["legenda_margem"])
        self.v_tam.set(cp["legenda_tamanho"])
        self.v_pal.set(cp["legenda_palavras"])
        self.v_cor.set(next((n for n, h in CORES_LEGENDA.items() if h.upper() == cp["legenda_cor"].upper()), "Amarelo"))
        self.v_estilo.set(cp["faixa_estilo"])
        self.v_formato.set(next((k for k, v in self.formatos.items() if v == cp.get("faixa_formato")), "Rasgada (papel)"))
        self.v_selo.set(cp["mostrar_selo"])
        for var, chave in [(self.v_rosto, "seguir_rosto"), (self.v_sil, "tirar_silencios"),
                           (self.v_gancho, "efeito_gancho"), (self.v_ganchoi, "gancho_inicio"),
                           (self.v_vicios, "tirar_vicios"), (self.v_audio, "audio_padrao"),
                           (self.v_1080, "baixar_1080"), (self.v_ab, "ab_teste"), (self.v_es, "espanhol"),
                           (self.v_inedito, "checar_inedito"), (self.v_animada, "legenda_animada"),
                           (self.v_emojis, "emojis_legenda"), (self.v_revisor, "revisor"),
                           (self.v_revia, "revisao_ia"), (self.v_serie, "serie"),
                           (self.v_hint, "horario_inteligente"), (self.v_musica, "musica_fundo")]:
            var.set(bool(cp.get(chave, cortes.CONFIG_PADRAO.get(chave))))
        self.v_estilo_corte.set(next((k for k, v in self.estilos_corte.items() if v == cp.get("estilo_corte", "faixa")),
                                     "Com faixa (foto + faixa)"))
        self.v_texto_gancho.set(bool(cp.get("texto_gancho", True)))
        self.v_template.set(cp.get("template_edicao") or "Clássico")
        self._descrever_template()
        self.v_final.set(next((k for k, v in self.finais.items() if v == cp.get("final_corte", "cta")),
                              "Chamada (cartaz no fim)"))
        self.v_zona.set(next((k for k, v in self.zonas.items() if v == cp.get("plataforma_alvo", "todas")),
                             "Todas as plataformas"))
        self.v_layout.set(next((k for k, v in self.layouts.items() if v == cp.get("layout", "auto")),
                               "Automático (detecta)"))
        self.e_marca.delete(0, "end")
        self.e_marca.insert(0, cp.get("marca", ""))
        self.v_nota.set(int(float(cp.get("nota_minima", 0) or 0)))
        self.e_horarios.delete(0, "end")
        self.e_horarios.insert(0, ", ".join(cp.get("horarios_postagem", [])))
        padrao = self.perfil_visual == "Padrão"
        self.e_canais_perfil.configure(state="normal")
        self.e_canais_perfil.delete(0, "end")
        self.e_canais_perfil.insert(0, ", ".join(cp.get("canais", [])))
        self.e_canais_perfil.configure(state="disabled" if padrao else "normal")
        self.lbl_canais_perfil.configure(
            text="O Padrão vale pra todo canal que não estiver em outro perfil." if padrao else
            "Cortes desses canais usam este perfil (visual, @, horários e a conta do YouTube dele).")
        self._carregando = False
        cortes.aplicar_config(self.cfg_perfil)
        self._atualizar_previa()

    def _trocar_perfil(self, nome):
        self.perfil_visual = nome
        self.cfg_perfil = cortes.carregar_config(nome)
        self.cfg["perfil_ativo"] = nome
        self._salvar_cfg()
        self._preencher_visual()

    def _novo_perfil(self, duplicar):
        from tkinter import simpledialog
        nome = simpledialog.askstring("Novo perfil", "Nome do perfil (ex: o nome do streamer ou do seu canal):",
                                      parent=self)
        if not nome or not nome.strip():
            return
        nome = nome.strip()[:30]
        if nome in cortes.nomes_perfis():
            return messagebox.showwarning("Perfil", "Já existe um perfil com esse nome.")
        base = dict(self.cfg_perfil) if duplicar else cortes.carregar_config("Padrão")
        base["canais"] = []
        cortes.salvar_perfil(base, nome)
        self.cb_perfil.configure(values=cortes.nomes_perfis())
        self.v_perfil.set(nome)
        self._trocar_perfil(nome)
        self._atualizar_perfis_combo()

    def _apagar_perfil(self):
        nome = self.perfil_visual
        if nome == "Padrão":
            return messagebox.showinfo("Perfil", "O perfil Padrão não pode ser apagado.")
        if not messagebox.askyesno("Apagar perfil", f"Apagar o perfil '{nome}'? (os cortes já feitos ficam)"):
            return
        base = cortes.carregar_config()
        base.get("perfis", {}).pop(nome, None)
        cortes.salvar_config(base)
        self.cfg["perfis"] = base.get("perfis", {})
        self.cb_perfil.configure(values=cortes.nomes_perfis())
        self.v_perfil.set("Padrão")
        self._trocar_perfil("Padrão")
        self._atualizar_perfis_combo()

    def _atualizar_perfis_combo(self):
        for attr in ("cb_perfil_corte", "cb_perfil_gal"):
            cb = getattr(self, attr, None)
            if cb:
                extra = ["Automático (pelo canal)"] if attr == "cb_perfil_corte" else []
                cb.configure(values=extra + cortes.nomes_perfis())

    def _mudou_visual(self):
        if getattr(self, "_carregando", False):
            return
        if hasattr(self, "lbl_template"):
            self._descrever_template()
        try:
            horarios = [h.strip() for h in re.split(r"[,; ]+", self.e_horarios.get())
                        if re.fullmatch(r"\d{1,2}:\d{2}", h.strip())]
            self.cfg_perfil.update(
                legenda_margem=int(self.v_margem.get()), legenda_tamanho=int(self.v_tam.get()),
                legenda_palavras=int(self.v_pal.get()),
                legenda_cor=CORES_LEGENDA.get(self.v_cor.get(), "#FFE600"),
                faixa_estilo=self.v_estilo.get(), mostrar_selo=self.v_selo.get(),
                faixa_formato=self.formatos.get(self.v_formato.get(), "Rasgada"),
                seguir_rosto=self.v_rosto.get(), tirar_silencios=self.v_sil.get(),
                efeito_gancho=self.v_gancho.get(), marca=self.e_marca.get().strip(),
                gancho_inicio=self.v_ganchoi.get(), tirar_vicios=self.v_vicios.get(),
                audio_padrao=self.v_audio.get(), baixar_1080=self.v_1080.get(),
                ab_teste=self.v_ab.get(), espanhol=self.v_es.get(), checar_inedito=self.v_inedito.get(),
                nota_minima=int(self.v_nota.get() or 0),
                layout=self.layouts.get(self.v_layout.get(), "auto"),
                estilo_corte=self.estilos_corte.get(self.v_estilo_corte.get(), "faixa"),
                texto_gancho=self.v_texto_gancho.get(), legenda_animada=self.v_animada.get(),
                template_edicao=self.v_template.get() or "Clássico",
                final_corte=self.finais.get(self.v_final.get(), "cta"),
                plataforma_alvo=self.zonas.get(self.v_zona.get(), "todas"),
                emojis_legenda=self.v_emojis.get(), revisor=self.v_revisor.get(), revisao_ia=self.v_revia.get(),
                serie=self.v_serie.get(), horario_inteligente=self.v_hint.get(), musica_fundo=self.v_musica.get(),
                horarios_postagem=horarios or self.cfg_perfil.get("horarios_postagem", ["12:00", "18:00", "21:00"]))
            if self.perfil_visual != "Padrão":
                self.cfg_perfil["canais"] = [c.strip() for c in self.e_canais_perfil.get().split(",") if c.strip()]
        except tk.TclError:
            return
        cortes.salvar_perfil(self.cfg_perfil, self.perfil_visual)
        if self.perfil_visual == "Padrão":
            self.cfg.update({k: self.cfg_perfil[k] for k in cortes.CHAVES_PERFIL if k in self.cfg_perfil})
        cortes.aplicar_config(self.cfg_perfil)
        if self._previa_job:
            self.after_cancel(self._previa_job)
        self._previa_job = self.after(250, self._atualizar_previa)

    @staticmethod
    def amostras_faixa(pasta, pergunta="ELE FALOU ISSO AO VIVO?", canal="SEU CANAL"):
        """Uma imagem de cada formato de faixa (com as cores do perfil atual). Devolve {formato: arquivo}."""
        import faixas
        saida = {}
        destaque = [pergunta.split()[-1]] if pergunta.split() else []
        for formato, func in list(faixas.FORMATOS_FAIXA.items()) + [("Reta", "faixa_reta_png")]:
            try:
                img = getattr(faixas, func)(pergunta, destaque, canal).convert("RGB")
            except Exception:
                continue
            img.thumbnail((330, 124))
            arq = Path(pasta) / f"faixa_{formato}.png"
            img.save(arq)
            saida[formato] = arq
        return saida

    def _ver_formatos_faixa(self):
        import tempfile
        if not hasattr(self, "_pasta_amostras"):
            self._pasta_amostras = tempfile.mkdtemp(prefix="faixas_")
        janela = tk.Toplevel(self)
        janela.title("Formatos da faixa")
        janela.configure(bg=FUNDO)
        janela.transient(self)
        tk.Label(janela, text="Clique no formato que você quer (as cores seguem o 'Estilo da faixa').",
                 bg=FUNDO, fg=TEXTO, font=("Segoe UI", 10, "bold")).pack(padx=12, pady=(10, 6), anchor="w")
        grade = tk.Frame(janela, bg=FUNDO)
        grade.pack(padx=12, pady=(0, 12))
        tk.Label(grade, text="Gerando as amostras...", bg=FUNDO, fg=CINZA).grid(row=0, column=0)
        nomes = {v: k for k, v in self.formatos.items()}
        atual = self.formatos.get(self.v_formato.get(), "Rasgada")

        def mostrar(amostras):
            if not janela.winfo_exists():
                return
            for w in grade.winfo_children():
                w.destroy()
            janela._imgs = []
            for i, (formato, arq) in enumerate((amostras or {}).items()):
                foto = tk.PhotoImage(file=str(arq))
                janela._imgs.append(foto)
                cel = tk.Frame(grade, bg=VERMELHO if formato == atual else CARTAO, padx=3, pady=3)
                cel.grid(row=i // 3, column=i % 3, padx=5, pady=5)

                def escolher(_e=None, f=formato):
                    self.v_formato.set(nomes.get(f, self.v_formato.get()))
                    self._mudou_visual()
                    janela.destroy()
                tk.Button(cel, image=foto, command=escolher, bg=CARTAO, relief="flat", cursor="hand2",
                          activebackground=CARTAO, bd=0).pack()
                tk.Label(cel, text=nomes.get(formato, formato) + ("  ✔ atual" if formato == atual else ""),
                         bg=cel["bg"], fg=TEXTO, font=("Segoe UI", 9, "bold")).pack(fill="x")
        self._em_segundo_plano(lambda: self.amostras_faixa(self._pasta_amostras), mostrar)

    def _descrever_template(self):
        import templates_edicao
        nome = self.v_template.get() or "Clássico"
        if nome == templates_edicao.AUTOMATICO:
            txt = ("A IA diz o clima do trecho (humor, polêmica, emoção...) na mesma chamada e o programa "
                   "escolhe o template que combina. Zero IA a mais.")
        else:
            txt = templates_edicao.TEMPLATES.get(nome, {}).get("descricao", "")
        self.lbl_template.configure(text=txt)

    def _visual_padrao(self):
        for k in ["legenda_margem", "legenda_tamanho", "legenda_palavras", "legenda_cor",
                  "faixa_estilo", "mostrar_selo", "faixa_formato"]:
            self.cfg_perfil[k] = cortes.CONFIG_PADRAO[k]
        self._preencher_visual()
        self._mudou_visual()

    def _atualizar_previa(self):
        try:
            from PIL import ImageTk
            import previa
        except ImportError:
            self.previa.configure(text="(instale as bibliotecas na aba\nContas & IA pra ver a prévia)",
                                  fg=CINZA, font=("Segoe UI", 9))
            return
        altura = max(300, self.winfo_height() - 170)
        img = previa.gerar_previa(getattr(self, "cfg_perfil", self.cfg), altura)
        self._img_previa = ImageTk.PhotoImage(img)
        self.previa.configure(image=self._img_previa)

    # =========================================================
    # ABA: CONTAS & IA
    # =========================================================
    def _montar_contas(self):
        cartao = self._cartao(self.aba_contas, side="left", fill="both", expand=True, padx=(0, 8), pady=8)
        self.can_contas, esq = self._lista_rolavel(cartao, bg=CARTAO)   # rola com a barra ou a rodinha
        esq.configure(padx=0, pady=0)
        dir_ = tk.Frame(self.aba_contas, bg=FUNDO, width=360)
        dir_.pack(side="left", fill="both", pady=8)
        dir_.pack_propagate(False)
        self.log_contas = self._caixa_log(dir_)
        self.log_contas.pack(fill="both", expand=True)
        self.log_contas.insert("end", "Aqui você instala o que falta e conecta suas contas.\n"
                                      "Tudo usa a sua assinatura — sem chave de API.\n")

        self.status = {}
        topo_inst = tk.Frame(esq, bg=CARTAO)
        topo_inst.pack(fill="x", pady=(2, 2))
        self._botao(topo_inst, "⚡ INSTALAR TUDO QUE FALTA", self._instalar_tudo, cor=VERMELHO,
                    cor_txt="white", grande=True).pack(side="left", fill="x", expand=True)
        self._botao(topo_inst, "🩺 Examinar o PC", lambda: self._acao_conta(contas.examinar_pc),
                    grande=True).pack(side="left", padx=(6, 0))
        ferr = tk.Frame(esq, bg=CARTAO)
        ferr.pack(fill="x", pady=(4, 2))
        self._botao(ferr, "⚡ Testar velocidade", self._testar_velocidade).pack(side="left", fill="x", expand=True)
        self._botao(ferr, "🧹 Espaço em disco", lambda: self._acao_conta(desempenho.limpar)).pack(
            side="left", fill="x", expand=True, padx=(6, 0))
        self.b_fraco = self._botao(ferr, "", self._alternar_pc_fraco)
        self.b_fraco.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self._mostrar_pc_fraco()
        import baixador                 # yt-dlp em dia (a cada 3 dias, em segundo plano)
        threading.Thread(target=baixador.manter_atualizado,
                         kwargs={"log": lambda t: self._log(self.log_contas, t)}, daemon=True).start()

        def linha(titulo, chave, botoes):
            f = tk.Frame(esq, bg=CARTAO)
            f.pack(fill="x", pady=(3, 0))
            topo = tk.Frame(f, bg=CARTAO)
            topo.pack(fill="x")
            tk.Label(topo, text=titulo, bg=CARTAO, fg=TEXTO, font=("Segoe UI", 11, "bold")).pack(side="left")
            st = tk.Label(topo, text="verificando...", bg=CARTAO, fg=CINZA, font=("Segoe UI", 9, "bold"))
            st.pack(side="right")
            self.status[chave] = st
            bf = tk.Frame(f, bg=CARTAO)
            bf.pack(fill="x", pady=(2, 0))
            for txt, func in botoes:
                acao = func if getattr(func, "_direto", False) else (lambda fn=func: self._acao_conta(fn))
                self._botao(bf, txt, acao).pack(side="left", padx=(0, 6))
            tk.Frame(f, bg="#33333C", height=1).pack(fill="x", pady=(4, 0))

        linha("Bibliotecas do Python", "libs", [("Instalar / atualizar", contas.instalar_bibliotecas),
                                                ("Atualizar baixadores", contas.atualizar_baixadores)])
        linha("ffmpeg (monta os vídeos)", "ffmpeg", [("Instalar", contas.instalar_ffmpeg)])
        linha("Claude (assinatura Claude)", "claude", [("Instalar", contas.instalar_claude),
                                                       ("Conectar conta", contas.conectar_claude),
                                                       ("Testar", contas.testar_claude)])
        linha("Codex (conta do ChatGPT)", "codex", [("Instalar", contas.instalar_codex),
                                                    ("Conectar conta", contas.conectar_codex),
                                                    ("Testar", contas.testar_codex)])
        linha("Gemini (grátis: chave API ou conta Google)", "gemini",
              [("🔑 Colar chave da API", self._chave_gemini), ("Testar", contas.testar_gemini),
               ("ou: Instalar CLI", contas.instalar_gemini), ("Conectar conta", contas.conectar_gemini)])
        linha("IA local (grátis, roda no PC)", "local", [("Instalar / baixar modelo", contas.instalar_local),
                                                          ("Ligar", contas.conectar_local),
                                                          ("Testar", contas.testar_local)])
        fm = tk.Frame(esq, bg=CARTAO)
        fm.pack(fill="x", pady=(2, 0))
        tk.Label(fm, text="Modelo da IA local:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 9)).pack(side="left")
        self.modelos_locais = {contas.rotulo_modelo(m): m["id"] for m in contas.MODELOS_LOCAIS}
        atual = self.cfg.get("modelo_local") or cortes.MODELO_LOCAL
        if atual not in self.modelos_locais.values():           # modelo escolhido à mão no config.json
            self.modelos_locais[f"Personalizado — {atual}"] = atual
        self.v_modelo_local = tk.StringVar(value=next(k for k, v in self.modelos_locais.items() if v == atual))
        cbm = ttk.Combobox(fm, textvariable=self.v_modelo_local, state="readonly", width=52,
                           values=list(self.modelos_locais))
        cbm.pack(side="left", padx=(6, 0))
        cbm.bind("<<ComboboxSelected>>", lambda e: self._mudou_modelo_local())
        ram = contas.memoria_pc_gb()
        rec = contas.modelo_recomendado(ram)
        self.lbl_modelo_local = tk.Label(
            esq, bg=CARTAO, fg=CINZA, font=("Segoe UI", 8), anchor="w", justify="left", wraplength=520,
            text=(f"Seu PC tem {ram} GB de RAM — recomendado: {rec}. " if ram else "")
            + "Escolha e clique em 'Instalar / baixar modelo': baixa uma vez só e fica salvo no PC.")
        self.lbl_modelo_local.pack(fill="x")

        self._rotulo(esq, "Qual IA usar nos cortes?", top=8)
        f = tk.Frame(esq, bg=CARTAO)
        f.pack(fill="x", pady=(4, 0))
        self.v_ia = tk.StringVar(value=self.cfg["ia_principal"])
        for txt, val in [("Claude", "claude"), ("Codex", "codex"), ("Gemini", "gemini"),
                         ("Local", "local"), ("Nenhuma", "nenhuma")]:
            ttk.Radiobutton(f, text=txt, value=val, variable=self.v_ia,
                            command=self._mudou_ia).pack(side="left", padx=(0, 14))
        self.v_reserva = tk.BooleanVar(value=self.cfg["ia_reserva"])
        ttk.Checkbutton(esq, text="Se a escolhida falhar ou acabar o limite, usar a outra",
                        variable=self.v_reserva, command=self._mudou_ia).pack(anchor="w", pady=(4, 0))
        import ia_motor
        self.qualidades_ia = {"Econômica — Haiku em tudo (gasta menos)": "economico",
                              "Equilibrada — Sonnet nos cortes e momentos": "equilibrado",
                              "Máxima — Opus nos cortes e momentos": "maximo"}
        fq = tk.Frame(esq, bg=CARTAO)
        fq.pack(fill="x", pady=(4, 0))
        tk.Label(fq, text="Qualidade da IA:", bg=CARTAO, fg=TEXTO, font=("Segoe UI", 10)).pack(side="left")
        nivel = ia_motor.nivel_qualidade(self.cfg)
        self.v_qualidade_ia = tk.StringVar(value=next(k for k, v in self.qualidades_ia.items() if v == nivel))
        cbq = ttk.Combobox(fq, textvariable=self.v_qualidade_ia, state="readonly", width=40,
                           values=list(self.qualidades_ia))
        cbq.pack(side="left", padx=(6, 8))
        cbq.bind("<<ComboboxSelected>>", lambda e: self._mudou_ia())
        self._botao(fq, "📊 Uso da IA", self._ver_uso_ia).pack(side="left")
        tk.Label(esq, text="(vale pro Claude e pro Gemini; o resto das tarefas usa sempre o modelo leve. "
                           "Se a resposta do modelo leve vier ruim, o corte é refeito 1 vez no mais forte.)",
                 bg=CARTAO, fg=CINZA, font=("Segoe UI", 8), wraplength=520, justify="left").pack(anchor="w")
        self._atualizar_lbl_ia()

    def _mudou_ia(self):
        self.cfg["ia_principal"] = self.v_ia.get()
        self.cfg["ia_reserva"] = self.v_reserva.get()
        qualidade = self.qualidades_ia.get(self.v_qualidade_ia.get(), "equilibrado")
        self.cfg["ia_qualidade"] = qualidade
        self.cfg["economico"] = qualidade == "economico"
        self._salvar_cfg()
        cortes.aplicar_config(self.cfg)
        self._atualizar_lbl_ia()

    def _mudou_modelo_local(self):
        modelo = self.modelos_locais.get(self.v_modelo_local.get(), cortes.MODELO_LOCAL)
        info = next((m for m in contas.MODELOS_LOCAIS if m["id"] == modelo), None)
        ram = contas.memoria_pc_gb()
        if info and ram and info["ram"] > ram and not messagebox.askyesno(
                "Modelo pesado", f"Esse modelo pede uns {info['ram']} GB de RAM e o seu PC tem {ram} GB.\n"
                "Ele pode ficar muito lento ou travar o PC enquanto pensa. Usar mesmo assim?"):
            self.v_modelo_local.set(next(k for k, v in self.modelos_locais.items() if v == cortes.MODELO_LOCAL))
            return
        self.cfg["modelo_local"] = modelo
        self._salvar_cfg()
        cortes.aplicar_config(self.cfg)
        dica = f" ({info['dica']})" if info else ""
        self._log(self.log_contas, f"IA local: {modelo}{dica}. Se ainda não baixou, clique em "
                                   "'Instalar / baixar modelo' (os que você já baixou não baixam de novo).")

    def _atualizar_lbl_ia(self):
        nome = {"claude": "Claude", "codex": "Codex", "gemini": "Gemini", "local": "Local",
                "nenhuma": "sem IA"}.get(self.cfg["ia_principal"], "?")
        import ia_motor
        if self.cfg["ia_principal"] in ("claude", "gemini"):
            nome += " · " + ia_motor.NOMES_QUALIDADE[ia_motor.nivel_qualidade(self.cfg)]
        self.lbl_ia.configure(text=f"IA: {nome}")

    def _ver_uso_ia(self):
        import ia_motor
        self._log(self.log_contas, "\n" + ia_motor.texto_uso(7))

    def _chave_gemini(self):
        from tkinter import simpledialog
        atual = self.cfg.get("gemini_api_key", "")
        chave = simpledialog.askstring(
            "Chave da API do Gemini",
            "Cole aqui a chave da API do Google AI Studio.\n"
            "Ela fica salva só neste PC, criptografada pelo Windows\n"
            "(só a sua conta deste PC consegue abrir).\n"
            "Deixe vazio e clique OK pra remover.", show="•", parent=self,
            initialvalue=atual)
        if chave is None:
            return
        self.cfg["gemini_api_key"] = chave.strip()
        if chave.strip() and self.cfg["ia_principal"] in ("claude", "nenhuma"):
            if messagebox.askyesno("Usar o Gemini?", "Quer usar o Gemini como IA principal? "
                                   "(é grátis — o Claude fica de reserva)"):
                self.cfg["ia_principal"] = "gemini"
                self.v_ia.set("gemini")
        self._salvar_cfg()
        cortes.aplicar_config(cortes.carregar_config())
        self._atualizar_lbl_ia()
        self._log(self.log_contas, "✅ Chave salva. Clique em Testar." if chave.strip()
                  else "Chave removida.")
        self._atualizar_status()
    _chave_gemini._direto = True

    def _recarregar_cfg(self):
        novo = cortes.carregar_config()
        self.cfg["gemini_modelo"] = novo.get("gemini_modelo", self.cfg.get("gemini_modelo"))

    def _instalar_tudo(self):
        ia = self.cfg["ia_principal"]
        ias = [ia] if ia in ("claude", "codex", "gemini", "local") else []
        if not messagebox.askyesno("Instalar tudo", "Vou examinar o PC e instalar o que faltar: Python, "
                                   "bibliotecas, Visual C++, ffmpeg" + (f" e a IA escolhida ({ia})" if ias else "") +
                                   ".\nSe algo der erro, o programa lê o erro e tenta consertar (com a IA, "
                                   "se tiver).\nO Windows pode pedir permissão. Continuar?"):
            return
        self._acao_conta(lambda log: contas.instalar_tudo(log, ias))

    def _mostrar_pc_fraco(self):
        ligado = bool(cortes.carregar_config().get("modo_pc_fraco"))
        self.b_fraco.configure(text="🐢 Modo PC fraco: " + ("LIGADO" if ligado else "desligado"))

    def _alternar_pc_fraco(self, ligar=None):
        cfg = cortes.carregar_config()
        ligar = (not cfg.get("modo_pc_fraco")) if ligar is None else ligar
        texto = ("Ligar o modo PC fraco?\n\n• legenda com o Whisper 'base' (~2x mais rápido, um pouco menos preciso)\n"
                 "• vídeo baixado em 720p\n• rostos lidos a cada 1 s\n\nDá pra desligar a qualquer hora."
                 if ligar else "Desligar o modo PC fraco? Volta pro Whisper 'small', 1080p e rostos a cada 0,5 s.")
        if not messagebox.askyesno("Modo PC fraco", texto):
            return
        cfg["modo_pc_fraco"] = ligar
        cortes.salvar_config(cfg)
        cortes.aplicar_config()
        self._recarregar_cfg()
        self._mostrar_pc_fraco()
        self._log(self.log_contas, "🐢 Modo PC fraco " + ("ligado." if ligar else "desligado."))

    def _testar_velocidade(self):
        self.log_contas.insert("end", "\n")

        def rodar():
            return desempenho.testar_velocidade(lambda t: self._log(self.log_contas, t))

        def fim(r):
            if r and r.get("pc_fraco") and not cortes.carregar_config().get("modo_pc_fraco"):
                self._alternar_pc_fraco(True)
        self._em_segundo_plano(rodar, fim)

    def _acao_conta(self, func):
        self.log_contas.insert("end", "\n")

        def rodar():
            log = lambda t: self._log(self.log_contas, t)  # noqa: E731
            if not self.gerando:            # mostra também os avisos internos (ex: erro da API)
                sys.stdout = sys.stderr = Saida(lambda t: t.strip() and log(t.rstrip()))
            return func(log)
        self._em_segundo_plano(rodar, lambda _r: (self._recarregar_cfg(), self._atualizar_status()))

    def _atualizar_status(self):
        def checar():
            return {"libs": contas.faltando_bibliotecas(), "ffmpeg": contas.tem_ffmpeg(),
                    "claude": contas.tem_claude(), "codex": contas.tem_codex(),
                    "local": contas.tem_local(), "gemini": contas.tem_gemini()}

        def mostrar(r):
            if not r:
                return
            falta = r["libs"]
            self.status["libs"].configure(text="✔ OK" if not falta else "✖ falta: " + ", ".join(falta),
                                          fg=VERDE if not falta else "#FF6B6B")
            for k in ("ffmpeg", "claude", "codex", "gemini", "local"):
                txt = "✔ instalado" if r[k] else "✖ não instalado"
                if k == "gemini" and self.cfg.get("gemini_api_key"):
                    txt = "✔ chave da API salva"
                self.status[k].configure(text=txt, fg=VERDE if r[k] else "#FF6B6B")
        self._em_segundo_plano(checar, mostrar)

    # =========================================================
    def _fechar(self):
        if self.monitor_proc and self.monitor_proc.poll() is None:
            if not messagebox.askyesno("Monitor ligado", "O monitor está ligado. Fechar mesmo assim?\n"
                                       "(ele será desligado)"):
                return
            (PASTA / "parar.flag").write_text("1")
            try:
                self.monitor_proc.wait(20)
            except subprocess.TimeoutExpired:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.monitor_proc.pid)],
                               creationflags=cortes.SEM_JANELA, capture_output=True)
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
