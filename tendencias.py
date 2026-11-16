"""
Radar de tendências — acha os vídeos que estão bombando AGORA pra você cortar primeiro.

Fontes (todas grátis):
  1. Assuntos em alta no Brasil (Google Trends, RSS público).
  2. Busca no YouTube por nicho (podcast, react, futebol...) ordenada por views da semana/do dia.
  3. "Em alta" oficial do YouTube Brasil (API), se o seu YouTube estiver conectado.

Cada vídeo ganha uma nota de tendência:
  velocidade (views por hora desde que saiu) + engajamento + bônus se o título cita um assunto
  em alta + bônus se o YouTube já tem o gráfico de "mais repetidos" − se você já cortou.
"""
from __future__ import annotations

import json
import math
import re
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from infraestrutura import salvar_json, exclusividade

PASTA = Path(__file__).resolve().parent
ARQ_CACHE = PASTA / "tendencias.json"
NICHOS_PADRAO = ["podcast", "react", "entrevista", "live", "polêmica", "fofoca", "futebol",
                 "BBB", "treta", "humor"]
# filtros de busca do YouTube: ordenar por views + período + só vídeos
FILTRO = {"hoje": "CAMSBAgCEAE%253D", "semana": "CAMSBAgDEAE%253D", "mes": "CAMSBAgEEAE%253D"}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


# ---------------- cache ----------------
def _cache():
    try:
        return json.loads(ARQ_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _salvar(dados):
    with exclusividade(ARQ_CACHE.with_suffix(".lock"), timeout=30):
        c = _cache()
        c.update(dados)
        salvar_json(ARQ_CACHE, c)


# ---------------- assuntos em alta (Google Trends) ----------------
def _trafego(txt):
    """'20.000+' / '2K+' / '1M+' → número."""
    t = (txt or "").upper().replace("+", "").replace(".", "").replace(",", "").strip()
    mult = 1000 if t.endswith("K") else 1_000_000 if t.endswith("M") else 1
    try:
        return int(float(t.rstrip("KM")) * mult)
    except ValueError:
        return 0


def buscar_assuntos(log=print):
    """Lista de {'termo', 'trafego', 'noticia'} dos assuntos em alta no Brasil."""
    urls = ["https://trends.google.com/trending/rss?geo=BR",
            "https://trends.google.com/trends/trendingsearches/daily/rss?geo=BR"]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=20) as r:
                xml = r.read()
            raiz = ET.fromstring(xml)
            ns = {"ht": "https://trends.google.com/trending/rss"}
            assuntos = []
            for item in raiz.iter("item"):
                termo = (item.findtext("title") or "").strip()
                trafego = item.findtext("ht:approx_traffic", namespaces=ns) or \
                    next((c.text for c in item if c.tag.endswith("approx_traffic")), "")
                noticia = next((c.findtext("{*}news_item_title") for c in item if c.tag.endswith("news_item")), "")
                if termo:
                    assuntos.append({"termo": termo, "trafego": _trafego(trafego), "noticia": noticia or ""})
            if assuntos:
                assuntos.sort(key=lambda a: -a["trafego"])
                _salvar({"assuntos": assuntos, "assuntos_quando": time.time()})
                return assuntos
        except Exception as e:
            log(f"   (assuntos em alta indisponíveis em {url.split('/')[2]}: {str(e)[:80]})")
    return _cache().get("assuntos", [])


def assuntos_recentes(n=8, idade_max_h=8):
    """Só lê o cache (rápido, sem internet) — usado no prompt da IA."""
    c = _cache()
    if time.time() - c.get("assuntos_quando", 0) > idade_max_h * 3600:
        return []
    return [a["termo"] for a in c.get("assuntos", [])[:n]]


# ---------------- YouTube ----------------
def _ydl(url, flat=True, n=15):
    import yt_dlp
    import cortes
    import baixador
    op = baixador.opcoes_ytdlp(skip_download=True, logger=cortes.LoggerMudo())
    if flat:
        op.update(extract_flat="in_playlist", playlistend=n)
    with yt_dlp.YoutubeDL(op) as y:
        return y.extract_info(url, download=False)


