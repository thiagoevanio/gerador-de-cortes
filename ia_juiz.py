"""Juiz local das respostas da IA (3.12): confere sem gastar nada o que a IA escreveu.

  • a pergunta da faixa é genérica ("VOCÊ VIU ISSO??") ou cita algo do trecho?
  • tem número que não aparece no trecho (número inventado)?
  • tamanho bom pra faixa?
Se a pergunta principal vier fraca e uma das alternativas for claramente melhor, troca.
Também limpa título, hashtags e o destaque da faixa.
"""
from __future__ import annotations

import re
import unicodedata

COMUNS = {
    "A", "O", "AS", "OS", "UM", "UMA", "UNS", "UMAS", "DE", "DO", "DA", "DOS", "DAS", "EM", "NO", "NA", "NOS",
    "NAS", "AO", "AOS", "PRA", "PRO", "PARA", "POR", "PELO", "PELA", "COM", "SEM", "QUE", "QUEM", "QUAL", "COMO",
    "QUANDO", "ONDE", "PORQUE", "SE", "MAS", "OU", "E", "NEM", "JA", "NAO", "SIM", "MAIS", "MENOS",
    "MUITO", "MUITA", "POUCO", "TUDO", "NADA", "ALGO", "ISSO", "ISTO", "AQUILO", "ESSE", "ESSA", "ESTE", "ESTA",
    "AQUELE", "AQUELA", "ELE", "ELA", "ELES", "ELAS", "VOCE", "VOCES", "EU", "NOS", "TU", "SEU", "SUA", "SEUS",
    "SUAS", "MEU", "MINHA", "DELE", "DELA", "LHE", "ME", "TE", "FOI", "ERA", "SER", "TER", "TEM", "TINHA", "VAI",
    "VAO", "VAI", "IA", "FAZ", "FEZ", "FAZER", "ESTA", "ESTAO", "ESTAVA", "FICA", "FICOU", "DIZ", "DISSE",
    "FALOU", "FALA", "VIU", "VER", "OLHA", "VEJA", "AGORA", "AINDA", "DEPOIS", "ANTES", "SEMPRE", "NUNCA",
    "AQUI", "ALI", "LA", "ENTAO", "ASSIM", "TAMBEM", "SO", "BEM", "MAL", "CADA", "TODO", "TODA", "TODOS",
    "TODAS", "OUTRO", "OUTRA", "MESMO", "MESMA", "ATE", "SOBRE", "ENTRE", "VEZ", "COISA", "GENTE", "CARA",
    "MANO", "TIPO", "NE", "AI", "EH", "SERA", "SERIO", "REAL", "VERDADE", "ACONTECEU", "ACONTECE", "ISSO",
}
GENERICAS = [
    "VOCE VIU ISSO", "VIU ISSO", "OLHA ISSO", "OLHA ESSA", "OLHA ESSE", "VEJA ISSO", "INACREDITAVEL",
    "ELE FALOU ISSO", "ELA FALOU ISSO", "ELE DISSE ISSO", "OLHA O QUE ELE FEZ", "OLHA O QUE ACONTECEU",
    "VOCE NAO VAI ACREDITAR", "NINGUEM ESPERAVA", "QUE ISSO", "E AGORA", "ISSO E SERIO", "ACONTECEU DE NOVO",
    "SERA QUE", "OLHA SO", "CHOCANTE", "ABSURDO", "MEU DEUS", "QUE LOUCURA", "DEU RUIM", "E AI",
]
_EXTENSO = {
    "ZERO": 0, "UM": 1, "UMA": 1, "DOIS": 2, "DUAS": 2, "TRES": 3, "QUATRO": 4, "CINCO": 5, "SEIS": 6,
    "SETE": 7, "OITO": 8, "NOVE": 9, "DEZ": 10, "ONZE": 11, "DOZE": 12, "TREZE": 13, "CATORZE": 14,
    "QUATORZE": 14, "QUINZE": 15, "DEZESSEIS": 16, "DEZESSETE": 17, "DEZOITO": 18, "DEZENOVE": 19,
    "VINTE": 20, "TRINTA": 30, "QUARENTA": 40, "CINQUENTA": 50, "SESSENTA": 60, "SETENTA": 70, "OITENTA": 80,
    "NOVENTA": 90, "CEM": 100, "CENTO": 100, "DUZENTOS": 200, "TREZENTOS": 300, "QUATROCENTOS": 400,
    "QUINHENTOS": 500, "SEISCENTOS": 600, "SETECENTOS": 700, "OITOCENTOS": 800, "NOVECENTOS": 900,
    "MIL": 1000, "PRIMEIRO": 1, "SEGUNDO": 2, "TERCEIRO": 3, "QUARTO": 4, "QUINTO": 5,
}
NOTA_BOA = 45          # abaixo disso a pergunta é considerada fraca
NOTA_RUIM = 35         # abaixo disso: falha (genérica, sem ligação com o trecho ou com número inventado)


