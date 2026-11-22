"""📥 Reels do Instagram: baixa os reels de um perfil, no arquivo ORIGINAL (sem a marca d'água que o
botão 'baixar' do app coloca — o mesmo que o cobalt faz).

O Instagram não deixa programa nenhum listar os reels de um perfil (o yt-dlp falha no perfil). Quem lista
é a extensão do Chrome: ela rola a página do perfil no SEU navegador e junta os links. Aqui cada reel é
baixado sozinho (isso funciona sem login, pra conta pública), com pausa entre um e outro pra não ser
bloqueado, e o que já foi baixado não baixa de novo.
"""
from __future__ import annotations

import json
import random
import re
import threading
import time
import uuid
from pathlib import Path

import cortes

RE_USUARIO = re.compile(r"^[A-Za-z0-9._]{1,30}$")
RE_REEL = re.compile(r"/(?:reel|reels|p|tv)/([A-Za-z0-9_-]{5,40})")
_TRAVA = threading.Lock()
TRABALHOS: dict[str, dict] = {}
_PARAR: set[str] = set()


def pasta_base() -> Path:
    return Path(cortes.PASTA_SAIDA).resolve().parent / "reels_instagram"


def usuario_valido(u) -> str:
    u = str(u or "").strip().lstrip("@").strip("/")
    if not RE_USUARIO.match(u) or u.lower() in ("reel", "reels", "p", "explore", "accounts", "stories"):
        raise ValueError("@ inválido.")
    return u


def ids_dos_links(links, limite=500) -> list[str]:
    """Links (ou caminhos) de reel/post → ids únicos, na ordem em que vieram."""
    vistos = []
    for l in links or []:
        m = RE_REEL.search(str(l))
        if m and m.group(1) not in vistos:
            vistos.append(m.group(1))
        if len(vistos) >= limite:
            break
    return vistos


RE_TEMPORARIO = re.compile(r"^~[0-9a-f]{8}_(.+)$")     # nome de passagem do organizar()


def _id_do_arquivo(p: Path) -> str:
    """'ID.mp4', '007 - 2026-11-19 - ID.mp4' ou o nome de passagem '~1a2b3c4d_ID.mp4' → ID."""
    m = RE_TEMPORARIO.match(p.stem)
    return m.group(1) if m else p.stem.rsplit(" - ", 1)[-1]


def arquivo_do_reel(pasta: Path, rid: str):
    """O .mp4 desse reel na pasta, com qualquer um dos nomes que ele pode ter."""
    antigo = pasta / f"{rid}.mp4"
    if antigo.exists():
        return antigo
    return next((p for p in pasta.glob("*.mp4") if _id_do_arquivo(p) == rid), None)


def _ja_baixados(pasta: Path) -> set[str]:
    return {_id_do_arquivo(p) for p in pasta.glob("*.mp4")}


def _quando(dados: dict) -> float:
    """Momento da postagem (segundos). Sem a hora exata, usa o dia."""
    if dados.get("timestamp"):
        try:
            return float(dados["timestamp"])
        except (TypeError, ValueError):
            pass
    try:
        import datetime
        return datetime.datetime.strptime(str(dados.get("data")), "%Y%m%d").timestamp()
    except (TypeError, ValueError):
        return 0.0


def organizar(pasta: Path) -> int:
    """Renomeia os reels da pasta do MAIS RECENTE pro mais antigo: '001 - 2026-11-19 - ID.mp4' (o 001 é
    sempre o mais novo; chegou reel novo, renumera). Também põe a data de modificação do arquivo = data da
    postagem. Assim a pasta fica em ordem no Windows, por nome ou por data. Devolve quantos organizou.

    Se um vídeo estiver aberto no player (o Windows não deixa renomear), desfaz o que já tinha mexido e
    avisa com OSError: a pasta continua como estava e organiza da próxima vez."""
    import os
    indice = _indice(pasta)
    presentes = []
    for ordem, (rid, dados) in enumerate(indice.items()):
        arq = arquivo_do_reel(pasta, rid)
        if arq:
            presentes.append((-_quando(dados), ordem, rid, arq))   # empate: a ordem em que veio (mais nova antes)
    presentes.sort()
    largura = max(3, len(str(len(presentes))))
    planos = []                                        # (rid, arquivo atual, nome final, quando)
    for n, (_q, _o, rid, arq) in enumerate(presentes, 1):
        quando = _quando(indice[rid])
        dia = time.strftime("%Y-%m-%d", time.localtime(quando)) if quando else "sem-data"
        if quando and not indice[rid].get("timestamp"):  # só o dia: meio-dia, um segundo a menos por posição
            quando += 43200 - n                        # (no mesmo dia, o mais novo continua na frente)
        planos.append((rid, arq, pasta / f"{n:0{largura}d} - {dia} - {rid}.mp4", quando))
    # 2 passos (nome de passagem, depois o final) só pra quem muda de nome: sem colisão entre eles
    mudar = [(rid, arq, final) for rid, arq, final, _ in planos if arq.name != final.name]
    passagem = []
    try:
        for rid, arq, final in mudar:
            tmp = arq.with_name(f"~{uuid.uuid4().hex[:8]}_{rid}.mp4")
            arq.rename(tmp)
            passagem.append((arq, tmp, final))
    except OSError:
        for arq, tmp, _ in reversed(passagem):         # desfaz: ninguém fica com nome de passagem
            try:
                tmp.rename(arq)
            except OSError:
                pass                                   # (se nem isso der, o nome de passagem é reconhecido)
        raise
    for _arq, tmp, final in passagem:
        tmp.rename(final)
    for rid, _arq, final, quando in planos:
        indice[rid]["arquivo"] = final.name
        if quando:
            try:
                os.utime(final, (quando, quando))
            except OSError:
                pass
    if presentes:
        (pasta / "reels.json").write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(presentes)


