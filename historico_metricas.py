"""Medições sucessivas; não inventa crescimento quando existe uma única observação."""
import sqlite3
from contextlib import closing
import statistics
import time
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent / 'metricas.sqlite3'


def medir(video, agora=None, arquivo=None):
    agora = time.time() if agora is None else agora
    with closing(sqlite3.connect(str(arquivo or ARQUIVO), timeout=20)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS medidas (video TEXT, canal TEXT, t REAL, views INTEGER, PRIMARY KEY(video,t))')
        anterior = db.execute('SELECT t,views FROM medidas WHERE video=? AND t<=? AND t>=? ORDER BY t DESC LIMIT 1',
                              (video['id'], agora-600, agora-48*3600)).fetchone()
        canal = video.get('canal_id') or video.get('canal') or ''
        db.execute('INSERT OR REPLACE INTO medidas VALUES(?,?,?,?)', (video['id'], canal, agora, int(video.get('views') or 0)))
        db.execute('DELETE FROM medidas WHERE t<?', (agora-90*86400,))
        if not anterior or video.get('views', 0) < anterior[1]:
            return {}
        velocidade = (video['views']-anterior[1]) / ((agora-anterior[0])/3600)
        resultado = dict(velocidade_recente=round(velocidade, 2), janela_medicao_h=round((agora-anterior[0])/3600, 2))
        rows = db.execute('SELECT video, min(t), max(t), min(views), max(views) FROM medidas WHERE canal=? AND t>=? AND video<>? GROUP BY video',
                          (canal, agora-7*86400, video['id'])).fetchall()
        velocidades = [(v1-v0)/((t1-t0)/3600) for _, t0,t1,v0,v1 in rows if t1-t0 >= 600 and v1>v0]
        if len(velocidades) >= 3:
            resultado['acima_normal_canal'] = round(velocidade/max(1, statistics.median(velocidades)), 2)
        return resultado
