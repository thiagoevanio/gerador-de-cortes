"""
Instalação de dependências e conexão das contas (Claude e Codex).
Usado pela interface (aba "Contas & IA").
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import cortes

PASTA = Path(__file__).resolve().parent
SEM_JANELA = cortes.SEM_JANELA
WINGET_OPCOES = ["--accept-package-agreements", "--accept-source-agreements", "--silent"]

import doutor

BIBLIOTECAS = doutor.BIBLIOTECAS


def python_console():
    """python.exe (não o pythonw.exe) pra rodar pip e o monitor."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").exists():
        return str(exe.parent / "python.exe")
    return sys.executable


def rodar_mostrando(cmd, log):
    """Roda um comando e manda a saída, linha a linha, pro log da janela."""
    log("$ " + " ".join(str(c) for c in cmd[-6:]))
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace", creationflags=SEM_JANELA,
                             cwd=str(PASTA))
    except FileNotFoundError as e:
        log(f"❌ Não encontrei o programa: {e}")
        return 1
    vistas, passo = set(), -1
    for bruta in p.stdout:
        # tira códigos de cor/cursor do terminal e as "rodinhas" (⠋⠙⠹...) que o Ollama desenha
        for linha in re.split(r"[\r\n]+", re.sub(r"\x1b\[[0-9;?]*[A-Za-z]|[⠀-⣿]", "", bruta)):
            linha = linha.strip()
            if not linha or not any(ch.isalnum() for ch in linha) or linha in vistas:
                continue
            pct = re.search(r"(\d{1,3})%", linha)
            if "█" in linha or "▒" in linha or "▏" in linha or pct:
                # barra de progresso: só a cada 10% (em vez de centenas de linhas)
                if pct and int(pct.group(1)) // 10 > passo:
                    passo = int(pct.group(1)) // 10
                    log(f"  {re.sub(r'[▕▏█▒ ]{3,}', ' ', linha)[:120]}")
                continue
            vistas.add(linha)                   # o Ollama redesenha as mesmas linhas sem parar
            log("  " + linha[:160])
    return p.wait()


# ---------------- status ----------------
def faltando_bibliotecas():
    return [nome for nome, mod in BIBLIOTECAS if importlib.util.find_spec(mod) is None]


def tem_ffmpeg():
    return bool(shutil.which("ffmpeg"))


def tem_claude():
    return bool(cortes.achar_cli("claude"))


def tem_codex():
    return bool(cortes.achar_cli("codex"))


def tem_winget():
    return bool(shutil.which("winget"))


# ---------------- instalar ----------------
def instalar_bibliotecas(log):
    log("Instalando bibliotecas do Python (pode demorar alguns minutos)...")
    rc = rodar_mostrando([python_console(), "-m", "pip", "install", "-U", "-r",
                          str(PASTA / "requirements.txt")], log)
    log("✅ Bibliotecas instaladas." if rc == 0 else "❌ Algo deu errado na instalação.")
    return rc == 0


def atualizar_baixadores(log):
    log("Atualizando yt-dlp e streamlink (resolve a maioria dos erros de download)...")
    rc = rodar_mostrando([python_console(), "-m", "pip", "install", "-U", "yt-dlp", "streamlink"], log)
    log("✅ Atualizado." if rc == 0 else "❌ Não consegui atualizar.")
    return rc == 0


def _winget(pacote, nome, log):
    if not tem_winget():
        log("❌ O winget não está disponível neste Windows. Instale pelo site oficial.")
        return False
    log(f"Instalando {nome}...")
    rc = rodar_mostrando(["winget", "install", "-e", "--id", pacote] + WINGET_OPCOES, log)
    # winget devolve código diferente de 0 quando já está instalado; não é erro
    return rc == 0 or rc == -1978335189


def instalar_ffmpeg(log):
    """ffmpeg completo dentro da pasta do programa (hash oficial conferido): vale na hora, sem reiniciar."""
    ok = doutor.conserto_instalar_ffmpeg(log)
    log("✅ ffmpeg instalado." if ok else "❌ Não consegui instalar o ffmpeg. Clique em 'Examinar o PC'.")
    return ok


