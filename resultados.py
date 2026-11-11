"""
Resultados e aprendizado — o programa aprende com os SEUS números.

  - YouTube: views, likes, comentários e retenção (quanto do vídeo as pessoas assistem) de cada
    Short postado pelo programa (API grátis, mesma conexão da Galeria).
  - TikTok: importe o relatório exportado do TikTok Studio (CSV ou Excel), ou digite as views
    na Galeria.
  - Aprendizado: compara grupos (pergunta curta x longa, com nome x sem nome, formato da faixa,
    canal de origem, horário...) e escreve um resumo curto que vai junto pra IA. Assim as
    próximas perguntas saem no estilo que dá mais views NO SEU canal.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
import statistics
from pathlib import Path
from infraestrutura import salvar_json
from estatistica_editorial import contraste

PASTA = Path(__file__).resolve().parent
BASE = PASTA / "cortes_prontos"
ARQ_APRENDIZADO = PASTA / "aprendizado.json"


# ---------------- fichas ----------------
def fichas(incluir_descartados=False):
    """Lista de (caminho do vídeo, ficha) de todos os cortes."""
    saida = []
    if not BASE.exists():
        return saida
    for js in BASE.rglob("*.json"):
        if any(p in js.parts for p in (".miniaturas", "_trabalho", "_edicao")):
            continue
        if not incluir_descartados and "_descartados" in js.parts:
            continue
        mp4 = js.with_suffix(".mp4")
        if not mp4.exists():
            continue
        try:
            saida.append((mp4, json.loads(js.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError):
            pass
    return saida


def _data_valida(valor,formato):
    try:dt.datetime.strptime(valor,formato);return True
    except ValueError:return False


def registrar_medicao(ficha, plataforma="youtube", agora=None):
    agora = agora or dt.datetime.now(dt.timezone.utc)
    stats = ficha.get('yt_stats' if plataforma == 'youtube' else 'tt_stats') or {}
    publicado = ficha.get('youtube_quando') if plataforma == 'youtube' else ficha.get('tiktok_quando') or stats.get('data')
    if not publicado or stats.get('views') is None:
        return
    try:
        bruto=str(publicado).strip()
        try:data = dt.datetime.fromisoformat(bruto.replace('Z', '+00:00'))
        except ValueError:
            data=next((dt.datetime.strptime(bruto,fmt) for fmt in ('%d/%m/%Y %H:%M:%S','%d/%m/%Y %H:%M') if _data_valida(bruto,fmt)),None)
            if data is None:return
        if plataforma=='tiktok' and len(bruto)<=10:return  # Dia sem horário não define uma janela de 24h.
        if data.tzinfo is None:
            data = data.astimezone()
        idade = (agora-data).total_seconds()/3600
    except (ValueError, TypeError):
        return
    if idade < 0:
        return
    historico = ficha.setdefault('medicoes', {}).setdefault(plataforma, [])
    if not historico or idade-historico[-1]['idade_h'] >= 0.25:
        historico.append(dict(idade_h=round(idade, 3), views=int(stats['views'])))
        ficha['medicoes'][plataforma] = historico[-96:]
    janela = [m for m in ficha['medicoes'][plataforma] if 24 <= m['idade_h'] <= 30]
    if janela:
        ficha.setdefault('views_24h', {})[plataforma] = min(janela, key=lambda m:m['idade_h'])['views']


def views_comparaveis(ficha, plataforma='youtube'):
    return (ficha.get('views_24h') or {}).get(plataforma)


def salvar(mp4: Path, ficha: dict):
    registrar_medicao(ficha)
    registrar_medicao(ficha, "tiktok")
    salvar_json(mp4.with_suffix(".json"), ficha)


def views_de(f: dict) -> int:
    return int((f.get("yt_stats") or {}).get("views", 0)) + int((f.get("tt_stats") or {}).get("views", 0))


def data_post(f: dict):
    q = f.get("youtube_quando") or (f.get("tt_stats") or {}).get("data") or f.get("criado")
    try:
        valor=dt.datetime.fromisoformat(str(q).replace("Z","+00:00"))
        return valor.astimezone() if valor.tzinfo else valor
    except ValueError:
        return None


# ---------------- YouTube ----------------
def atualizar_youtube(log=print):
    """Puxa views/likes/comentários (Data API) e retenção (Analytics API) dos Shorts postados."""
    import postagem
    from googleapiclient.discovery import build
    todos = [(m, f) for m, f in fichas() if f.get("youtube_id")]
    if not todos:
        log("Nenhum corte postado no YouTube pelo programa ainda.")
        return 0
    por_perfil = {}
    for m, f in todos:
        por_perfil.setdefault(f.get("perfil") or "Padrão", []).append((m, f))
    atualizados = 0
    canais = {}
    for perfil, itens in por_perfil.items():
        try:
            cred = postagem.credenciais_leitura(perfil)
        except Exception as e:
            log(f"⚠ perfil {perfil}: {e}")
            continue
        yt = build("youtube", "v3", credentials=cred, cache_discovery=False)
        for i in range(0, len(itens), 50):
            lote = itens[i:i + 50]
            r = yt.videos().list(part="statistics,status", id=",".join(f["youtube_id"] for _, f in lote)).execute()
            dados = {v["id"]: v for v in r.get("items", [])}
            for m, f in lote:
                v = dados.get(f["youtube_id"])
                if not v:
                    continue
                st = v.get("statistics", {})
                f["yt_stats"] = dict(f.get("yt_stats") or {}, views=int(st.get("viewCount", 0) or 0),
                                     likes=int(st.get("likeCount", 0) or 0),
                                     comentarios=int(st.get("commentCount", 0) or 0),
                                     privacidade=v.get("status", {}).get("privacyStatus"),
                                     atualizado=dt.datetime.now().isoformat(timespec="minutes"))
                salvar(m, f)
                atualizados += 1
        # retenção (precisa da 'YouTube Analytics API' ativada no projeto do Google Cloud)
        try:
            an = build("youtubeAnalytics", "v2", credentials=cred, cache_discovery=False)
            ids = [f["youtube_id"] for _, f in itens]
            for i in range(0, len(ids), 150):
                r = an.reports().query(ids="channel==MINE", startDate="2020-01-01",
                                       endDate=dt.date.today().isoformat(),
                                       metrics="views,averageViewPercentage,averageViewDuration",
                                       dimensions="video", filters="video==" + ",".join(ids[i:i + 150])).execute()
                ret = {row[0]: row for row in r.get("rows", [])}
                for m, f in itens:
                    row = ret.get(f["youtube_id"])
                    if row:
                        f["yt_stats"] = dict(f.get("yt_stats") or {}, retencao=round(float(row[2]), 1),
                                             tempo_medio=round(float(row[3]), 1))
                        salvar(m, f)
        except Exception as e:
            log(f"   (retenção indisponível — ative a 'YouTube Analytics API' no Google Cloud: {str(e)[:90]})")
        try:
            c = yt.channels().list(part="statistics,snippet", mine=True).execute().get("items", [])
            if c:
                canais[perfil] = {"nome": c[0]["snippet"]["title"],
                                  "inscritos": int(c[0]["statistics"].get("subscriberCount", 0) or 0),
                                  "views": int(c[0]["statistics"].get("viewCount", 0) or 0)}
        except Exception:
            pass
    if canais:
        _salvar_extra({"canais_youtube": canais})
    log(f"✅ {atualizados} corte(s) atualizados com os números do YouTube.")
    gerar_aprendizado()
    return atualizados


# ---------------- TikTok ----------------
def _ler_tabela(arquivo: Path):
    if arquivo.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        ws = load_workbook(arquivo, read_only=True, data_only=True).active
        linhas = [[("" if c is None else str(c)) for c in row] for row in ws.iter_rows(values_only=True)]
    else:
        texto = arquivo.read_text(encoding="utf-8-sig", errors="replace")
        dialeto = csv.Sniffer().sniff(texto[:5000], delimiters=",;\t") if texto.strip() else csv.excel
        linhas = list(csv.reader(texto.splitlines(), dialeto))
    # acha a linha de cabeçalho (a primeira que tem algo parecido com "views"/"visualizações")
    for i, l in enumerate(linhas[:15]):
        if any(re.search(r"view|visualiz|reprodu|plays", c, re.I) for c in l):
            return [c.strip() for c in l], linhas[i + 1:]
    return (linhas[0] if linhas else []), linhas[1:]


def _coluna(cab, *padroes):
    for p in padroes:
        for i, c in enumerate(cab):
            if re.search(p, c, re.I):
                return i
    return None


def _numero(txt):
    t = str(txt).strip().upper().replace(" ", "")
    mult = 1
    if t.endswith("K") or t.endswith("MIL"):
        mult, t = 1000, t.rstrip("K").replace("MIL", "")
    elif t.endswith("M"):
        mult, t = 1_000_000, t.rstrip("M")
    t = t.replace(".", "").replace(",", ".") if "," in t else t.replace(",", "")
    try:
        return int(float(t) * mult)
    except ValueError:
        return 0


def _parecido(a, b):
    pa = {w for w in re.findall(r"[a-zà-ú0-9]+", a.lower()) if len(w) >= 3}
    pb = {w for w in re.findall(r"[a-zà-ú0-9]+", b.lower()) if len(w) >= 3}
    return len(pa & pb) / max(1, min(len(pa), len(pb))) if pa and pb else 0


def importar_tiktok(arquivo, log=print):
    """Lê o relatório do TikTok Studio e liga cada linha ao corte pelo título/legenda."""
    cab, linhas = _ler_tabela(Path(arquivo))
    c_txt = _coluna(cab, r"title|t[ií]tulo|descri|caption|legenda|v[ií]deo$")
    c_views = _coluna(cab, r"video views|visualiza|views|reprodu|plays")
    c_24h = _coluna(cab, r"24.?h|first.?24|primeiras.?24")
    if c_views==c_24h and c_24h is not None:
        outra=_coluna([c if i!=c_24h else "" for i,c in enumerate(cab)],r"video views|visualiza|views|reprodu|plays")
        if outra is not None:c_views=outra
    c_likes = _coluna(cab, r"like|curtid")
    c_coment = _coluna(cab, r"comment|coment")
    c_data = _coluna(cab, r"date|data|posted|publica")
    if c_views is None or c_txt is None:
        log("❌ Não achei as colunas de título e de visualizações nesse arquivo.")
        return 0
    todos = fichas()
    ligados = 0
    for l in linhas:
        if len(l) <= max(c_txt, c_views):
            continue
        texto = l[c_txt]
        if not texto.strip():
            continue
        melhor, nota, segundo = None, 0, 0
        for m, f in todos:
            n = max(_parecido(texto, f.get("titulo", "")), _parecido(texto, f.get("pergunta", "")))
            if n > nota:
                segundo=nota
                melhor, nota = (m, f), n
            else:segundo=max(segundo,n)
        if melhor and nota >= .5 and nota-segundo<.15:
            log(f"   Linha ambígua, não importada: {texto[:70]}")
            continue
        if melhor and nota >= 0.5:
            m, f = melhor
            f["tt_stats"] = {"views": _numero(l[c_views]),
                             "likes": _numero(l[c_likes]) if c_likes is not None and c_likes < len(l) else 0,
                             "comentarios": _numero(l[c_coment]) if c_coment is not None and c_coment < len(l) else 0,
                             "data": l[c_data] if c_data is not None and c_data < len(l) else "",
                             "fonte": "relatório"}
            if c_24h is not None and c_24h<len(l):f.setdefault("views_24h",{})["tiktok"]=_numero(l[c_24h])
            f["tiktok"] = True
            salvar(m, f)
            ligados += 1
    log(f"✅ {ligados} corte(s) ligados ao relatório do TikTok (de {len(linhas)} linhas).")
    gerar_aprendizado()
    return ligados


def views_manual(mp4: Path, plataforma: str, views: int):
    f = json.loads(Path(mp4).with_suffix(".json").read_text(encoding="utf-8"))
    chave = "tt_stats" if plataforma == "tiktok" else "yt_stats"
    f[chave] = dict(f.get(chave) or {}, views=int(views), fonte="manual",
                    atualizado=dt.datetime.now().isoformat(timespec="minutes"))
    if plataforma == "tiktok":
        f["tiktok"] = True
    salvar(Path(mp4), f)
    gerar_aprendizado()


# ---------------- aprendizado ----------------
def _tem_nome(pergunta, titulo):
    """A pergunta cita alguém pelo nome? (palavra com maiúscula no meio do título que aparece na pergunta)"""
    palavras = re.findall(r"\b[A-ZÁÉÍÓÚ][a-záéíóúãõç]{2,}\b", titulo or "")[1:]
    p = (pergunta or "").upper()
    return any(w.upper() in p for w in palavras)


def _grupos(itens):
    """Divide os cortes em grupos comparáveis. itens = [(views, ficha)]."""
    g = {}

    def add(chave, rotulo, v):
        g.setdefault(chave, {}).setdefault(rotulo, []).append(v)
    for v, f in itens:
        p = f.get("pergunta", "")
        add("Tamanho da pergunta", "curta (até 35 letras)" if len(p) <= 35 else "longa (mais de 35 letras)", v)
        add("Nome na pergunta", "com nome de alguém" if _tem_nome(p, f.get("titulo", "")) else "sem nome", v)
        add("Formato da pergunta", "termina com ??" if p.strip().endswith("??") else "afirmação/sem ??", v)
        if f.get("formato_faixa"):
            add("Formato da faixa", f["formato_faixa"], v)
        if f.get("template"):
            add("Template de edição", f["template"], v)
        if f.get("tom"):
            add("Tom do corte", f["tom"], v)
        if (f.get("ia") or {}).get("modelo"):
            add("Modelo da IA", f["ia"]["modelo"], v)
        if f.get("canal"):
            add("Canal de origem", f["canal"], v)
        d = f.get("duracao") or 0
        if d:
            add("Duração", "até 45s" if d <= 45 else "46 a 70s" if d <= 70 else "mais de 70s", v)
        q = data_post(f)
        if q and f.get("youtube_quando"):
            add("Horário de postagem", f"{q.hour:02d}h", v)
    return g


def desempenho_templates(perfil=None):
    """{template: {"n": cortes, "indice": mediana das views relativas}} — cada corte é comparado com a
    mediana do mesmo perfil e da mesma plataforma (janela de 24–30h), então canal grande não distorce."""
    por_estrato = {}
    for _, f in fichas():
        if not f.get("template") or f.get("idioma", "pt") != "pt":
            continue
        if perfil is not None and (f.get("perfil") or "Padrão") != perfil:
            continue
        for plataforma in ("youtube", "tiktok"):
            v = views_comparaveis(f, plataforma)
            if isinstance(v, (int, float)) and v > 0:
                por_estrato.setdefault((f.get("perfil") or "Padrão", plataforma), []).append((v, f["template"]))
    relativos = {}
    for amostra in por_estrato.values():
        if len(amostra) < 6:
            continue
        mediana = statistics.median(v for v, _ in amostra) or 1
        for v, tpl in amostra:
            relativos.setdefault(tpl, []).append(v / mediana)
    return {tpl: {"n": len(vs), "indice": round(statistics.median(vs), 3)} for tpl, vs in relativos.items()}


def gerar_aprendizado(minimo_por_grupo=5, perfil=None, salvar_arquivo=True, plataforma="youtube"):
    itens = [(views_comparaveis(f,plataforma), f) for _, f in fichas()
             if views_comparaveis(f,plataforma) is not None and f.get("idioma", "pt") == "pt"
             and (perfil is None or (f.get("perfil") or "Padrão") == perfil)]
    linhas = []
    if len(itens) >= 6:
        mediana_geral = statistics.median(v for v, _ in itens) or 1
        estratos = {}
        for v, f in itens:
            chave = (f.get('perfil', 'Padrão'), f.get('canal', ''), int((f.get('duracao') or 0)//30))
            estratos.setdefault(chave, []).append((v, f))
        comparacoes = {}
        for chave, amostra in estratos.items():
            for tema, grupos in _grupos(amostra).items():
                comparacoes[f"{tema} [{chave[0]} / {chave[1]} / faixa {chave[2]*30}s]"] = grupos
        for tema, grupos in comparacoes.items():
            validos = {r: vs for r, vs in grupos.items() if len(vs) >= minimo_por_grupo}
            if len(validos) < 2:
                continue
            medianas = {r: statistics.median(vs) for r, vs in validos.items()}
            melhor = max(medianas, key=medianas.get)
            pior = min(medianas, key=medianas.get)
            suporte=contraste(validos[melhor],validos[pior],max(5,minimo_por_grupo))
            if suporte["conclusivo"] and medianas[pior] > 0 and medianas[melhor] / medianas[pior] >= 1.4:
                linhas.append(f"{tema}: '{melhor}' teve {medianas[melhor] / medianas[pior]:.1f}x mais views "
                              f"que '{pior}' na janela de 24–30h (associação observada, não prova causal).")
        # Compara notas somente dentro de estratos equivalentes e com amostra suficiente.
        for chave,amostra in estratos.items():
            com_nota=[(v,f['nota']) for v,f in amostra if isinstance(f.get('nota'),(int,float))]
            altas=[v for v,n in com_nota if n>=7];baixas=[v for v,n in com_nota if n<7]
            if len(altas)>=8 and len(baixas)>=8 and statistics.median(baixas)>statistics.median(altas):
                if contraste(baixas,altas)['conclusivo']:
                    linhas.append(f'Notas editoriais [{chave[0]}/{chave[1]}]: nesta amostra equivalente, notas menores tiveram mais views; revisar os critérios, sem inferir causalidade.')
        ordenados = sorted(itens, key=lambda x: -x[0])
        bons = list(dict.fromkeys(f.get("pergunta") for v, f in ordenados[:8]
                                  if v >= mediana_geral and f.get("pergunta")))[:5]
        ruins = [f.get("pergunta") for v, f in ordenados[-3:] if v < mediana_geral and f.get("pergunta")]
    else:
        bons, ruins = [], []
    ab = comparar_ab(perfil,plataforma)
    venc = [r["vencedora"] for r in ab if r.get("vencedora")]
    dados = {"atualizado": dt.datetime.now().isoformat(timespec="minutes"), "cortes_com_numeros": len(itens),
             "linhas": linhas, "bons": bons, "ruins": ruins, "ab_vencedoras": venc[-5:]}
    if perfil is None:
        perfis = set(f.get('perfil') or 'Padrão' for _,f in fichas())
        dados['por_perfil'] = {p:gerar_aprendizado(minimo_por_grupo, p, False, plataforma) for p in perfis}
    dados["plataforma"]=plataforma
    if salvar_arquivo and plataforma=="youtube":
        dados["por_plataforma"]={"youtube":dict(dados),"tiktok":gerar_aprendizado(minimo_por_grupo,perfil,False,"tiktok")}
    if salvar_arquivo:
        from infraestrutura import salvar_json
        salvar_json(ARQ_APRENDIZADO, dados)
    return dados


def aprendizado():
    try:
        return json.loads(ARQ_APRENDIZADO.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def aprendizado_para_prompt():
    """Texto curto (~100-200 tokens) que vai junto pra IA."""
    raiz=aprendizado()
    import cortes
    partes=[]
    for plataforma,dados in raiz.get('por_plataforma',{'youtube':raiz}).items():
        a=dados.get('por_perfil',{}).get(cortes.PERFIL_EM_USO,{}) if 'por_perfil' in dados else dados
        linhas=[l for l in a.get('linhas',[]) if not l.startswith(('Canal de origem','Horário'))][:3]
        partes.extend(f'{plataforma}: {linha}' for linha in linhas)
        if a.get('bons'):partes.append(f"{plataforma}, exemplos observados (não regra causal): "+' | '.join(a['bons'][:2]))
        if a.get('ab_vencedoras'):partes.append(f"{plataforma}, A/B repetido: "+' | '.join(a['ab_vencedoras'][:2]))
    try:
        from editorial import memoria
        partes.extend(memoria()[:3])
    except (OSError, ValueError):
        pass
    return "\n".join(f"- {p}" for p in partes)


# ---------------- horário inteligente ----------------
def melhores_horarios(perfil=None, minimo_total=15, minimo_hora=4, plataforma="youtube"):
    """Horas que mais deram views pra esse perfil. Devolve [(hora, mediana, n), ...] (melhor primeiro)
    ou [] se ainda não tem dados suficientes."""
    por_hora, total, registros = {}, 0, []
    for _, f in fichas():
        if perfil and (f.get("perfil") or "Padrão") != perfil:
            continue
        v, q = views_comparaveis(f,plataforma), data_post(f) if plataforma=="youtube" else _data_tiktok(f)
        if v is None or v <= 0 or not q or (plataforma=="youtube" and not f.get("youtube_quando")) or f.get("idioma", "pt") != "pt":
            continue
        registros.append((q.hour,v,(f.get("canal",""),int((f.get("duracao") or 0)//30))))
        total += 1
    if total < minimo_total:
        return []
    estratos={}
    for h,v,chave in registros:estratos.setdefault(chave,[]).append(v)
    for h,v,chave in registros:
        if len(estratos[chave])>=minimo_hora:
            por_hora.setdefault(h,[]).append(v/max(1,statistics.median(estratos[chave])))
    ranking = [(h, statistics.median(vs), len(vs)) for h, vs in por_hora.items() if len(vs) >= minimo_hora]
    ranking=sorted(ranking,key=lambda x:-x[1])
    if len(ranking)<2:return []
    from estatistica_editorial import contraste
    melhor=ranking[0][0]
    if not any(contraste(por_hora[melhor],por_hora[h],minimo_hora)['conclusivo'] for h,_,_ in ranking[1:]):return []
    return ranking


def horarios_inteligentes(perfil, base):
    """Troca os horários do perfil pelos que mais deram views, mas sempre deixa 1 horário 'teste'
    da lista original (assim ele continua aprendendo). Sem dados suficientes = devolve a base."""
    base = list(base or ["12:00", "18:00", "21:00"])
    ranking = melhores_horarios(perfil)
    if len(ranking) < 2:
        return base
    n = max(2, len(base))
    escolhidos = [f"{h:02d}:00" for h, _, _ in ranking[:n - 1]]
    testadas = {h for h, _, _ in ranking}
    teste = next((b for b in base if int(b.split(":")[0]) not in testadas), None)
    if not teste:
        teste = f"{ranking[n - 1][0]:02d}:00" if len(ranking) >= n else None
    if teste and teste not in escolhidos:
        escolhidos.append(teste)
    return sorted(escolhidos)


# ---------------- painel ----------------
def comparar_ab(perfil=None,plataforma="youtube"):
    grupos = {}
    for _, f in fichas():
        if f.get("grupo_ab") and (perfil is None or (f.get("perfil") or "Padrão") == perfil):
            grupos.setdefault(f["grupo_ab"], {})[f.get("variante", "A")] = f
    saida = []
    for g, var in grupos.items():
        if "A" in var and "B" in var:
            if (var['A'].get('perfil') or 'Padrão') != (var['B'].get('perfil') or 'Padrão'):
                continue
            va, vb = views_comparaveis(var['A'],plataforma), views_comparaveis(var['B'],plataforma)
            if va is None or vb is None:
                continue
            r = {"grupo": g, "a": var["A"].get("pergunta"), "b": var["B"].get("pergunta"), "views_a": va, "views_b": vb}
            r.update(plataforma=plataforma,hipotese=var['A'].get('hipotese_ab'),perfil=var['A'].get('perfil','Padrão'),estado='exploratorio')
            mesma_fonte=all(var['A'].get(k)==var['B'].get(k) for k in ('fonte','inicio','fim'))
            if mesma_fonte and va + vb >= 200 and max(va, vb) >= 1.25 * max(1, min(va, vb)):
                r["sugestao"] = r["a"] if va > vb else r["b"]
                r["variante_sugerida"]="A" if va>vb else "B"
            saida.append(r)
    from calibracao import limite_wilson
    experimentos={}
    for r in saida:
        if r.get('hipotese') and r.get('variante_sugerida'):
            experimentos.setdefault((r['perfil'],r['hipotese']),[]).append(r['variante_sugerida'])
    for r in saida:
        votos=experimentos.get((r['perfil'],r.get('hipotese')),[])
        if len(votos)>=6:
            vencedora=max(('A','B'),key=votos.count)
            if limite_wilson(votos.count(vencedora),len(votos))>.5:
                r.update(estado='replicado',vencedora=r['a'] if vencedora=='A' else r['b'],repeticoes=len(votos))
    return saida


def _data_tiktok(ficha):
    valor=ficha.get('tiktok_quando') or (ficha.get('tt_stats') or {}).get('data')
    if not valor:return None
    try:return dt.datetime.fromisoformat(str(valor).replace('Z','+00:00'))
    except ValueError:
        for fmt in ('%d/%m/%Y %H:%M:%S','%d/%m/%Y %H:%M'):
            if _data_valida(str(valor),fmt):return dt.datetime.strptime(str(valor),fmt)
    return None


def _extra():
    try:
        return json.loads((PASTA / "resultados_extra.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _salvar_extra(d):
    e = _extra()
    e.update(d)
    (PASTA / "resultados_extra.json").write_text(json.dumps(e, indent=2, ensure_ascii=False), encoding="utf-8")


def resumo(dias=14):
    todos = fichas()
    hoje = dt.date.today()
    por_dia = {(hoje - dt.timedelta(days=i)).isoformat(): 0 for i in range(dias - 1, -1, -1)}
    cortes_dia = dict.fromkeys(por_dia, 0)
    total, total30, tt30 = 0, 0, 0
    por_canal = {}
    for _, f in todos:
        v = views_de(f)
        total += v
        q = data_post(f)
        if q:
            k = q.date().isoformat()
            if k in por_dia:
                por_dia[k] += v
            criado = str(f.get("criado", ""))[:10]
            if criado in cortes_dia:
                cortes_dia[criado] += 1
            if (hoje - q.date()).days <= 30:
                total30 += v
                tt30 += int((f.get("tt_stats") or {}).get("views", 0))
        c = f.get("canal") or "?"
        pc = por_canal.setdefault(c, {"cortes": 0, "views": 0})
        pc["cortes"] += 1
        pc["views"] += v
    postados = sum(1 for _, f in todos if f.get("status") == "postado" or f.get("tiktok"))
    top = sorted(todos, key=lambda x: -views_de(x[1]))[:6]
    extra = _extra()
    return {"cortes": len(todos), "postados": postados, "views": total, "views30": total30,
            "tiktok_views30": tt30, "por_dia": por_dia, "cortes_por_dia": cortes_dia,
            "por_canal": sorted(por_canal.items(), key=lambda x: -x[1]["views"])[:6],
            "top": [(m, f, views_de(f)) for m, f in top if views_de(f) > 0],
            "canais_youtube": extra.get("canais_youtube", {}), "ab": comparar_ab()+comparar_ab(plataforma="tiktok")}
