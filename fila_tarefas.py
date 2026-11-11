"""Fila local durável. Um único monitor deve ser executado por vez."""
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path


class FilaTarefas:
    def __init__(self, caminho):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(caminho), check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS tarefas
            (id TEXT PRIMARY KEY, dados TEXT NOT NULL, estado TEXT NOT NULL,
             prioridade INTEGER NOT NULL, criado REAL NOT NULL,
             tentativas INTEGER NOT NULL DEFAULT 0, disponivel REAL NOT NULL DEFAULT 0,
             erro TEXT)""")
        self.db.execute("UPDATE tarefas SET estado='pendente' WHERE estado='executando'")
        self.db.execute("CREATE TABLE IF NOT EXISTS contexto (chave TEXT PRIMARY KEY, dados TEXT NOT NULL)")
        self.db.commit()

    def __len__(self):
        with self.lock:
            return self.db.execute("SELECT count(*) FROM tarefas WHERE estado='pendente'").fetchone()[0]

    def __iter__(self):
        with self.lock:
            rows = self.db.execute("SELECT dados FROM tarefas WHERE estado='pendente' ORDER BY prioridade DESC, criado").fetchall()
        return iter([json.loads(r[0]) for r in rows])

    def adicionar(self, tarefa):
        dados = dict(tarefa)
        dados.setdefault('_job_id', uuid.uuid4().hex)
        with self.lock, self.db:
            self.db.execute("INSERT OR IGNORE INTO tarefas(id,dados,estado,prioridade,criado) VALUES(?,?,'pendente',?,?)",
                            (dados['_job_id'], json.dumps(dados, ensure_ascii=False), dados.get('prioridade', 0), time.time()))

    def proxima(self, apenas_manual=False):
        with self.lock, self.db:
            rows = self.db.execute("SELECT id,dados FROM tarefas WHERE estado='pendente' AND disponivel<=? ORDER BY prioridade DESC, criado", (time.time(),)).fetchall()
            for ident, raw in rows:
                tarefa = json.loads(raw)
                if apenas_manual and not (tarefa.get('manual') or tarefa.get('prioridade', 0) >= 100):
                    continue
                if tarefa.get('tipo') == 'apagar' and self._fonte_em_uso(tarefa['pasta']):
                    continue
                self.db.execute("UPDATE tarefas SET estado='executando', tentativas=tentativas+1 WHERE id=?", (ident,))
                return tarefa
        return None

    def _fonte_em_uso(self, pasta):
        raiz = Path(pasta).resolve()
        agenda = self.carregar_contexto('agenda', {})
        for dados in list(agenda.get('agendados', [])) + list(agenda.get('aprovacoes', {}).values()):
            if dados.get('fonte') and Path(dados['fonte']).resolve().is_relative_to(raiz):
                return True
        for (raw,) in self.db.execute("SELECT dados FROM tarefas WHERE estado IN ('pendente','executando','falhou','revisao')"):
            dados = json.loads(raw)
            fonte = dados.get('fonte') or dados.get('base', {}).get('fonte')
            if fonte and not str(fonte).startswith(('http://', 'https://')):
                if Path(fonte).resolve().is_relative_to(raiz):
                    return True
        return False

    def concluir(self, tarefa):
        with self.lock, self.db:
            self.db.execute("UPDATE tarefas SET estado='concluido', erro=NULL WHERE id=?", (tarefa['_job_id'],))

    def falhar(self, tarefa, erro):
        with self.lock, self.db:
            tentativas = self.db.execute("SELECT tentativas FROM tarefas WHERE id=?", (tarefa['_job_id'],)).fetchone()[0]
            estado = 'falhou' if tentativas >= 3 else 'pendente'
            self.db.execute("UPDATE tarefas SET estado=?, erro=?, disponivel=? WHERE id=?",
                            (estado, str(erro)[:2000], time.time() + 30 * 2 ** max(0, tentativas - 1), tarefa['_job_id']))
            return estado

    def remove(self, tarefa):
        with self.lock, self.db:
            self.db.execute("UPDATE tarefas SET estado='cancelado' WHERE id=? AND estado='pendente'", (tarefa['_job_id'],))

    def atualizar(self, tarefa):
        with self.lock, self.db:
            self.db.execute("UPDATE tarefas SET dados=? WHERE id=? AND estado IN ('pendente','executando')",
                            (json.dumps(tarefa, ensure_ascii=False), tarefa['_job_id']))

    def resumo(self):
        with self.lock:
            return dict(self.db.execute("SELECT estado,count(*) FROM tarefas GROUP BY estado").fetchall())

    def salvar_contexto(self, chave, dados):
        with self.lock, self.db:
            self.db.execute('INSERT OR REPLACE INTO contexto VALUES(?,?)', (chave, json.dumps(dados, ensure_ascii=False)))

    def carregar_contexto(self, chave, padrao=None):
        with self.lock:
            row = self.db.execute('SELECT dados FROM contexto WHERE chave=?', (chave,)).fetchone()
            return json.loads(row[0]) if row else padrao

    def listar(self, limite=40):
        with self.lock:
            rows = self.db.execute("SELECT id,dados,estado,tentativas,erro FROM tarefas ORDER BY criado DESC LIMIT ?", (limite,)).fetchall()
            fases = {k.removeprefix('progresso:'):json.loads(v) for k,v in self.db.execute("SELECT chave,dados FROM contexto WHERE chave LIKE 'progresso:%'")}
        return [dict(id=i, tipo=(d := json.loads(raw)).get('tipo'),
                     titulo=(d.get('meta') or d.get('base', {}).get('meta') or {}).get('titulo', ''),
                     estado=estado, tentativas=n, erro=erro, etapa=fases.get(i, '') if estado=='executando' else '') for i, raw, estado, n, erro in rows]

    def retomar(self, ident):
        with self.lock, self.db:
            row = self.db.execute("SELECT dados,estado FROM tarefas WHERE id=? AND estado IN ('falhou','cancelado','revisao')", (ident,)).fetchone()
            if not row:
                return False
            dados = json.loads(row[0])
            if row[1] == 'revisao':
                dados['_aprovado'] = True
            self.db.execute("UPDATE tarefas SET dados=?,estado='pendente',tentativas=0,disponivel=0,erro=NULL WHERE id=?", (json.dumps(dados, ensure_ascii=False), ident))
            return True

    def cancelar(self, ident):
        with self.lock, self.db:
            return self.db.execute("UPDATE tarefas SET estado='cancelado' WHERE id=? AND estado='pendente'", (ident,)).rowcount > 0

    def origem_agendada(self, url):
        with self.lock:
            rows = self.db.execute("SELECT dados FROM tarefas WHERE estado IN ('pendente','executando','concluido','falhou','revisao')").fetchall()
        return any((d := json.loads(raw)).get('url') == url or d.get('fonte') == url for (raw,) in rows)

    def aguardar_revisao(self, tarefa, motivo):
        with self.lock, self.db:
            self.db.execute("UPDATE tarefas SET estado='revisao',erro=? WHERE id=?", (motivo, tarefa['_job_id']))

    def fonte_em_uso(self, pasta):
        with self.lock:
            return self._fonte_em_uso(pasta)

    def progresso(self, tarefa, mensagem):
        self.salvar_contexto('progresso:'+tarefa['_job_id'], str(mensagem)[:300])