def instalar_claude(log):
    ok = _winget("Anthropic.ClaudeCode", "Claude Code", log)
    log("✅ Claude Code instalado. Agora clique em 'Conectar conta'." if ok
        else "❌ Não consegui instalar o Claude Code.")
    return ok


def instalar_codex(log):
    npm = shutil.which("npm") or next((c for c in [r"C:\Program Files\nodejs\npm.cmd"]
                                       if os.path.exists(c)), None)
    if not npm:
        log("O Codex precisa do Node.js. Instalando o Node.js primeiro...")
        if not _winget("OpenJS.NodeJS.LTS", "Node.js", log):
            log("❌ Não consegui instalar o Node.js.")
            return False
        npm = r"C:\Program Files\nodejs\npm.cmd"
        if not os.path.exists(npm):
            log("⚠ Node.js instalado. FECHE E ABRA a interface e clique em Instalar Codex de novo.")
            return False
    log("Instalando o Codex...")
    env_path = os.path.dirname(npm)
    os.environ["PATH"] = env_path + os.pathsep + os.environ.get("PATH", "")
    rc = rodar_mostrando(["cmd", "/c", npm, "install", "-g", "@openai/codex"], log)
    if rc == 0:
        log("✅ Codex instalado. Agora clique em 'Conectar conta'.")
        log("   (se o botão Testar falhar, feche e abra a interface uma vez)")
        return True
    log("❌ Não consegui instalar o Codex.")
    return False


def _npm_global(pacote, nome, log):
    npm = shutil.which("npm") or next((c for c in [r"C:\Program Files\nodejs\npm.cmd"]
                                       if os.path.exists(c)), None)
    if not npm:
        log(f"O {nome} precisa do Node.js. Instalando o Node.js primeiro...")
        if not _winget("OpenJS.NodeJS.LTS", "Node.js", log):
            log("❌ Não consegui instalar o Node.js.")
            return False
        npm = r"C:\Program Files\nodejs\npm.cmd"
        if not os.path.exists(npm):
            log("⚠ Node.js instalado. FECHE E ABRA a interface e clique em Instalar de novo.")
            return False
    os.environ["PATH"] = os.path.dirname(npm) + os.pathsep + os.environ.get("PATH", "")
    log(f"Instalando o {nome}...")
    return rodar_mostrando(["cmd", "/c", npm, "install", "-g", pacote], log) == 0


def instalar_gemini(log):
    ok = _npm_global("@google/gemini-cli", "Gemini CLI", log)
    log("✅ Gemini instalado. Agora clique em 'Conectar conta' (login com sua conta Google)." if ok
        else "❌ Não consegui instalar o Gemini.")
    return ok


def tem_gemini():
    return bool(cortes.GEMINI_API_KEY or cortes.achar_cli("gemini"))


# ---------------- conectar (login) ----------------
def _abrir_console(titulo, cmd):
    if os.name == "nt":
        subprocess.Popen(["cmd", "/c", "start", titulo, "cmd", "/k"] + cmd,
                         creationflags=SEM_JANELA)
    else:
        subprocess.Popen(["x-terminal-emulator", "-e"] + cmd)


def conectar_claude(log):
    base = cortes.achar_cli("claude")
    if not base:
        log("❌ Instale o Claude Code primeiro.")
        return False
    _abrir_console("Conectar Claude", base)
    log("Abri uma janela preta do Claude:")
    log("  1. Escolha 'Claude account with subscription' e faça login no navegador")
    log("  2. Quando aparecer a caixinha pra digitar, escreva /exit e feche a janela")
    log("  3. Volte aqui e clique em Testar")
    return True


def conectar_codex(log):
    base = cortes.achar_cli("codex")
    if not base:
        log("❌ Instale o Codex primeiro.")
        return False
    _abrir_console("Conectar Codex", base + ["login"])
    log("Abri uma janela preta do Codex:")
    log("  1. Escolha entrar com a conta do ChatGPT e faça login no navegador")
    log("  2. Quando terminar, feche a janela")
    log("  3. Volte aqui e clique em Testar")
    return True


