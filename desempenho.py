"""Desempenho: teste de velocidade do PC, tempos de cada etapa dos cortes e espaço em disco.

• testar_velocidade(log): mede neste PC o encoder de vídeo (processador x chip de vídeo), a leitura de
  rostos e o Whisper, junta com os tempos reais dos últimos cortes (analises/tempos.jsonl) e recomenda
  ajustes (ex.: modo PC fraco).
• uso_disco() / limpar(log): mostra o que ocupa espaço e apaga só o que é descartável e antigo
  (projetos de edição e restos de tarefas). Cortes prontos e gravações em uso nunca são apagados aqui.
"""
from __future__ import annotations

import json
import os
import shutil
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
NOMES_ETAPAS = {"espera": "esperando a vez", "baixar": "baixar o trecho", "recortar": "recortar",
                "pausas": "tirar pausas", "legenda": "legenda (Whisper)", "rostos": "olhar os rostos",
                "ia": "IA (pergunta/título)", "gancho": "gancho no começo", "montagem": "montar o vídeo",
                "outros": "outros"}


# ============================================================ espaço em disco
def _tamanho(caminho: Path) -> int:
    if caminho.is_file():
        return caminho.stat().st_size
    total = 0
    for raiz, _dirs, arquivos in os.walk(caminho):
        for a in arquivos:
            try:
                total += (Path(raiz) / a).stat().st_size
            except OSError:
                pass
    return total


def _gb(n):
    return f"{n / 1024 ** 3:.1f} GB" if n >= 1024 ** 3 else f"{n / 1024 ** 2:.0f} MB"


def uso_disco(base: Path = BASE):
    """[(rótulo, bytes)] do que o programa guarda, e os GB livres no disco."""
    saida = base / "cortes_prontos"
    itens = []
    if saida.is_dir():
        cortes = sum(p.stat().st_size for p in saida.iterdir() if p.is_file())
        itens.append(("Cortes prontos (vídeos, capas, legendas)", cortes))
        for nome, rotulo in (("_edicao", "Projetos de edição (pra reeditar)"), ("_trabalho", "Restos de tarefas"),
                             ("espanhol", "Versões em espanhol"), ("longos", "Cortes longos")):
            if (saida / nome).is_dir():
                itens.append((rotulo, _tamanho(saida / nome)))
    if (base / "gravacoes").is_dir():
        itens.append(("Gravações das lives", _tamanho(base / "gravacoes")))
    livre = shutil.disk_usage(base).free / 1024 ** 3
    return itens, livre


def texto_disco(base: Path = BASE):
    itens, livre = uso_disco(base)
    linhas = [f"💾 Livre no disco: {livre:.1f} GB" + ("  ⚠ POUCO ESPAÇO" if livre < 10 else "")]
    for rotulo, n in sorted(itens, key=lambda x: -x[1]):
        linhas.append(f"   {_gb(n):>8}  {rotulo}")
    return "\n".join(linhas)


def limpar_projetos_edicao(pasta_saida: Path, dias: float, agora=None):
    """Apaga _edicao/<corte> com mais de `dias` dias. Devolve (quantos, bytes). O corte pronto fica;
    só a opção de reeditar sem refazer some (o editor avisa)."""
    raiz = Path(pasta_saida) / "_edicao"
    if dias <= 0 or not raiz.is_dir():
        return 0, 0
    agora, n, livres = agora or time.time(), 0, 0
    for pasta in raiz.iterdir():
        if not pasta.is_dir() or pasta.is_symlink():
            continue
        try:
            ultima = max([pasta.stat().st_mtime] + [p.stat().st_mtime for p in pasta.iterdir()])
        except OSError:
            continue
        if agora - ultima > dias * 86400:
            tam = _tamanho(pasta)
            shutil.rmtree(pasta, ignore_errors=True)
            if not pasta.exists():
                n, livres = n + 1, livres + tam
    return n, livres