def buscar_youtube(termo, periodo="semana", n=15):
    """Vídeos de um termo, ordenados por views no período. Lista rasa (rápida)."""
    url = f"https://www.youtube.com/results?search_query={quote(termo)}&sp={FILTRO.get(periodo, FILTRO['semana'])}"
    info = _ydl(url, flat=True, n=n)
    saida = []
    for e in info.get("entries") or []:
        if not e.get("id") or e.get("ie_key") not in (None, "Youtube"):
            continue
        saida.append({"id": e["id"], "titulo": e.get("title") or "", "canal": e.get("channel") or e.get("uploader") or "",
                      "canal_id": e.get("channel_id"), "views": e.get("view_count") or 0, "duracao": e.get("duration") or 0, "termo": termo})
    return saida


def em_alta_api(log=print):
    """'Em alta' oficial do YouTube Brasil (precisa do YouTube conectado na Galeria)."""
    try:
        import postagem
        if not postagem.youtube_conectado():
            return []
        from googleapiclient.discovery import build
        yt = build("youtube", "v3", credentials=postagem.credenciais_leitura(), cache_discovery=False)
        r = yt.videos().list(part="snippet,statistics,contentDetails", chart="mostPopular",
                             regionCode="BR", maxResults=50).execute()
    except Exception as e:
        log(f"   (em alta do YouTube indisponível: {str(e)[:100]})")
        return []
    saida = []
    for v in r.get("items", []):
        st, sn = v.get("statistics", {}), v.get("snippet", {})
        saida.append({"id": v["id"], "titulo": sn.get("title", ""), "canal": sn.get("channelTitle", ""),
                      "views": int(st.get("viewCount", 0) or 0), "likes": int(st.get("likeCount", 0) or 0),
                      "comentarios": int(st.get("commentCount", 0) or 0),
                      "duracao": _iso_duracao(v.get("contentDetails", {}).get("duration", "")),
                      "publicado": sn.get("publishedAt", ""), "termo": "em alta no YouTube"})
    return saida


def _iso_duracao(iso):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def _horas_desde(publicado=None, timestamp=None, upload_date=None):
    agora = datetime.now(timezone.utc)
    try:
        if timestamp:
            quando = datetime.fromtimestamp(float(timestamp), timezone.utc)
        elif publicado:
            quando = datetime.fromisoformat(publicado.replace("Z", "+00:00"))
        elif upload_date:
            quando = datetime.strptime(upload_date, "%Y%m%d").replace(hour=12, tzinfo=timezone.utc)
        else:
            return None
    except (ValueError, OSError):
        return None
    return max(1.0, (agora - quando).total_seconds() / 3600)


def _ja_cortados():
    feitos = set()
    base = PASTA / "cortes_prontos"
    if base.exists():
        for f in base.rglob("*.json"):
            try:
                fonte = json.loads(f.read_text(encoding="utf-8")).get("fonte", "")
            except (OSError, json.JSONDecodeError):
                continue
            m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", fonte)
            if m:
                feitos.add(m.group(1))
    return feitos


def _formatar(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} mi".replace(".", ",")
    if n >= 1000:
        return f"{n / 1000:.0f} mil"
    return str(int(n))


def pontuar(v, assuntos, feitos):
    motivos = []
    vel = v.get("velocidade_recente", v.get("velocidade")) or 0
    nota = math.log10(vel + 1) * 12 if vel else math.log10((v.get("views") or 0) + 1) * 5
    if vel:
        motivos.append(f"🔥 {_formatar(vel)} views/hora" + (" na última medição" if "velocidade_recente" in v else " em média desde a publicação"))
    if v.get("acima_normal_canal", 0) > 1:
        nota += min(12, math.log2(v["acima_normal_canal"]) * 4)
        motivos.append(f"{v['acima_normal_canal']:.1f}x o crescimento medido em outros vídeos do canal")
    if not v.get("detalhado"):
        nota *= 0.6
        motivos.append("Dados parciais: classificação provisória")
    if v.get("views") and v.get("likes"):
        eng = v["likes"] / max(1, v["views"]) * 100
        nota += min(8, eng * 1.5)
        if eng >= 4:
            motivos.append(f"❤ engajamento alto ({eng:.1f}%)")
    titulo = (v.get("titulo") or "").lower()
    for a in assuntos[:25]:
        termo = a["termo"].lower()
        if len(termo) >= 3 and termo in titulo:
            nota += 15
            v["assunto"] = a["termo"]
            motivos.append(f"📈 assunto em alta: {a['termo']}")
            break
    if v.get("heatmap"):
        nota += 5
        motivos.append("📊 já tem 'mais repetidos'")
    if v["id"] in feitos:
        nota -= 30
        motivos.append("✔ você já cortou")
    v["nota"] = round(nota, 1)
    v["motivos"] = motivos
    return v


def _normalizar(texto):
    return " ".join(re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()))