def conectar_gemini(log):
    base = cortes.achar_cli("gemini")
    if not base:
        log("❌ Instale o Gemini primeiro.")
        return False
    _abrir_console("Conectar Gemini", base)
    log("Abri uma janela preta do Gemini:")
    log("  1. Escolha 'Login with Google' e entre com a mesma conta do Gemini do celular")
    log("  2. Se perguntar se confia na pasta, escolha que sim")
    log("  3. Quando aparecer a caixinha pra digitar, escreva /quit e feche a janela")
    log("  4. Volte aqui e clique em Testar")
    return True


# ---------------- testar ----------------
TESTE = 'Responda apenas com este JSON, sem mais nada: {"ok": true}'


def testar_claude(log):
    log("Testando o Claude...")
    r = cortes.claude_json(TESTE, timeout=180)
    ok = bool(r and r.get("ok"))
    log("✅ Claude conectado e respondendo!" if ok else
        "❌ Claude não respondeu. Clique em 'Conectar conta' e faça o login.")
    return ok


def testar_gemini(log):
    log("Testando o Gemini" + (" (pela chave da API)..." if cortes.GEMINI_API_KEY else " (pelo CLI)..."))
    r = cortes.gemini_json(TESTE, timeout=180)
    ok = bool(r and r.get("ok"))
    if ok and cortes.GEMINI_API_KEY:
        cfg = cortes.carregar_config()
        if cfg.get("gemini_modelo") != cortes.GEMINI_MODELO:
            cfg["gemini_modelo"] = cortes.GEMINI_MODELO        # lembra o modelo que funcionou
            cortes.salvar_config(cfg)
        log(f"   modelo: {cortes.GEMINI_MODELO}")
    log("✅ Gemini conectado e respondendo!" if ok else
        "❌ Gemini não respondeu. Clique em 'Conectar conta' e faça o login com a conta Google.")
    return ok


def testar_codex(log):
    log("Testando o Codex...")
    r = cortes.codex_json(TESTE, timeout=180)
    ok = bool(r and r.get("ok"))
    log("✅ Codex conectado e respondendo!" if ok else
        "❌ Codex não respondeu. Clique em 'Conectar conta' e faça o login.")
    return ok


# ---------------- IA local (Ollama) ----------------
def achar_ollama():
    c = shutil.which("ollama")
    if not c and os.name == "nt":
        c = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
        c = c if os.path.exists(c) else None
    return c


def tem_local():
    return bool(achar_ollama())