def limpar_trabalho(pasta_saida: Path, horas: float = 12, agora=None):
    """Restos de tarefas que caíram no meio (_trabalho/tarefa_*) há mais de `horas` horas."""
    raiz = Path(pasta_saida) / "_trabalho"
    if not raiz.is_dir():
        return 0, 0
    agora, n, livres = agora or time.time(), 0, 0
    for pasta in raiz.glob("tarefa_*"):
        try:
            if pasta.is_dir() and agora - pasta.stat().st_mtime > horas * 3600:
                tam = _tamanho(pasta)
                shutil.rmtree(pasta, ignore_errors=True)
                if not pasta.exists():
                    n, livres = n + 1, livres + tam
        except OSError:
            pass
    return n, livres


def limpeza_automatica(cfg=None, base: Path = BASE, log=print):
    """Roda de tempos em tempos (monitor) e ao abrir o programa: projetos de edição antigos e restos."""
    if cfg is None:
        import cortes
        cfg = cortes.carregar_config()
    saida = base / "cortes_prontos"
    dias = float(cfg.get("dias_projetos_edicao", 30) or 0)
    n1, b1 = limpar_projetos_edicao(saida, dias)
    n2, b2 = limpar_trabalho(saida)
    if n1 or n2:
        log(f"🧹 Limpeza: {n1} projeto(s) de edição com mais de {dias:g} dias e {n2} resto(s) de tarefa "
            f"— {_gb(b1 + b2)} liberados.")
    livre = shutil.disk_usage(base).free / 1024 ** 3
    if livre < float(cfg.get("aviso_disco_gb", 10)):
        log(f"⚠ Pouco espaço no disco: {livre:.1f} GB livres. Use 'Espaço em disco' em Contas & IA.")
    return n1 + n2, b1 + b2


def limpar(log, dias=None, base: Path = BASE):
    """Botão '🧹 Espaço em disco': mostra o uso, limpa o descartável e mostra quanto liberou."""
    import cortes
    cfg = cortes.carregar_config()
    dias = float(cfg.get("dias_projetos_edicao", 30) if dias is None else dias)
    log("=== Espaço em disco ===")
    log(texto_disco(base))
    saida = base / "cortes_prontos"
    n1, b1 = limpar_projetos_edicao(saida, dias)
    n2, b2 = limpar_trabalho(saida)
    log(f"\n🧹 Apaguei {n1} projeto(s) de edição com mais de {dias:g} dias e {n2} resto(s) de tarefa: "
        f"{_gb(b1 + b2)} liberados.")
    log("   (cortes prontos e gravações não são apagados aqui; as gravações têm a retenção do monitor)")
    log("\n" + texto_disco(base))
    return True


# ============================================================ tempos dos cortes
# etapa de cada mensagem do log (pra somar quanto tempo cada uma levou)
_ETAPAS = (("baixar", ("baixando",)), ("recortar", ("recortando o trecho", "recortando vídeo", "recortando:")),
           ("pausas", ("pausas", "silêncio", "vícios")), ("legenda", ("transcrevendo", "whisper")),
           ("rostos", ("rostos",)), ("gancho", ("gancho", "momento mais forte")),
           ("montagem", ("montando",)), ("ia", ("ia ", "claude", "pensando", "revisor", "pergunta")),
           ("espera", ("aguardando",)))


def etapas_do_log(marcas, fim=None):
    """[(hora, msg)] -> {etapa: segundos}. Mensagem que não abre etapa conta na anterior."""
    soma, atual = {}, None
    for i, (hora, msg) in enumerate(marcas):
        baixo = msg.lower()
        nome = next((n for n, chaves in _ETAPAS if any(c in baixo for c in chaves)), None)
        atual = nome or atual or "outros"
        prox = marcas[i + 1][0] if i + 1 < len(marcas) else (fim or hora)
        soma[atual] = round(soma.get(atual, 0) + max(0.0, prox - hora), 1)
    return soma


