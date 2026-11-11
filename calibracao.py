"""Autonomia calibrada por aprovação humana, nunca por promessa de viralização."""
import hashlib
import json
import math
from pathlib import Path

BASE=Path(__file__).resolve().parent/'feedback_editorial'


def limite_wilson(acertos,total):
    if total<=0:return 0.0
    z=1.96;p=acertos/total
    return (p+z*z/(2*total)-z*math.sqrt(p*(1-p)/total+z*z/(4*total*total)))/(1+z*z/total)


def amostras(perfil):
    arquivo=BASE/(hashlib.sha256(perfil.encode()).hexdigest()[:16]+'.json')
    try:dados=json.loads(arquivo.read_text(encoding='utf-8'))
    except (OSError,ValueError):return []
    unicas={}
    for d in dados:
        t=d.get('trecho') or {}
        a=(t.get('evidencias') or t.get('editorial') or {}).get('avaliacao') or {}
        if not a.get('verificavel'):continue
        chave=json.dumps([t.get('fonte'),t.get('inicio'),t.get('fim'),t.get('transcricao')],ensure_ascii=False)
        try:
            nota=float(a['nota'])
            if math.isfinite(nota) and 0<=nota<=10:
                unicas[chave]=(nota,int(d.get('decisao')=='aprovado'))
        except (ValueError,TypeError,KeyError):pass
    return list(unicas.values())


def decidir(avaliacao,palavras,perfil,limiar,observacoes=None,minimo=20,confianca_minima=.75):
    motivos=[]
    if not avaliacao.get('verificavel'):motivos.append('Critérios editoriais sem evidências completas.')
    criterios=avaliacao.get('criterios',{})
    if any(criterios.get(k,{}).get('nota',0)<6 for k in ('contexto','conclusao')):
        motivos.append('Contexto ou conclusão abaixo do mínimo editorial.')
    nota=avaliacao.get('nota',0)
    if nota<limiar:motivos.append('Nota editorial abaixo do limite configurado.')
    if not palavras or sum(p.get('confianca',0)<.6 for p in palavras)/max(1,len(palavras))>.2:
        motivos.append('Transcrição sem confiança suficiente para autonomia.')
    historico=amostras(perfil) if observacoes is None else observacoes
    comparaveis=[ok for n,ok in historico if n>=limiar and abs(n-nota)<=1.5]
    inferior=limite_wilson(sum(comparaveis),len(comparaveis))
    if len(comparaveis)<minimo:motivos.append(f'Calibração inicial: {len(comparaveis)}/{minimo} avaliações humanas comparáveis.')
    elif inferior<confianca_minima:motivos.append('Histórico de aprovação ainda não sustenta processamento autônomo.')
    return dict(automatico=not motivos,motivos=motivos,amostras=len(comparaveis),
                limite_inferior_aprovacao=round(inferior,4),alvo='aprovação editorial humana, não views')
