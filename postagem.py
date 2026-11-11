"""
Postagem dos cortes.

YouTube Shorts — automático pela API oficial (grátis):
  - Você cria uma vez um "cliente OAuth" no Google Cloud e salva como client_secret.json
    nesta pasta (passo a passo no LEIA-ME e no botão de ajuda da interface).
  - Na primeira postagem abre o navegador pra você autorizar a sua conta do YouTube.
  - Os vídeos sobem como PRIVADOS com horário marcado (publishAt): o próprio YouTube
    publica na hora certa, mesmo com o seu PC desligado.

TikTok — ajudante (a API só posta como privado sem auditoria do TikTok):
  - copia a legenda, abre a página de upload e mostra o arquivo pra você arrastar.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import webbrowser
from pathlib import Path

PASTA = Path(__file__).resolve().parent
ARQ_CLIENTE = PASTA / "client_secret.json"
ARQ_TOKEN = PASTA / "token_youtube.json"          # perfil Padrão (outros: token_youtube_<perfil>.json)
ARQ_AGENDA = PASTA / "agenda_postagens.json"
ESCOPOS = ["https://www.googleapis.com/auth/youtube.upload",
           "https://www.googleapis.com/auth/youtube.readonly",          # ler views/likes e 'em alta'
           "https://www.googleapis.com/auth/yt-analytics.readonly"]     # retenção (quanto assistem)
HORARIOS_PADRAO = ["12:00", "18:00", "21:00"]


# ---------------- fichas dos cortes ----------------
def ler_ficha(video: Path) -> dict:
    try:
        return json.loads(Path(video).with_suffix(".json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        txt = Path(video).with_suffix(".txt")
        titulo = txt.read_text(encoding="utf-8").splitlines()[0] if txt.exists() else Path(video).stem
        return {"titulo": titulo, "hashtags": [], "status": "novo"}


def salvar_ficha(video: Path, ficha: dict):
    Path(video).with_suffix(".json").write_text(json.dumps(ficha, indent=2, ensure_ascii=False),
                                               encoding="utf-8")


def legenda_post(ficha: dict, plataforma="tiktok") -> str:
    tags = [t if t.startswith("#") else "#" + t for t in ficha.get("hashtags", []) if t]
    extra = ["#cortes", "#fyp", "#viral"] if plataforma == "tiktok" else ["#shorts", "#cortes"]
    for e in extra:
        if e.lower() not in [t.lower() for t in tags]:
            tags.append(e)
    corpo = ficha.get('titulo', '').strip()
    chamada = str(ficha.get("chamada") or "").strip()      # pergunta pro público (puxa comentário)
    if chamada and chamada.lower() not in corpo.lower():
        corpo = f"{corpo}\n\n{chamada}"
    return f"{corpo}\n\n{' '.join(tags)}".strip()


# ---------------- agenda ----------------
def _agenda_tudo():
    try:
        dados = json.loads(ARQ_AGENDA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {"Padrão": dados} if isinstance(dados, list) else dados


def _agenda(perfil=None):
    return _agenda_tudo().get(perfil or "Padrão", [])


def horarios_do_perfil(perfil=None):
    """Horários de postagem do perfil — com 'horário inteligente' ligado, usa as horas que mais
    deram views nos Resultados (cada perfil aprende sozinho)."""
    import cortes
    cfg = cortes.carregar_config(perfil)
    base = cfg.get("horarios_postagem") or HORARIOS_PADRAO
    if cfg.get("horario_inteligente"):
        try:
            import resultados
            return resultados.horarios_inteligentes(perfil or "Padrão", base)
        except Exception:
            pass
    return base


def proximo_horario(horarios=None, agora=None, perfil=None):
    """Próximo horário livre do perfil (cada canal tem a sua agenda), com 20 min de folga."""
    horarios = horarios or HORARIOS_PADRAO
    agora = agora or dt.datetime.now().astimezone()
    ocupados = set(_agenda(perfil))
    for dia in range(0, 60):
        data = (agora + dt.timedelta(days=dia)).date()
        for h in sorted(horarios):
            hh, mm = (int(x) for x in h.split(":"))
            quando = dt.datetime(data.year, data.month, data.day, hh, mm).astimezone()
            if quando > agora + dt.timedelta(minutes=20) and quando.isoformat() not in ocupados:
                return quando
    return agora + dt.timedelta(hours=1)


def _reservar(quando: dt.datetime, perfil=None):
    tudo = _agenda_tudo()
    agora = dt.datetime.now().astimezone().isoformat()
    lista = [q for q in tudo.get(perfil or "Padrão", []) if q > agora] + [quando.isoformat()]
    tudo[perfil or "Padrão"] = sorted(lista)
    ARQ_AGENDA.write_text(json.dumps(tudo, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------- YouTube ----------------
def arq_token(perfil=None):
    if not perfil or perfil == "Padrão":
        return ARQ_TOKEN
    import re
    return PASTA / f"token_youtube_{re.sub(r'[^\w-]', '_', perfil)}.json"


def youtube_configurado():
    return ARQ_CLIENTE.exists()


def youtube_conectado(perfil=None):
    return arq_token(perfil).exists()


def perfis_conectados():
    import cortes
    return [p for p in cortes.nomes_perfis() if youtube_conectado(p)]


def _credenciais(log=print, perfil=None):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    token = arq_token(perfil)
    cred = None
    if token.exists():
        cred = Credentials.from_authorized_user_file(str(token))
        if not cred.has_scopes(ESCOPOS):          # token antigo (só upload): pede de novo
            log("Precisa autorizar de novo (agora o programa também lê as estatísticas).")
            cred = None
    if cred and cred.expired and cred.refresh_token:
        try:
            cred.refresh(Request())
        except Exception:
            cred = None
    if not cred or not cred.valid:
        if not ARQ_CLIENTE.exists():
            raise RuntimeError("Falta o arquivo client_secret.json (veja a ajuda do YouTube).")
        log("Abrindo o navegador pra você autorizar o canal do YouTube" +
            (f" do perfil '{perfil}'" if perfil and perfil != "Padrão" else "") + "...")
        fluxo = InstalledAppFlow.from_client_secrets_file(str(ARQ_CLIENTE), ESCOPOS)
        cred = fluxo.run_local_server(port=0, prompt="consent",
                                      success_message="Pronto! Pode fechar esta aba e voltar pro programa.")
    token.write_text(cred.to_json(), encoding="utf-8")
    return cred


def credenciais_leitura(perfil=None):
    """Credenciais só se já estiver conectado (não abre o navegador)."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    token = arq_token(perfil)
    if not token.exists():
        for p in perfis_conectados():
            token = arq_token(p)
            break
        else:
            raise RuntimeError("YouTube não conectado.")
    cred = Credentials.from_authorized_user_file(str(token))
    if cred.expired and cred.refresh_token:
        cred.refresh(Request())
        token.write_text(cred.to_json(), encoding="utf-8")
    return cred