def _ligar_ollama():
    exe = achar_ollama()
    if exe and not cortes.ollama_rodando():
        subprocess.Popen([exe, "serve"], creationflags=SEM_JANELA, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        import time
        for _ in range(15):
            if cortes.ollama_rodando():
                break
            time.sleep(1)
    return cortes.ollama_rodando()


def instalar_local(log):
    if not achar_ollama():
        if not _winget("Ollama.Ollama", "Ollama (IA local)", log):
            log("❌ Não consegui instalar o Ollama.")
            return False
    exe = achar_ollama()
    if not exe:
        log("⚠ Ollama instalado. FECHE E ABRA a interface e clique em Instalar de novo pra baixar o modelo.")
        return False
    if not _ligar_ollama():
        log("❌ O Ollama não iniciou. Reinicie o PC e tente de novo.")
        return False
    modelo = cortes.MODELO_LOCAL
    if modelo_baixado(modelo):
        log(f"✅ O modelo {modelo} já está no PC — não precisa baixar de novo.")
        return True
    info = next((m for m in MODELOS_LOCAIS if m["id"] == modelo), None)
    tamanho = f"{info['gb']:.1f} GB".replace(".", ",") if info else "alguns GB"
    log(f"Baixando o modelo {modelo} ({tamanho}, só desta vez — depois fica salvo no PC)...")
    rc = rodar_mostrando([exe, "pull", modelo], log)
    log("✅ IA local pronta! Ela é grátis mas mais lenta e mais simples que Claude/Codex."
        if rc == 0 else "❌ Não consegui baixar o modelo.")
    return rc == 0


# Modelos da IA local, do mais leve ao mais forte (tamanho do download e memória pedida).
MODELOS_LOCAIS = [
    {"id": "qwen2.5:3b", "nome": "Leve", "gb": 1.9, "ram": 8,
     "dica": "roda em qualquer PC; respostas mais simples"},
    {"id": "qwen2.5:7b", "nome": "Média", "gb": 4.7, "ram": 16,
     "dica": "bem melhor nos títulos e perguntas"},
    {"id": "gemma3:12b", "nome": "Forte", "gb": 8.1, "ram": 16,
     "dica": "ótima em português; mais rápida com placa de vídeo"},
    {"id": "qwen2.5:14b", "nome": "Máxima", "gb": 9.0, "ram": 32,
     "dica": "a melhor; pede PC forte ou placa de vídeo com 12 GB"},
]


def rotulo_modelo(m):
    return f"{m['nome']} — {m['id']} ({m['gb']:.1f} GB, {m['ram']} GB de RAM)".replace(".", ",", 1)


def memoria_pc_gb():
    """Memória RAM total do PC, em GB (0 se não der pra saber)."""
    try:
        import ctypes

        class Mem(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = Mem()
        m.dwLength = ctypes.sizeof(Mem)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return round(m.ullTotalPhys / 1024 ** 3)
    except Exception:
        return 0


def modelo_recomendado(ram_gb=None):
    """O modelo mais forte que cabe com folga na memória do PC."""
    ram = memoria_pc_gb() if ram_gb is None else ram_gb
    cabem = [m for m in MODELOS_LOCAIS if m["ram"] <= ram] if ram else []
    return (cabem[-1] if cabem else MODELOS_LOCAIS[0])["id"]


def modelos_baixados():
    """Modelos que já estão no PC (pergunta ao Ollama; vazio se ele estiver desligado)."""
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(cortes.URL_OLLAMA + "/api/tags", timeout=3) as r:
            return [m.get("name", "") for m in json.loads(r.read().decode("utf-8")).get("models", [])]
    except Exception:
        return []


def modelo_baixado(modelo):
    nomes = modelos_baixados()
    return modelo in nomes or (":" not in modelo and f"{modelo}:latest" in nomes)


def conectar_local(log):
    ok = _ligar_ollama()
    log("✅ IA local ligada (não precisa de conta)." if ok else "❌ Instale a IA local primeiro.")
    return ok


def testar_local(log):
    _ligar_ollama()
    log("Testando a IA local (pode levar até 1 minuto na primeira vez)...")
    r = cortes.ollama_json(TESTE, timeout=300)
    ok = bool(r and r.get("ok"))
    log("✅ IA local respondendo!" if ok else "❌ A IA local não respondeu.")
    return ok


# ---------------- tudo de uma vez ----------------
def examinar_pc(log):
    """Mostra o que o PC tem e o que falta (sem instalar nada)."""
    log("Examinando o PC...")
    log(doutor.texto_relatorio(doutor.examinar()))
    return True


def instalar_tudo(log, ias=("claude",)):
    log("=== Examinando o PC e instalando o que falta ===")
    if faltando_bibliotecas():            # faltam aqui: instala neste Python e depois confere tudo
        instalar_bibliotecas(log)
    ok, relatorio = doutor.consertar(log, usar_ia=True)
    log(doutor.texto_relatorio(relatorio))
    prog = doutor.python_do_programa()
    if ok and prog and os.path.normcase(str(prog)) != os.path.normcase(python_console()):
        log("⚠ As bibliotecas foram instaladas no ambiente do programa. FECHE e abra pelo atalho "
            "'Gerador de Cortes' pra usar.")
    for ia in ias:
        if ia == "claude" and not tem_claude():
            instalar_claude(log)
        elif ia == "codex" and not tem_codex():
            instalar_codex(log)
        elif ia == "gemini" and not tem_gemini():
            instalar_gemini(log)
        elif ia == "local" and not cortes.ollama_rodando():
            instalar_local(log)
    log("=== Fim. Agora clique em 'Conectar conta' na IA que você vai usar. ===")
    return True