def registrar_tempos(marcas, saida=None, duracao=None, arquivo=None, encoder=""):
    """Guarda quanto cada etapa levou em analises/tempos.jsonl (usado no Teste de velocidade)."""
    if not marcas:
        return None
    fim = time.time()
    reg = {"quando": round(fim), "total": round(fim - marcas[0][0], 1), "duracao_corte": duracao,
           "etapas": etapas_do_log(marcas, fim), "encoder": encoder,
           "arquivo": Path(saida).name if saida else ""}
    try:
        destino = Path(arquivo) if arquivo else BASE / "analises" / "tempos.jsonl"
        destino.parent.mkdir(exist_ok=True)
        linhas = destino.read_text(encoding="utf-8").splitlines()[-199:] if destino.exists() else []
        linhas.append(json.dumps(reg, ensure_ascii=False))
        destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    except OSError:
        pass
    return reg


def tempos_recentes(n=10, arquivo=None):
    """Média de cada etapa nos últimos n cortes (analises/tempos.jsonl)."""
    arq = Path(arquivo) if arquivo else BASE / "analises" / "tempos.jsonl"
    try:
        regs = [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()][-n:]
    except (OSError, json.JSONDecodeError):
        return None
    if not regs:
        return None
    etapas = {}
    for r in regs:
        for k, v in r.get("etapas", {}).items():
            etapas.setdefault(k, []).append(v)
    return {"cortes": len(regs), "total": round(statistics.mean(r["total"] for r in regs), 1),
            "etapas": {k: round(sum(v) / len(regs), 1) for k, v in etapas.items()}}


def texto_tempos(t):
    if not t:
        return "Ainda não há cortes medidos (cada corte novo passa a anotar quanto cada etapa levou)."
    linhas = [f"⏱ Últimos {t['cortes']} corte(s): {t['total']:.0f} s em média"]
    for k, v in sorted(t["etapas"].items(), key=lambda x: -x[1]):
        if v >= 0.5:
            pct = 100 * v / max(1, t["total"])
            linhas.append(f"   {v:6.1f} s  {'█' * max(1, round(pct / 5)):<20} {NOMES_ETAPAS.get(k, k)}")
    return "\n".join(linhas)


# ============================================================ teste de velocidade
def _medir(cmd):
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=600)
    return time.time() - t, r.returncode == 0


def amostra_de_fala(base: Path = BASE):
    """O corte pronto mais recente (tem fala): é com ele que o Whisper é medido."""
    pasta = base / "cortes_prontos"
    videos = sorted(pasta.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True) if pasta.is_dir() else []
    return videos[0] if videos else None


