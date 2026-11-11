"""Checkpoint de saída independente da confirmação da fila."""
import hashlib
import json
from pathlib import Path
from infraestrutura import salvar_json

BASE = Path(__file__).resolve().parent / '_jobs'


def identificador(job):
    return hashlib.sha256(str(job).encode()).hexdigest()[:24]


def recuperar(job):
    arquivo = BASE / (identificador(job)+'.json')
    try:
        dados = json.loads(arquivo.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False, None
    if dados.get('job') != job:
        return False, None
    if dados.get('estado') == 'descartado':
        return True, None
    for nome in dados.get('arquivos', []):
        video = Path(nome)
        try:
            ficha = json.loads(video.with_suffix('.json').read_text(encoding='utf-8'))
            qa = json.loads(video.with_suffix('.qualidade.json').read_text(encoding='utf-8'))
            if not video.is_file() or video.stat().st_size < 100 or ficha.get('_job_id') != job or not qa.get('aprovado'):
                return False, None
            from qualidade import inspecionar
            if not inspecionar(video, aprofundar=False)['aprovado']:
                return False, None
        except (OSError, ValueError, RuntimeError):
            return False, None
    if dados.get('arquivos') and dados.get('resultado') in dados['arquivos']:
        return True, Path(dados['resultado'])
    return False, None


def confirmar(job, resultado):
    if resultado is None:
        dados = dict(job=job, estado='descartado', arquivos=[])
    else:
        resultado = Path(resultado).resolve()
        arquivos = []
        for ficha in resultado.parent.glob('*_'+identificador(job)[:8]+'*.json'):
            try:
                conteudo = json.loads(ficha.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            video = ficha.with_suffix('.mp4')
            if conteudo.get('_job_id') == job and video.is_file():
                arquivos.append(str(video))
        if str(resultado) not in arquivos:
            raise RuntimeError('Não foi possível confirmar a saída da tarefa.')
        dados = dict(job=job, estado='concluido', resultado=str(resultado), arquivos=arquivos)
    salvar_json(BASE/(identificador(job)+'.json'), dados)