def sem_acento(texto):
    t = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in t if not unicodedata.combining(c))


def tokens(texto):
    """Palavras em MAIÚSCULAS, sem acento, só letras e números."""
    return re.findall(r"[A-Z0-9]+", sem_acento(texto).upper())


def _numeros(texto):
    """Números que aparecem no texto, em algarismo ou por extenso ("quarenta mil" → 40, 1000, 40000)."""
    achados = set()
    for n in re.findall(r"\d+(?:[.,]\d+)*", str(texto or "")):
        limpo = re.sub(r"[.,]", "", n)
        achados.add(limpo.lstrip("0") or "0")
        achados.add(n.split(",")[0].split(".")[0].lstrip("0") or "0")
    anterior = None
    for t in tokens(texto):
        if t in _EXTENSO:
            v = _EXTENSO[t]
            achados.add(str(v))
            if t == "MIL" and anterior is not None:
                achados.add(str(anterior * 1000))
            anterior = v
        elif t.isdigit():
            anterior = int(t)                        # "40 mil" → 40 e 40000
        else:
            anterior = None
    return achados


class Base:
    """O que a pergunta pode citar: palavras do trecho, do título, do canal e os nomes conhecidos."""

    def __init__(self, transcricao="", titulo="", canal="", nomes=()):
        ref = " ".join([str(transcricao or ""), str(titulo or ""), str(canal or ""), " ".join(nomes or [])])
        self.palavras = {t for t in tokens(ref) if len(t) >= 3 and t not in COMUNS}
        self.prefixos = {t[:4] for t in self.palavras if len(t) >= 4}
        self.numeros = _numeros(ref)
        self.entidades = {t for t in tokens(" ".join([str(titulo or ""), str(canal or ""), " ".join(nomes or [])]))
                          if len(t) >= 2 and t not in COMUNS}

    def liga(self, palavra):
        return palavra in self.palavras or (len(palavra) >= 4 and palavra[:4] in self.prefixos)


def _generica(toks):
    texto = " ".join(toks)
    for g in GENERICAS:
        if re.search(rf"(^| ){re.escape(g)}( |$)", texto):
            resto = [t for t in toks if t not in g.split() and t not in COMUNS and len(t) >= 3]
            if len(resto) <= 1:
                return True
    return False