def testar_velocidade(log, segundos=20):
    """Mede este PC e recomenda ajustes. Devolve {'recomendacoes': [...], 'pc_fraco': bool, ...}."""
    import cortes
    cortes.checar_ffmpeg()
    log("=== Teste de velocidade (uns 2 minutos; pode usar o PC normalmente) ===")
    nucleos = os.cpu_count() or 2
    try:
        import contas
        ram = contas.memoria_pc_gb()
    except Exception:
        ram = None
    log(f"Processador: {nucleos} threads · RAM: {f'{ram:.0f} GB' if ram else '?'}")
    res = {"nucleos": nucleos, "ram": ram}
    with tempfile.TemporaryDirectory(prefix="velocidade_") as d:
        d = Path(d)
        teste = d / "teste.mp4"
        log(f"Criando um vídeo de teste de {segundos} s em 1080x1920...")
        ok = _medir(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=s=1080x1920:r=30:d={segundos}",
                     "-f", "lavfi", "-i", f"sine=f=440:d={segundos}", "-c:v", "libx264", "-preset", "ultrafast",
                     "-c:a", "aac", "-shortest", str(teste)])[1]
        if not ok:
            log("✖ Não consegui criar o vídeo de teste (o ffmpeg está instalado?).")
            return None
        # 1) vídeo: processador x chip de vídeo
        cpu, _ = _medir(["ffmpeg", "-y", "-v", "error", "-i", str(teste), "-c:v", "libx264", "-preset", "veryfast",
                         "-crf", "20", "-c:a", "copy", str(d / "cpu.mp4")])
        res["video_cpu"] = cpu
        log(f"🎞 Vídeo no processador: {cpu:.1f} s ({segundos / cpu:.1f}x o tempo real)")
        enc = cortes.detectar_encoder_h264()
        res["encoder"] = enc
        if enc != "libx264":
            dec = {"h264_qsv": "qsv", "h264_nvenc": "cuda", "h264_amf": "d3d11va"}[enc]
            hw, ok = _medir(["ffmpeg", "-y", "-v", "error", "-hwaccel", dec, "-i", str(teste),
                             *cortes.args_encoder_video(crf_padrao=20), "-c:a", "copy", str(d / "hw.mp4")])
            res["video_hw"] = hw if ok else None
            log(f"🎞 Vídeo no chip de vídeo ({enc}): {hw:.1f} s — {cpu / hw:.1f}x mais rápido" if ok
                else "🎞 O chip de vídeo falhou no teste — o programa usa o processador.")
        else:
            log("🎞 Este PC não tem acelerador de vídeo: tudo é feito no processador.")
        # 2) rostos
        try:
            import efeitos
            t = time.time()
            efeitos.analisar_rostos(teste)
            res["rostos"] = time.time() - t
            log(f"🙂 Olhar os rostos: {res['rostos']:.1f} s pra {segundos} s de vídeo")
        except Exception as e:                                     # noqa: BLE001
            log(f"🙂 Olhar os rostos: não deu pra medir ({e})")
        # 3) Whisper (o modelo da legenda) — precisa de FALA de verdade: usa o áudio de um corte pronto
        try:
            amostra = amostra_de_fala()
            if not amostra:
                raise RuntimeError("ainda não há corte pronto pra usar a fala como teste")
            wav = d / "a.wav"
            _medir(["ffmpeg", "-y", "-v", "error", "-i", str(amostra), "-t", str(segundos), "-vn", "-ac", "1",
                    "-ar", "16000", str(wav)])
            audio = cortes.ler_wav(wav)
            for nome in ("base", cortes.modelo_final()):
                if f"whisper_{nome}" in res:
                    continue
                modelo = cortes.carregar_whisper(nome)
                t = time.time()
                list(modelo.transcribe(audio, language="pt", vad_filter=False, beam_size=1)[0])
                res[f"whisper_{nome}"] = time.time() - t
                log(f"🗣 Whisper '{nome}': {res[f'whisper_{nome}']:.1f} s pra {segundos} s de áudio")
        except Exception as e:                                     # noqa: BLE001
            log(f"🗣 Whisper: não deu pra medir ({e})")
    # 4) os cortes de verdade
    t = tempos_recentes()
    log("\n" + texto_tempos(t))
    res["tempos"] = t
    # 5) recomendações
    rec = []
    fator = res.get("video_cpu", 0) / segundos
    whisper = res.get(f"whisper_{cortes.modelo_final()}", 0) / segundos
    pc_fraco = nucleos <= 4 and (fator > 0.8 or whisper > 0.6)
    if pc_fraco and not cortes.carregar_config().get("modo_pc_fraco"):
        rec.append("Ligar o MODO PC FRACO: legenda com o Whisper 'base', vídeo baixado em 720p e rostos lidos "
                   "a cada 1 s. Os cortes saem bem mais rápido, com legenda um pouco menos precisa.")
    if res.get("encoder") == "libx264":
        rec.append("Sem acelerador de vídeo: um PC com placa Nvidia ou Intel mais nova renderiza 3-5x mais rápido.")
    if ram and ram < 8:
        rec.append("Pouca memória: prefira a IA Claude/Gemini à IA local (o modelo local disputa memória com o vídeo).")
    livre = shutil.disk_usage(BASE).free / 1024 ** 3
    if livre < 15:
        rec.append(f"Só {livre:.0f} GB livres: use '🧹 Espaço em disco' e diminua os dias dos projetos de edição.")
    if t and t["etapas"].get("espera", 0) > 30:
        rec.append("Os cortes ficam muito tempo esperando a vez: use o modo madrugada pros automáticos.")
    log("\n=== Recomendações ===")
    for r in rec or ["Tudo certo pra este PC. Nada a mudar."]:
        log("• " + r)
    res.update(recomendacoes=rec, pc_fraco=pc_fraco)
    return res