def _relevante(video, termos):
    texto = set(_normalizar(video.get("titulo", "") + " " + video.get("canal", "")).split())
    return any(set(_normalizar(t).split()).issubset(texto) for t in termos if _normalizar(t))


def _canal_existe(url):
    try:
        info = _ydl(url + "/videos", flat=True, n=1)
        return bool(info.get("channel_id") or info.get("id"))
    except Exception:
        return False


def buscar_canal(termo, n=15):
    """Resolve uma origem por identificador, endereço ou nome exato, sem adivinhar homônimos."""
    termo = termo.strip()
    if re.fullmatch(r"UC[\w-]{22}", termo):
        url = f"https://www.youtube.com/channel/{termo}"
    elif re.fullmatch(r"@[\w.\-]+", termo):
        url = "https://www.youtube.com/" + termo
    elif re.fullmatch(r"https://(?:www\.)?youtube\.com/(?:@[\w.\-]+|channel/UC[\w-]{22})/?", termo):
        url = termo.rstrip('/')
    elif re.fullmatch(r"(?:https?://)?(?:www\.|m\.)?youtube\.com/(?:@[\w.\-]+|channel/UC[\w-]{22}|c/[\w.\-]+|user/[\w.\-]+)/?.*", termo):
        m = re.search(r"youtube\.com/(@[\w.\-]+|channel/UC[\w-]{22}|c/[\w.\-]+|user/[\w.\-]+)", termo)
        url = "https://www.youtube.com/" + m.group(1)
    elif re.fullmatch(r"[\w.\-]{3,30}", termo) and _canal_existe("https://www.youtube.com/@" + termo):
        url = "https://www.youtube.com/@" + termo          # nome digitado = @ do canal (o jeito mais comum)
    else:
        origens = {}
        for v in buscar_youtube(termo, n=30):
            if _normalizar(v['canal']) == _normalizar(termo) and v.get('canal_id'):
                origens[v['canal_id']] = v['canal']
        if len(origens) != 1:
            raise ValueError(f"Não foi possível identificar um único canal para '{termo}'. Use o @ ou o link do canal.")
        url = 'https://www.youtube.com/channel/' + next(iter(origens))
    info = _ydl(url + '/videos', flat=True, n=n)
    canal_id = info.get('channel_id') or info.get('id')
    saida = []
    for e in info.get('entries') or []:
        if not e or not re.fullmatch(r'[\w-]{11}', e.get('id') or ''):
            continue
        saida.append(dict(id=e['id'], titulo=e.get('title') or '',
                          canal=e.get('channel') or info.get('channel') or info.get('uploader') or termo,
                          canal_id=canal_id, origem_id=canal_id, views=e.get('view_count') or 0,
                          duracao=e.get('duration') or 0, termo=termo))
    return saida