def conectar_youtube(log=print, perfil=None):
    _credenciais(log, perfil)
    log("✅ Canal do YouTube conectado" + (f" ao perfil '{perfil}'." if perfil and perfil != "Padrão" else "."))
    return True


def postar_youtube(video: Path, horarios=None, agora_mesmo=False, log=print, perfil=None):
    """Sobe o corte como Short (ou a compilação como vídeo normal), agendado no próximo horário livre
    do perfil. Cada perfil pode postar num canal diferente."""
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    video = Path(video)
    ficha = ler_ficha(video)
    perfil = perfil or ficha.get("perfil") or "Padrão"
    if horarios is None:
        horarios = horarios_do_perfil(perfil)
    compilacao = ficha.get("tipo") in ("compilacao", "longo")      # vídeo normal (não é Short)
    titulo = (ficha.get("titulo") or video.stem)[:100 if compilacao else 90]
    if not compilacao and "#shorts" not in titulo.lower():
        titulo = (titulo[:91] + " #shorts")[:100]
    descricao = ficha.get("descricao") if compilacao else legenda_post(ficha, "youtube")
    if (ficha.get("canal") or ficha.get("titulo_original")) and "Fonte:" not in (descricao or ""):
        descricao = (descricao or "") + f"\n\nFonte: {ficha.get('canal', '')} — {ficha.get('titulo_original', '')}"
    status = {"selfDeclaredMadeForKids": False}
    quando = None
    if agora_mesmo:
        status["privacyStatus"] = "public"
    else:
        quando = proximo_horario(horarios, perfil=perfil)
        status["privacyStatus"] = "private"
        status["publishAt"] = quando.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    corpo = {"snippet": {"title": titulo, "description": descricao[:4900], "categoryId": "24",
                         "tags": [t.lstrip("#") for t in ficha.get("hashtags", [])][:15]},
             "status": status}
    yt = build("youtube", "v3", credentials=_credenciais(log, perfil), cache_discovery=False)
    log(f"Enviando pro YouTube: {titulo}")
    pedido = yt.videos().insert(part="snippet,status", body=corpo,
                                media_body=MediaFileUpload(str(video), chunksize=4 * 1024 * 1024,
                                                           resumable=True, mimetype="video/mp4"))
    resposta = None
    while resposta is None:
        progresso, resposta = pedido.next_chunk()
        if progresso:
            log(f"   {int(progresso.progress() * 100)}%")
    vid = resposta["id"]
    if quando:
        _reservar(quando, perfil)
    ficha.update(status="postado", youtube_id=vid,
                 youtube_quando=quando.isoformat() if quando else dt.datetime.now().isoformat())
    salvar_ficha(video, ficha)
    log(f"✅ No YouTube: https://youtube.com/shorts/{vid}" +
        (f" — publica em {quando:%d/%m às %H:%M}" if quando else " — já está público"))
    return vid


# ---------------- TikTok (ajudante) ----------------
def ajudar_tiktok(video: Path, copiar_texto) -> str:
    """Copia a legenda (via função da interface), abre a página de upload e mostra o arquivo."""
    video = Path(video)
    ficha = ler_ficha(video)
    texto = legenda_post(ficha, "tiktok")
    copiar_texto(texto)
    webbrowser.open("https://www.tiktok.com/tiktokstudio/upload")
    if os.name == "nt":
        subprocess.Popen(["explorer", "/select,", str(video.resolve())])
    ficha["tiktok"] = True
    if ficha.get("status") == "novo":
        ficha["status"] = "aprovado"
    salvar_ficha(video, ficha)
    return texto