def _indice(pasta: Path) -> dict:
    try:
        return json.loads((pasta / "reels.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def baixar_um(rid: str, pasta: Path) -> dict:
    """Um reel, na melhor qualidade, já em .mp4. Devolve os dados dele (legenda, data, duração...)."""
    import yt_dlp
    import baixador
    opcoes = baixador.opcoes_ytdlp(outtmpl=str(pasta / "%(id)s.%(ext)s"), quiet=True, no_warnings=True,
                                   noprogress=True, format="bv*+ba/b", merge_output_format="mp4")
    with yt_dlp.YoutubeDL(opcoes) as y:
        info = y.extract_info(f"https://www.instagram.com/reel/{rid}/", download=True)
    arq = pasta / f"{info.get('id') or rid}.mp4"
    if not arq.exists():
        achados = list(pasta.glob(f"{rid}.*"))
        if not achados:
            raise RuntimeError("o arquivo não apareceu depois do download")
        arq = achados[0]
    return {"id": rid, "arquivo": arq.name, "url": f"https://www.instagram.com/reel/{rid}/",
            "legenda": (info.get("description") or "")[:2000], "data": info.get("upload_date"),
            "timestamp": info.get("timestamp"),
            "duracao": info.get("duration"), "largura": info.get("width"), "altura": info.get("height")}


def _bloqueio(texto: str) -> bool:
    t = texto.lower()
    return any(m in t for m in ("login required", "rate-limit", "rate limit", "429", "please wait a few minutes",
                                "checkpoint", "challenge_required", "not available"))


def resumo(limite=4) -> list[dict]:
    with _TRAVA:
        itens = sorted(TRABALHOS.values(), key=lambda x: -x["inicio"])[:limite]
        return [dict(x) for x in itens]


def parar(tid: str) -> bool:
    if tid in TRABALHOS and TRABALHOS[tid]["estado"] == "baixando":
        _PARAR.add(tid)
        return True
    return False


def iniciar(usuario, links, baixar=None, pausa=(2.0, 5.0)) -> dict:
    """Começa a baixar em segundo plano. Um perfil por vez (pra não chamar atenção do Instagram)."""
    usuario = usuario_valido(usuario)
    ids = ids_dos_links(links)
    if not ids:
        raise ValueError("Não achei nenhum link de reel nesse perfil.")
    with _TRAVA:
        if any(x["estado"] == "baixando" for x in TRABALHOS.values()):
            raise ValueError("Já tem um perfil sendo baixado. Espere terminar (ou pare ele).")
    pasta = pasta_base() / usuario
    pasta.mkdir(parents=True, exist_ok=True)
    ja = _ja_baixados(pasta)
    trabalho = {"id": uuid.uuid4().hex[:10], "usuario": usuario, "pasta": str(pasta), "estado": "baixando",
                "total": len(ids), "feitos": 0, "pulados": sum(1 for i in ids if i in ja), "falhas": 0,
                "atual": "", "msg": "", "inicio": time.time(), "fim": None}
    with _TRAVA:
        for k in [k for k, v in TRABALHOS.items() if v["estado"] != "baixando"][:-6]:
            TRABALHOS.pop(k, None)
        TRABALHOS[trabalho["id"]] = trabalho
    threading.Thread(target=_rodar, args=(trabalho, [i for i in ids if i not in ja], pasta, baixar or baixar_um,
                                          pausa), daemon=True, name="instagram-reels").start()
    return dict(trabalho)


def _rodar(trabalho, ids, pasta, baixar, pausa):
    seguidas = 0
    indice = _indice(pasta)
    try:
        for n, rid in enumerate(ids, 1):
            if trabalho["id"] in _PARAR:
                trabalho["msg"] = "Parado por você."
                break
            trabalho["atual"] = rid
            try:
                dados = baixar(rid, pasta)
                indice[rid] = dados
                trabalho["feitos"] += 1
                seguidas = 0
            except Exception as e:                       # noqa: BLE001 - um reel ruim não para os outros
                trabalho["falhas"] += 1
                seguidas += 1
                texto = str(e)
                if _bloqueio(texto) and seguidas >= 3:
                    trabalho["msg"] = ("O Instagram começou a bloquear (pediu login ou limitou). O que já baixou "
                                       "ficou salvo — tente o resto mais tarde; os baixados não baixam de novo.")
                    break
            (pasta / "reels.json").write_text(json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8")
            if n < len(ids) and pausa:
                time.sleep(random.uniform(*pausa))       # ritmo de gente, não de robô
        if not trabalho["msg"]:
            partes = [f"{trabalho['feitos']} baixado(s)"]
            if trabalho["pulados"]:
                partes.append(f"{trabalho['pulados']} já tinha(m)")
            if trabalho["falhas"]:
                partes.append(f"{trabalho['falhas']} falha(s)")
            trabalho["msg"] = ", ".join(partes) + "."
        trabalho["estado"] = "pronto"
    except Exception as e:                               # noqa: BLE001
        trabalho.update(estado="erro", msg=str(e)[:300])
    finally:
        try:
            trabalho["atual"] = "organizando a pasta do mais recente pro mais antigo..."
            organizar(pasta)
        except OSError:
            if trabalho.get("msg"):                      # vídeo aberto no player: organiza na próxima
                trabalho["msg"] += " (Feche o vídeo que está aberto pra pasta ficar em ordem — arruma na próxima.)"
        trabalho["fim"] = time.time()
        trabalho["atual"] = ""
        _PARAR.discard(trabalho["id"])