def radar(nichos=None, periodo="semana", detalhar=15, incluir_assuntos=True, log=print, descoberta=False, modo="assunto", filtros=None):
    """Lista de vídeos longos em alta, do mais quente pro menos quente."""
    if modo not in ('assunto', 'canal', 'descoberta'):
        raise ValueError('Modo de pesquisa inválido.')
    filtros = filtros or {}
    minimo = max(5, float(filtros.get("duracao_min", 360)))
    maximo = max(minimo, min(21600, float(filtros.get("duracao_max", 21600))))
    descoberta = descoberta or modo == 'descoberta'
    nichos = [n.strip() for n in (nichos or NICHOS_PADRAO) if n.strip()]
    # no modo canal só entram os canais digitados: nada de assuntos do Brasil nem buscas soltas
    assuntos = buscar_assuntos(log) if incluir_assuntos and modo != 'canal' else []
    termos = list(dict.fromkeys(nichos + ([a["termo"] for a in assuntos[:5]] if descoberta else [])))
    log(f"Procurando vídeos em alta: {', '.join(termos[:12])}{'...' if len(termos) > 12 else ''}")
    candidatos, falhas = {}, []
    for v in em_alta_api(log) if descoberta else []:
        candidatos[v["id"]] = v
    for termo in termos:
        try:
            for v in (buscar_canal(termo) if modo == 'canal' else buscar_youtube(termo, periodo)):
                if modo == 'canal' or descoberta or _relevante(v, nichos):
                    candidatos.setdefault(v["id"], v)
        except Exception as e:
            if modo == 'canal':
                falhas.append(f"{termo}: {str(e)[:120]}")
            log(f"   (busca '{termo}' falhou: {str(e)[:80]})")
    if modo == 'canal' and falhas and not candidatos:
        raise ValueError("Não achei o canal. " + " | ".join(falhas[:3]))
    # só vídeos que dá pra cortar: entre 6 min e 6 h (tira Shorts e lives de 12h)
    lista = [v for v in candidatos.values() if (modo == 'canal' and not v.get('duracao')) or minimo <= (v.get("duracao") or 0) <= maximo
             or (not v.get("duracao") and v.get("views"))]
    # Intercala as origens pesquisadas para o orçamento não ficar só no maior nicho.
    por_termo = {t: [] for t in termos}
    for v in lista:
        por_termo.setdefault(v.get('termo'), []).append(v)
    lista = [grupo[i] for i in range(max((len(g) for g in por_termo.values()), default=0))
             for grupo in por_termo.values() if i < len(grupo)]
    log(f"   {len(lista)} candidatos — detalhando até {min(detalhar, len(lista))}, alternando os termos pesquisados...")
    for i, v in enumerate(lista[:detalhar], 1):
        try:
            info = _ydl(f"https://www.youtube.com/watch?v={v['id']}", flat=False)
        except Exception:
            continue
        if modo == 'canal':
            if v.get('origem_id') and info.get('channel_id') != v['origem_id']:
                v['fora_filtro'] = True
                continue
            horas_canal = _horas_desde(timestamp=info.get('timestamp') or info.get('release_timestamp'),
                                       upload_date=info.get('upload_date'))
            if horas_canal is None or horas_canal > {'hoje': 24, 'semana': 168, 'mes': 720}.get(periodo, 168):
                v['fora_filtro'] = True
                continue
            if not minimo <= (info.get('duration') or 0) <= maximo:
                v['fora_filtro'] = True
                continue
            v['origem_validada'] = True
        idioma = info.get('language') or ''
        if filtros.get('idioma') and not idioma.lower().startswith(filtros['idioma'].lower()):
            v['fora_filtro'] = True
            continue
        if not minimo <= (info.get('duration') or 0) <= maximo:
            v['fora_filtro'] = True
            continue
        v.update(descricao=(info.get("description") or "")[:3000], idioma=idioma, views=info.get("view_count") or v.get("views") or 0, likes=info.get("like_count") or 0,
                 comentarios=info.get("comment_count") or 0, duracao=info.get("duration") or v.get("duracao"),
                 detalhado=True, canal_id=info.get("channel_id"), canal=info.get("channel") or v.get("canal"), heatmap=bool(info.get("heatmap")),
                 ao_vivo=info.get("live_status") in ("is_live", "is_upcoming"))
        horas = _horas_desde(v.get("publicado"), info.get("timestamp") or info.get("release_timestamp"),
                             info.get("upload_date"))
        if horas:
            v["horas"] = round(horas, 1)
            v["velocidade"] = v["views"] / horas
        from historico_metricas import medir
        v.update(medir(v))
        log(f"   {i}/{min(detalhar, len(lista))} {v['titulo'][:50]}")
    feitos = _ja_cortados()
    resultado = [pontuar(v, assuntos, feitos) for v in lista if not v.get("ao_vivo")
                 and not v.get('fora_filtro') and (not filtros.get("idioma") or v.get("detalhado")) and (modo != 'canal' or v.get('origem_validada'))]
    resultado.sort(key=lambda v: -v["nota"])
    for v in resultado:
        v["url"] = f"https://www.youtube.com/watch?v={v['id']}"
        v["thumb"] = f"https://i.ytimg.com/vi/{v['id']}/mqdefault.jpg"
    from editorial import agrupar
    for i, grupo in enumerate(agrupar(resultado)):
        for v in grupo:
            v['grupo_assunto'] = i
            v['coberturas_relacionadas'] = len(grupo)-1
            if len(grupo) > 1:
                v['motivos'].append(f'{len(grupo)-1} cobertura(s) relacionada(s) neste radar')
    _salvar({"videos": resultado[:40], "videos_quando": time.time(), "nichos": nichos, "periodo": periodo})
    return resultado[:40]


def ultimo_radar():
    c = _cache()
    return c.get("videos", []), c.get("assuntos", []), c.get("videos_quando", 0)


def prioridade_titulo(titulo):
    """Bônus de prioridade na fila se o título cita um assunto em alta (usa só o cache)."""
    t = (titulo or "").lower()
    return 10 if any(a.lower() in t for a in assuntos_recentes(20, 12) if len(a) >= 3) else 0


def formatar(n):
    return _formatar(n)
