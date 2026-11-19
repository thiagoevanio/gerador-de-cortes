"""🤖 IA corta os melhores momentos (extensão, vídeo do YouTube).

A extensão manda o link, quantos cortes, a duração e o que só ela vê na página (os minutos citados nos
comentários e os picos do gráfico "mais repetidos"). Aqui, em segundo plano: o achar momentos com IA
(momentos.achar_momentos, sempre com a IA conferindo) escolhe os trechos com começo e fim nas frases
certas e eles vão pra fila do monitor — cada corte pronto vira aviso no Chrome.
"""
from __future__ import annotations

import math
import re
import threading
import time
import uuid

LINK_YT = re.compile(r"^https://(www\.|m\.)?youtube\.com/watch\?v=[\w-]{6,20}$")
_TRAVA = threading.Lock()
TRABALHOS: dict[str, dict] = {}          # id → estado (o /status mostra os mais recentes)


def _num(v, padrao, minimo, maximo):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return padrao
    return max(minimo, min(maximo, v)) if math.isfinite(v) else padrao


def validar(pedido) -> dict:
    """O que vem da página é dado, não instrução: só passa link do YouTube e números/textos limitados."""
    if not isinstance(pedido, dict):
        raise ValueError("Pedido inválido.")
    url = str(pedido.get("url") or "")
    if not LINK_YT.match(url):
        raise ValueError("Abra um vídeo do YouTube (link youtube.com/watch?v=...).")
    coments = []
    for c in (pedido.get("comentarios") or [])[:20]:
        if isinstance(c, dict):
            t = _num(c.get("t"), -1, -1, 86400)
            if t >= 0:
                textos = [re.sub(r"\s+", " ", str(x))[:200] for x in (c.get("textos") or [])[:3] if str(x).strip()]
                coments.append({"t": t, "n": int(_num(c.get("n"), 1, 1, 999)), "textos": textos})
    picos = [_num(p.get("t") if isinstance(p, dict) else p, -1, -1, 86400) for p in (pedido.get("picos") or [])[:8]]
    return {"url": url, "n": int(_num(pedido.get("n"), 3, 1, 5)), "dur": int(_num(pedido.get("dur"), 60, 20, 120)),
            "titulo": re.sub(r"\s+", " ", str(pedido.get("titulo") or ""))[:150],
            "comentarios": coments, "picos": [p for p in picos if p >= 0]}


def resumo(limite=4) -> list[dict]:
    with _TRAVA:
        itens = sorted(TRABALHOS.values(), key=lambda x: -x["inicio"])[:limite]
        return [{k: v for k, v in x.items() if k != "_log"} for x in itens]


def em_andamento(url=None):
    with _TRAVA:
        return next((x for x in TRABALHOS.values() if x["estado"] == "trabalhando"
                     and (url is None or x["url"] == url)), None)


def iniciar(pedido: dict, enfileirar, achar=None) -> dict:
    """Começa o trabalho em segundo plano e devolve o estado inicial. enfileirar(itens) põe os cortes
    na fila do monitor. Um trabalho por vez (achar momentos é pesado no processador)."""
    p = validar(pedido)
    atual = em_andamento()
    if atual:
        raise ValueError("A IA já está escolhendo momentos de outro vídeo. Espere terminar."
                         if atual["url"] != p["url"] else "A IA já está trabalhando neste vídeo.")
    trabalho = {"id": uuid.uuid4().hex[:10], "url": p["url"], "titulo": p["titulo"], "n": p["n"], "dur": p["dur"],
                "estado": "trabalhando", "etapa": "começando...", "momentos": [], "inicio": time.time(), "fim": None,
                "msg": ""}
    with _TRAVA:
        for k in [k for k, v in TRABALHOS.items() if v["estado"] != "trabalhando"][:-6]:
            TRABALHOS.pop(k, None)                    # guarda só os últimos
        TRABALHOS[trabalho["id"]] = trabalho
    threading.Thread(target=_rodar, args=(trabalho, p, enfileirar, achar), daemon=True,
                     name="ia-momentos-youtube").start()
    return dict(trabalho)


def _rodar(trabalho, p, enfileirar, achar):
    def etapa(txt):
        txt = re.sub(r"\s+", " ", str(txt)).strip()
        if txt:
            trabalho["etapa"] = txt[:140]
    try:
        import cortes
        if achar is None:
            import momentos
            achar = momentos.achar_momentos
        etapa("esperando a vez (o monitor está renderizando)...")
        with cortes.contexto_render():                 # um trabalho pesado por vez no processador
            achados, _meta = achar(p["url"], p["n"], p["dur"], log=etapa, contexto_titulo=p["titulo"],
                                   dicas={"comentarios": p["comentarios"], "picos": p["picos"]}, usar_ia=True)
        achados = [m for m in achados or [] if m.get("fim", 0) - m.get("inicio", 0) >= 5][:p["n"]]
        if not achados:
            trabalho.update(estado="sem_momentos", msg="A IA não achou trechos bons o bastante neste vídeo.")
            return
        trabalho["momentos"] = [{"inicio": round(m["inicio"], 1), "fim": round(m["fim"], 1),
                                 "motivo": str(m.get("motivo", ""))[:160], "nota": m.get("nota_ia")}
                                for m in achados]
        etapa(f"mandando {len(achados)} corte(s) pra fila...")
        r = enfileirar([{"inicio": m["inicio"], "fim": m["fim"], "motivo": m.get("motivo", ""),
                         "url": p["url"], "titulo": p["titulo"]} for m in achados])
        if not (r or {}).get("ok"):
            raise RuntimeError((r or {}).get("msg") or "o monitor não aceitou os cortes")
        trabalho.update(estado="pronto", msg=f"{len(achados)} corte(s) na fila. Você recebe um aviso quando "
                                             "cada um ficar pronto.")
    except Exception as e:                                 # noqa: BLE001 - vira mensagem no painel
        trabalho.update(estado="erro", msg=str(e)[:300] or "erro inesperado")
    finally:
        trabalho["fim"] = time.time()
        trabalho["etapa"] = ""