def avaliar_pergunta(pergunta, base: Base):
    """Nota de 0 a 100 + motivos. Não julga criatividade: só pega o que é claramente ruim."""
    p = str(pergunta or "").strip()
    if not p:
        return {"nota": 0, "motivos": ["vazia"], "ligadas": []}
    toks = tokens(p)
    conteudo = [t for t in toks if len(t) >= 3 and t not in COMUNS]
    nota, motivos = 60, []
    if not conteudo or _generica(toks):
        nota -= 50
        motivos.append("genérica")
    ligadas = [t for t in conteudo if base.liga(t)]
    if not ligadas:
        nota -= 30
        motivos.append("não cita nada do trecho")
    else:
        nota += min(15, 5 * len(ligadas))
    for n in sorted(set(re.findall(r"\d+", p))):
        n_limpo = n.lstrip("0") or "0"
        if n_limpo not in base.numeros:
            ano = len(n_limpo) == 4 and n_limpo[:2] in ("19", "20")
            nota -= 10 if ano else 45                # número inventado = falha de fidelidade
            motivos.append(f"número {n} não aparece no trecho")
    tam = len(p)
    if tam > 58:
        nota -= 10
        motivos.append("longa demais pra faixa")
    elif tam < 16:
        nota -= 15
        motivos.append("curta demais")
    elif 24 <= tam <= 52:
        nota += 8
    if base.entidades & set(toks):
        nota += 10                                   # cita o jogo/pessoa/canal: ajuda na busca
    if not p.endswith("?"):
        nota -= 5
    return {"nota": max(0, min(100, nota)), "motivos": motivos, "ligadas": ligadas}


def escolher_pergunta(principal, alternativas, base: Base):
    """(pergunta escolhida, alternativas atualizadas, relatório). Só troca quando a principal veio
    fraca e uma alternativa é claramente melhor."""
    alternativas = [a for a in (alternativas or []) if isinstance(a, str) and a.strip()]
    rel_p = avaliar_pergunta(principal, base)
    notas = [(avaliar_pergunta(a, base), a) for a in alternativas]
    relatorio = {"nota": rel_p["nota"], "motivos": rel_p["motivos"], "trocou": False,
                 "motivos_original": rel_p["motivos"]}
    if rel_p["nota"] < NOTA_BOA and notas:
        melhor_rel, melhor = max(notas, key=lambda x: x[0]["nota"])
        if melhor_rel["nota"] >= max(NOTA_BOA, rel_p["nota"] + 15):
            # a principal só continua como opção (botão ✏) se não for ruim de vez
            novas = [a for a in alternativas if a != melhor] + (
                [principal] if principal and rel_p["nota"] >= NOTA_RUIM else [])
            relatorio.update(nota=melhor_rel["nota"], motivos=melhor_rel["motivos"], trocou=True)
            return melhor, novas[:3], relatorio
    relatorio["melhor_alternativa"] = max((r["nota"] for r, _ in notas), default=None)
    return principal, alternativas, relatorio


def destaque_para(pergunta, destaque_antigo=None, maximo=2):
    """Palavras da pergunta que ficam coloridas na faixa (só vale palavra que está na pergunta)."""
    toks_p = tokens(pergunta)
    bons = []
    for d in destaque_antigo or []:
        if isinstance(d, str) and d.strip() and all(t in toks_p for t in tokens(d)) and tokens(d):
            bons.append(d.strip().upper())
    if bons:
        return bons[:maximo]
    palavras = [w.strip("?!.,;:\"'") for w in str(pergunta).split()]
    cand = [w for w in palavras if len(sem_acento(w)) >= 4 and sem_acento(w).upper() not in COMUNS]
    cand.sort(key=lambda w: (any(c.isdigit() for c in w), len(w)), reverse=True)
    return [c.upper() for c in cand[:maximo]]


def limpar_titulo(titulo, limite=95):
    t = re.sub(r"\s+", " ", str(titulo or "")).strip().strip("\"'“”").strip()
    if len(t) > limite:
        t = t[:limite].rsplit(" ", 1)[0].rstrip(",;:-– ")
    return t


def normalizar_hashtags(lista, maximo=5):
    saida, vistos = [], set()
    for h in lista or []:
        if not isinstance(h, str):
            continue
        corpo = re.sub(r"[^\w]", "", h.replace("#", " ").strip().replace(" ", ""), flags=re.UNICODE)
        if not corpo or len(corpo) > 30 or corpo.isdigit():
            continue
        chave = sem_acento(corpo).lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append("#" + corpo)
        if len(saida) >= maximo:
            break
    return saida
