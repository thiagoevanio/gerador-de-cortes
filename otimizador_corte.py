"""
Otimizador Local de Cortes e Economia de Tokens (Zero-Token Viral Engine — v3.7).

Tecnologias auxiliares 100% locais (sem custo de API) para:
  1. Economia de tokens de saída/entrada:
     - Correções esparsas por delta ("correcoes": {"12": "Gaules", "gaules": "Gaules"})
       em vez de obrigar a IA a repetir centenas de palavras idênticas.
     - Reconciliador tolerante a falhas (SequenceMatcher): se a IA devolver a lista "palavras"
       com 1 ou 2 palavras a mais/menos, resgata as correções de nomes/acentos/pontuação sem
       quebrar a sincronia dos timestamps nem desperdiçar os tokens já gastos.
     - Cache global por hash de conteúdo (reaproveita respostas da IA ao refazer o mesmo trecho).
  2. Qualidade máxima do corte sem depender de IA:
     - Detector multimodal local de gancho/clímax (energia vocal + impacto semântico).
     - Seletor computacional do melhor quadro/thumbnail (nitidez Laplaciana + exposição + expressão facial).
     - Gerador local de pergunta chamativa e palavra de destaque quando sem IA.
     - Analisador de ritmo e curva de retenção (WPM, buracos de ritmo, velocidade de entrada).
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
import re
import time
import unicodedata
from pathlib import Path
from infraestrutura import salvar_json, exclusividade

BASE = Path(__file__).resolve().parent
ARQ_CACHE_CONTEUDO = BASE / "analises" / "cache_ia_conteudo.json"
ARQ_ECONOMIA = BASE / "analises" / "economia_tokens.json"

PALAVRAS_IMPACTO = {
    "segredo": 3.2, "verdade": 2.6, "mentira": 3.2, "revelou": 3.0, "descobri": 3.0,
    "ninguem": 2.4, "nunca": 2.3, "sempre": 1.8, "escondeu": 3.0, "confessou": 3.2,
    "vazou": 3.3, "proibido": 2.8, "crime": 2.9, "golpe": 3.0, "esquema": 2.9,
    "caralho": 3.0, "absurdo": 3.0, "impossivel": 2.9, "insano": 2.7, "bizarro": 2.8,
    "inacreditavel": 3.0, "chocante": 2.9, "perigo": 2.5, "medo": 2.2, "morreu": 2.8,
    "explodiu": 2.9, "destruiu": 2.7, "acabou": 2.4, "perdeu": 2.3, "ganhou": 2.3,
    "briga": 3.0, "treta": 3.0, "processo": 2.8, "demitido": 2.9, "banido": 2.9,
    "expulso": 2.9, "dinheiro": 2.5, "milhao": 2.8, "milhoes": 2.9, "fortuna": 2.7,
    "erro": 2.2, "problema": 2.2, "culpa": 2.5, "traicao": 3.1, "vergonha": 2.6,
}

STOPWORDS_PT = {
    "que", "nao", "para", "com", "uma", "por", "mais", "como", "mas", "foi", "ele", "ela",
    "isso", "esse", "essa", "esta", "tem", "seu", "sua", "dos", "das", "nos", "nas",
    "pelo", "pela", "ate", "muito", "quando", "mesmo", "depois", "antes", "sobre", "entre",
    "era", "sao", "vou", "vai", "ter", "fazer", "feito", "tudo", "nada", "aqui", "ali",
    "entao", "tipo", "assim", "cara", "mano", "gente", "galera", "voce", "voces",
}


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", str(texto).lower()).encode("ascii", "ignore").decode()


def _limpar_token(texto: str) -> str:
    return re.sub(r"[^\w]", "", _sem_acento(texto))


def estimar_tokens(texto: str | None, imagens: int = 0) -> int:
    n_chars = len(str(texto or ""))
    return int(math.ceil(n_chars / 3.8)) + int(imagens) * 258


def _preservar_pontuacao(original: str, corrigida: str) -> str:
    orig = original.strip()
    corr = corrigida.strip()
    if not corr:
        return orig
    m_orig = re.match(r"^([^\wÀ-ÿ]*)(.*?)([^\wÀ-ÿ]*)$", orig, flags=re.UNICODE)
    m_corr = re.match(r"^([^\wÀ-ÿ]*)(.*?)([^\wÀ-ÿ]*)$", corr, flags=re.UNICODE)
    if not m_orig or not m_corr:
        return corr
    pref_o, _, suf_o = m_orig.groups()
    pref_c, miolo_c, suf_c = m_corr.groups()
    if not miolo_c:
        return orig
    return f"{pref_c or pref_o}{miolo_c}{suf_c or suf_o}"


def aplicar_delta_palavras(palavras: list[dict], correcoes: dict | list | None) -> list[str]:
    base = [str(p.get("t", "")).strip() for p in palavras]
    if not palavras or not correcoes:
        return base
    por_indice: dict[int, str] = {}
    por_termo: dict[str, str] = {}

    itens = []
    if isinstance(correcoes, dict):
        itens = list(correcoes.items())
    elif isinstance(correcoes, list):
        for item in correcoes:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                itens.append((item[0], item[1]))
            elif isinstance(item, dict) and "i" in item and "t" in item:
                itens.append((item["i"], item["t"]))

    for k, v in itens:
        if not isinstance(v, str) or not v.strip():
            continue
        v_limpo = v.strip()
        if isinstance(k, int) or (isinstance(k, str) and k.strip().isdigit()):
            idx = int(k)
            if 0 <= idx < len(base):
                por_indice[idx] = v_limpo
        elif isinstance(k, str) and k.strip():
            chave = re.sub(r"^[^\wÀ-ÿ]+|[^\wÀ-ÿ]+$", "", k.strip().lower(), flags=re.UNICODE)
            if chave:
                por_termo[chave] = v_limpo

    saida = []
    for i, texto in enumerate(base):
        if i in por_indice:
            saida.append(_preservar_pontuacao(texto, por_indice[i]))
            continue
        m = re.match(r"^([^\wÀ-ÿ]*)(.*?)([^\wÀ-ÿ]*)$", texto, flags=re.UNICODE)
        if m:
            pref, miolo, suf = m.groups()
            chave = miolo.lower()
            if chave in por_termo:
                saida.append(f"{pref}{por_termo[chave]}{suf}")
                continue
        saida.append(texto)
    return saida


def reconciliar_palavras_ia(palavras: list[dict], lista_ia: list | None = None,
                            correcoes: dict | list | None = None) -> tuple[list[str], str]:
    originais = [str(p.get("t", "")).strip() for p in palavras]
    if not originais:
        return [], "vazio"

    if isinstance(lista_ia, list) and len(lista_ia) == len(originais) and all(isinstance(x, str) and x.strip() for x in lista_ia):
        textos = [x.strip() for x in lista_ia]
        if correcoes:
            textos = aplicar_delta_palavras([{"t": t} for t in textos], correcoes)
        return textos, "lista_exata"

    if correcoes:
        base = aplicar_delta_palavras(palavras, correcoes)
        if not isinstance(lista_ia, list) or not lista_ia:
            return base, "delta_esparso"
    else:
        base = list(originais)

    if isinstance(lista_ia, list) and lista_ia:
        limpa_ia = [str(x).strip() for x in lista_ia if isinstance(x, str) and str(x).strip()]
        if limpa_ia and abs(len(limpa_ia) - len(base)) <= max(8, int(len(base) * 0.25)):
            norm_orig = [_limpar_token(w) for w in base]
            norm_ia = [_limpar_token(w) for w in limpa_ia]
            sm = difflib.SequenceMatcher(None, norm_orig, norm_ia, autojunk=False)
            reconciliadas = list(base)
            resgatadas = 0
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    for k in range(i2 - i1):
                        candidato = limpa_ia[j1 + k]
                        if candidato != reconciliadas[i1 + k]:
                            reconciliadas[i1 + k] = candidato
                            resgatadas += 1
                elif tag == "replace" and (i2 - i1) == (j2 - j1):
                    for k in range(i2 - i1):
                        reconciliadas[i1 + k] = limpa_ia[j1 + k]
                        resgatadas += 1
            if resgatadas > 0:
                return reconciliadas, "alinhamento_tolerante"

    return base, ("delta_esparso" if correcoes else "original")


def achar_gancho_multimodal(palavras: list[dict], textos: list[str] | None = None,
                            audio=None, sr: int = 16000) -> int | None:
    if not palavras or len(palavras) < 5:
        return None
    textos = textos if textos and len(textos) == len(palavras) else [str(p.get("t", "")) for p in palavras]
    dur_total = max(float(palavras[-1].get("fim", 0)), 1.0)

    rms_mediana = 1.0
    if audio is not None and len(audio) >= sr:
        import numpy as np
        n_seg = len(audio) // sr
        blocos = audio[:n_seg * sr].reshape(n_seg, sr).astype("float32")
        rms_seg = np.sqrt((blocos ** 2).mean(axis=1))
        rms_mediana = float(np.median(rms_seg)) + 1e-6
    else:
        rms_seg = None

    melhor_i, melhor_nota = None, -1.0
    for i, (p, txt) in enumerate(zip(palavras, textos)):
        ini = float(p.get("ini", 0))
        if dur_total > 10 and (ini < 3.5 or ini > dur_total - 1.5):
            continue
        limpa = _limpar_token(txt)
        nota = PALAVRAS_IMPACTO.get(limpa, 0.0)
        if "?" in txt:
            nota += 1.6
        if "!" in txt:
            nota += 1.8
        if len(limpa) >= 5 and txt.isupper():
            nota += 1.0
        if p.get("foco"):
            nota += 3.5

        for j in range(i + 1, min(len(palavras), i + 4)):
            viz = _limpar_token(textos[j])
            nota += PALAVRAS_IMPACTO.get(viz, 0.0) * 0.45

        if rms_seg is not None:
            s_idx = min(len(rms_seg) - 1, max(0, int(ini)))
            ratio = float(rms_seg[s_idx]) / rms_mediana
            if ratio > 1.35:
                nota += min(3.5, (ratio - 1.0) * 1.6)

        if nota > melhor_nota:
            melhor_nota = nota
            melhor_i = i

    if melhor_nota < 1.2:
        foco_i = next((i for i, p in enumerate(palavras) if p.get("foco")), None)
        if foco_i is not None:
            return foco_i
        return None
    return melhor_i


def gerar_pergunta_local(palavras: list[dict], meta: dict | None = None) -> dict:
    meta = meta or {}
    titulo = str(meta.get("titulo") or "").strip()

    if palavras:
        texto_total = " ".join(str(p.get("t", "")).strip() for p in palavras if p.get("t"))
        frases = [f.strip() for f in re.split(r"(?<=[.!?…])\s+", texto_total) if len(f.strip()) >= 8]
        melhor_frase, maior_peso = "", -1.0
        for f in frases:
            tokens_f = [_limpar_token(w) for w in f.split()]
            peso = sum(PALAVRAS_IMPACTO.get(t, 0.0) for t in tokens_f)
            if "?" in f:
                peso += 2.5
            if "!" in f:
                peso += 1.5
            if 10 <= len(f) <= 52:
                peso += 1.2
            if peso > maior_peso:
                maior_peso, melhor_frase = peso, f

        if melhor_frase and maior_peso >= 2.0:
            limpa = re.sub(r"[.!?…]+$", "", melhor_frase.strip()).upper()
            if len(limpa) > 50:
                palavras_f = limpa.split()
                limpa = ""
                for w in palavras_f:
                    if len((limpa + " " + w).strip()) <= 50:
                        limpa = (limpa + " " + w).strip()
                    else:
                        break
            if len(limpa) >= 8:
                pergunta = limpa.rstrip("?") + "??"
                destaque = _escolher_destaque(pergunta)
                return {"pergunta": pergunta, "destaque": destaque}

    if titulo and not re.fullmatch(r"[\w_-]+\.(mp4|mkv|ts|mov|webm)", titulo, flags=re.I):
        limpo = re.sub(r"\s*[\|\-—]\s*.*$", "", titulo).strip().upper()
        limpo = re.sub(r"[^\wÀ-ÿ\s?!]", "", limpo, flags=re.UNICODE).strip()
        if 6 <= len(limpo) <= 50 and limpo.lower() not in ("teste", "fonte", "live", "video", "original"):
            pergunta = limpo.rstrip("?.!") + "??"
            return {"pergunta": pergunta, "destaque": _escolher_destaque(pergunta)}

    return {"pergunta": "VOCÊ VIU ISSO??", "destaque": ["ISSO"]}


def _escolher_destaque(pergunta: str) -> list[str]:
    cand = []
    for w in pergunta.upper().split():
        limpa = re.sub(r"\W", "", w)
        if len(limpa) < 3 or _sem_acento(limpa) in STOPWORDS_PT:
            continue
        peso = PALAVRAS_IMPACTO.get(_sem_acento(limpa), 0.0) + min(2.0, len(limpa) * 0.2)
        cand.append((peso, limpa))
    cand.sort(reverse=True)
    return [w for _, w in cand[:2]] or ["ISSO"]


def pontuar_quadro(img_bgr, detector_rosto=None) -> float:
    try:
        import cv2
    except ImportError:
        return 0.0
    if img_bgr is None or img_bgr.size == 0:
        return -100.0
    h, w = img_bgr.shape[:2]
    peq = cv2.resize(img_bgr, (320, max(90, int(320 * h / max(1, w)))))
    cinza = cv2.cvtColor(peq, cv2.COLOR_BGR2GRAY)
    brilho = float(cinza.mean())
    if brilho < 18 or brilho > 245:
        return -50.0
    contraste = float(cinza.std())
    nitidez = float(cv2.Laplacian(cinza, cv2.CV_64F).var())
    nota = min(35.0, math.log1p(nitidez) * 4.5) + min(15.0, contraste * 0.25)

    if detector_rosto is not None:
        try:
            rostos = detector_rosto(peq)
        except Exception:
            rostos = []
        if rostos:
            ph, pw = peq.shape[:2]
            x, y, rw, rh = max(rostos, key=lambda r: r[2] * r[3])
            area_rel = (rw * rh) / max(1.0, pw * ph)
            cx = (x + rw / 2) / pw
            centralidade = 1.0 - min(1.0, abs(cx - 0.5) * 1.6)
            x0, x1 = max(0, int(x)), min(pw, int(x + rw))
            y0, y1 = max(0, int(y)), min(ph, int(y + rh))
            reg_rosto = cinza[y0:y1, x0:x1]
            expressao = float(reg_rosto.std()) if reg_rosto.size > 0 else 0.0
            nota += 30.0 + min(25.0, area_rel * 180.0) + centralidade * 10.0 + min(12.0, expressao * 0.2)
    return round(nota, 3)


def escolher_melhor_quadro(frames: list[Path], detector_rosto=None) -> Path | None:
    if not frames:
        return None
    try:
        import cv2
    except ImportError:
        return frames[len(frames) // 3]
    if detector_rosto is None:
        try:
            import efeitos
            detector_rosto = efeitos._criar_detector()
        except Exception:
            detector_rosto = None
    melhor, melhor_nota = frames[len(frames) // 3], -1e9
    for f in frames:
        try:
            img = cv2.imread(str(f))
            if img is None:
                continue
            nota = pontuar_quadro(img, detector_rosto)
            if nota > melhor_nota:
                melhor_nota, melhor = nota, f
        except Exception:
            continue
    return melhor


def analisar_ritmo_retencao(palavras: list[dict], duracao: float) -> dict:
    dur = max(0.1, float(duracao or 0))
    if not palavras:
        return {"nota_retencao": 25.0, "ppm": 0.0, "densidade_fala": 0.0,
                "buracos_ritmo": 0, "tempo_primeira_fala": round(dur, 2),
                "diagnostico": ["Sem fala transcrita no corte."]}

    n = len(palavras)
    ppm = round(n / (dur / 60.0), 1)
    t_primeira = max(0.0, float(palavras[0].get("ini", 0)))
    tempo_falado = sum(max(0.02, float(p.get("fim", 0)) - float(p.get("ini", 0))) for p in palavras)
    densidade = round(min(1.0, tempo_falado / dur), 3)

    buracos = 0
    maior_pausa = 0.0
    for a, b in zip(palavras, palavras[1:]):
        pausa = float(b.get("ini", 0)) - float(a.get("fim", 0))
        if pausa > 1.2:
            buracos += 1
        if pausa > maior_pausa:
            maior_pausa = pausa

    nota = 70.0
    diag = []
    if 130 <= ppm <= 200:
        nota += 14.0
        diag.append(f"Ritmo dinâmico ({ppm:.0f} palavras/min).")
    elif 100 <= ppm < 130 or 200 < ppm <= 230:
        nota += 6.0
    else:
        nota -= 10.0
        diag.append(f"Ritmo fora da faixa ideal ({ppm:.0f} palavras/min).")

    if t_primeira <= 0.6:
        nota += 10.0
    elif t_primeira > 1.8:
        nota -= 12.0
        diag.append(f"Demora {t_primeira:.1f}s para começar a falar.")

    if buracos == 0:
        nota += 6.0
    else:
        nota -= min(18.0, buracos * 6.0)
        diag.append(f"{buracos} pausa(s) acima de 1.2s (maior: {maior_pausa:.1f}s).")

    nota = round(max(0.0, min(100.0, nota)), 1)
    return {
        "nota_retencao": nota,
        "ppm": ppm,
        "densidade_fala": densidade,
        "buracos_ritmo": buracos,
        "tempo_primeira_fala": round(t_primeira, 2),
        "diagnostico": diag or ["Corte enxuto e sem pausas mortas."],
    }


def registrar_economia_tokens(tokens_entrada: int = 0, tokens_saida: int = 0,
                              tokens_poupados: int = 0, motivo: str = ""):
    try:
        ARQ_ECONOMIA.parent.mkdir(parents=True, exist_ok=True)
        with exclusividade(ARQ_ECONOMIA.with_suffix(".lock"), timeout=5):
            try:
                d = json.loads(ARQ_ECONOMIA.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                d = {"tokens_entrada": 0, "tokens_saida": 0, "tokens_poupados": 0, "eventos": {}}
            d["tokens_entrada"] = int(d.get("tokens_entrada", 0)) + int(tokens_entrada)
            d["tokens_saida"] = int(d.get("tokens_saida", 0)) + int(tokens_saida)
            d["tokens_poupados"] = int(d.get("tokens_poupados", 0)) + int(tokens_poupados)
            if motivo:
                ev = d.setdefault("eventos", {})
                ev[motivo] = int(ev.get(motivo, 0)) + 1
            salvar_json(ARQ_ECONOMIA, d)
    except Exception:
        pass


def relatorio_economia_tokens() -> dict:
    try:
        d = json.loads(ARQ_ECONOMIA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {"tokens_entrada": 0, "tokens_saida": 0, "tokens_poupados": 0, "eventos": {}}
    usados = d.get("tokens_entrada", 0) + d.get("tokens_saida", 0)
    poupados = d.get("tokens_poupados", 0)
    taxa = round(poupados / max(1, usados + poupados) * 100, 1) if (usados + poupados) else 0.0
    return {**d, "tokens_totais_usados": usados, "percentual_economia": taxa}


def main():
    ap = argparse.ArgumentParser(description="Otimizador local de cortes e auditoria de economia de tokens.")
    ap.add_argument("--relatorio", action="store_true", help="Mostra o resumo de tokens economizados")
    ap.add_argument("--auditar", help="Analisa o arquivo .transcricao.json de um corte pronto")
    args = ap.parse_args()
    if args.auditar:
        p = Path(args.auditar)
        arq = p if p.name.endswith(".transcricao.json") else p.with_suffix(".transcricao.json")
        dados = json.loads(arq.read_text(encoding="utf-8"))
        palavras = dados.get("palavras", [])
        dur = palavras[-1]["fim"] if palavras else 0.0
        print(json.dumps(analisar_ritmo_retencao(palavras, dur), ensure_ascii=False, indent=2))
        return
    print(json.dumps(relatorio_economia_tokens(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
