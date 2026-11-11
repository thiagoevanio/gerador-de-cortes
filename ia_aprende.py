"""O que a IA aprende com o uso (3.12), sem gastar nada a mais:

  • Glossário de nomes por canal: toda vez que a IA (ou você, no editor de legenda) corrige um nome
    que o Whisper errou ("Davi Jones" → "Davy Jones"), o nome certo é guardado. Nos próximos cortes
    do mesmo canal ele vai pro Whisper (que passa a acertar já na transcrição) e pra IA (que usa a
    grafia certa na pergunta, no título e nas hashtags).
  • Gosto do dono: quando você troca a pergunta de um corte (✏), a troca é guardada e as últimas vão
    pra IA como exemplo do jeito que você gosta.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path

from infraestrutura import exclusividade, salvar_json

BASE = Path(__file__).resolve().parent
ARQ_GLOSSARIO = BASE / "analises" / "glossario_nomes.json"
ARQ_GOSTO = BASE / "analises" / "gosto_dono.json"
MAX_TERMOS_CANAL = 200

COMUNS = {
    "a", "o", "as", "os", "um", "uma", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas", "ao",
    "pra", "pro", "para", "por", "com", "sem", "que", "se", "mas", "ou", "e", "eu", "ele", "ela", "voce",
    "isso", "esse", "essa", "este", "esta", "entao", "mais", "muito", "tipo", "cara", "mano", "gente", "bom",
    "bem", "olha", "ai", "la", "aqui", "ja", "nao", "sim", "agora", "depois", "quando", "como", "porque",
    "tambem", "so", "tudo", "nada", "foi", "era", "vai", "tem", "ta", "to", "ne", "ok", "beleza", "nossa",
}


def _norm(texto):
    t = unicodedata.normalize("NFKD", str(texto or "").lower())
    return "".join(c for c in t if c.isalnum() and not unicodedata.combining(c))


def _chave(canal):
    return _norm(canal)[:60] or "_geral"


def _limpo(palavra):
    """A palavra sem pontuação nas pontas (mantém o de dentro: iPhone, GTA-6, D'Ávila)."""
    return re.sub(r"^[^\w]+|[^\w]+$", "", str(palavra or ""), flags=re.UNICODE)


def _inicio_de_frase(textos, i):
    if i == 0:
        return True
    anterior = str(textos[i - 1] or "").rstrip()
    return anterior.endswith((".", "!", "?", "…", ":"))


def _parece_nome(palavra):
    return bool(palavra) and (palavra[:1].isupper() or any(c.isdigit() for c in palavra)
                              or any(c.isupper() for c in palavra[1:]))


def _forma_especial(palavra):
    """Maiúscula no meio ou número (iPhone, LOUD, GTA, PS5): não é só começo de frase."""
    return any(c.isupper() for c in palavra[1:]) or any(c.isdigit() for c in palavra)


def extrair_termos(originais, corrigidas, maximo=3):
    """{nome certo: como estava escrito} dos nomes que foram corrigidos (frases de até 3 palavras)."""
    if not originais or len(originais) != len(corrigidas):
        return {}
    n = len(corrigidas)
    limpas = [_limpo(c) for c in corrigidas]
    marcados = set()
    for i in range(n):
        o, c = _limpo(originais[i]), limpas[i]
        if len(c) < 2 or o == c or _norm(c) in COMUNS:
            continue
        inicio = _inicio_de_frase(corrigidas, i)
        if _norm(o) != _norm(c):                       # grafia mudou
            if _forma_especial(c) or (_parece_nome(c) and (not inicio or len(_norm(c)) >= 4)):
                marcados.add(i)
        elif _forma_especial(c) or (c[:1].isupper() and not inicio):   # só maiúscula/acento mudou
            marcados.add(i)
    termos = {}
    usados = set()
    for i in sorted(marcados):
        if i in usados:
            continue
        a = b = i
        while a - 1 >= 0 and b - a + 1 < maximo and (a - 1 in marcados or (
                _parece_nome(limpas[a - 1]) and not _inicio_de_frase(corrigidas, a - 1)
                and _norm(limpas[a - 1]) not in COMUNS)):
            a -= 1
        while b + 1 < n and b - a + 1 < maximo and (b + 1 in marcados or (
                _parece_nome(limpas[b + 1]) and _norm(limpas[b + 1]) not in COMUNS)):
            b += 1
        if any(str(corrigidas[k]).rstrip().endswith((".", "!", "?")) for k in range(a, b)):
            a = b = i                                   # não junta palavras de frases diferentes
        usados.update(range(a, b + 1))
        frase = " ".join(limpas[k] for k in range(a, b + 1) if limpas[k])
        errado = " ".join(_limpo(originais[k]) for k in range(a, b + 1) if _limpo(originais[k]))
        if frase and len(frase) <= 40:
            termos[frase] = errado
    return termos


def _ler(arq):
    try:
        return json.loads(Path(arq).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def aprender_correcoes(canal, originais, corrigidas, fonte="ia", arquivo=None):
    """Guarda os nomes corrigidos. fonte='dono' (você corrigiu no editor) vale na hora;
    fonte='ia' só vale depois de aparecer em 2 cortes (a IA pode errar). Sem canal não aprende: o
    glossário é por canal e um vídeo solto (arquivo sem canal) não tem a quem ensinar."""
    if not str(canal or "").strip():
        return []
    termos = extrair_termos(list(originais or []), list(corrigidas or []))
    if not termos:
        return []
    arq = Path(arquivo or ARQ_GLOSSARIO)
    try:
        arq.parent.mkdir(parents=True, exist_ok=True)
        with exclusividade(arq.with_suffix(".lock"), timeout=10):
            dados = _ler(arq)
            canais = dados.setdefault("canais", {})
            c = canais.setdefault(_chave(canal), {})
            agora = int(time.time())
            for frase, errado in termos.items():
                e = c.setdefault(frase, {"n": 0, "dono": 0, "errados": [], "visto": 0})
                e["n"] += 1
                if fonte == "dono":
                    e["dono"] += 1
                if errado and _norm(errado) != _norm(frase) and errado not in e["errados"]:
                    e["errados"] = (e["errados"] + [errado])[-3:]
                e["visto"] = agora
            if len(c) > MAX_TERMOS_CANAL:              # guarda os mais confirmados e recentes
                ordem = sorted(c.items(), key=lambda kv: (kv[1].get("dono", 0), kv[1].get("n", 0),
                                                          kv[1].get("visto", 0)), reverse=True)
                canais[_chave(canal)] = dict(ordem[:MAX_TERMOS_CANAL])
            salvar_json(arq, dados)
    except Exception:
        return []
    return list(termos)


def termos_confirmados(canal, limite=15, minimo=2, arquivo=None):
    """Nomes que já foram confirmados neste canal (você corrigiu, ou a IA corrigiu em 2+ cortes)."""
    c = _ler(arquivo or ARQ_GLOSSARIO).get("canais", {}).get(_chave(canal), {})
    ok = [(f, e) for f, e in c.items() if e.get("dono") or e.get("n", 0) >= minimo]
    ok.sort(key=lambda kv: (kv[1].get("dono", 0) > 0, kv[1].get("n", 0), kv[1].get("visto", 0)), reverse=True)
    return [f for f, _ in ok[:limite]]


def dica_whisper(canal, limite_chars=160, arquivo=None):
    """'Nomes: A, B, C.' pra frase de vocabulário do Whisper (ele erra menos esses nomes)."""
    nomes, total = [], 0
    for t in termos_confirmados(canal, 25, arquivo=arquivo):
        if total + len(t) + 2 > limite_chars:
            break
        nomes.append(t)
        total += len(t) + 2
    return ("Nomes: " + ", ".join(nomes) + ".") if nomes else ""


# ------------------------------------------------------------------ gosto do dono
def registrar_troca_pergunta(perfil, antes, depois, da_lista=False, arquivo=None):
    """Você trocou a pergunta de um corte: guarda o par (antes → depois)."""
    antes, depois = str(antes or "").strip(), str(depois or "").strip()
    if not depois or antes == depois:
        return False
    arq = Path(arquivo or ARQ_GOSTO)
    try:
        arq.parent.mkdir(parents=True, exist_ok=True)
        with exclusividade(arq.with_suffix(".lock"), timeout=10):
            dados = _ler(arq)
            lista = dados.setdefault(perfil or "Padrão", [])
            lista.append({"antes": antes[:120], "depois": depois[:120], "da_lista": bool(da_lista),
                          "quando": int(time.time())})
            dados[perfil or "Padrão"] = lista[-30:]
            salvar_json(arq, dados)
        return True
    except Exception:
        return False


def gosto_para_prompt(perfil, limite=4, arquivo=None):
    lista = _ler(arquivo or ARQ_GOSTO).get(perfil or "Padrão", [])[-limite:]
    if not lista:
        return ""
    linhas = [f'- trocou "{x["antes"]}" por "{x["depois"]}"' for x in reversed(lista)]
    return ("Gosto do dono deste canal (perguntas que ele preferiu no lugar das sugeridas; siga o tamanho, "
            "o tom e o jeito de escrever, sem copiar o assunto):\n" + "\n".join(linhas))
