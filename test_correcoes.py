"""Regressões locais: não baixam vídeos e não chamam serviços de IA."""
import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fila_tarefas import FilaTarefas
import detector
import tendencias


def ranquear_isolado(resposta, trechos=None, n=3):
    tree = ast.parse(Path('momentos.py').read_text(encoding='utf-8'))
    func = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == '_ranquear')
    auxiliar = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'encaixar')
    class Cortes:
        IA_PRINCIPAL = 'teste'
        ia_json = staticmethod(lambda _: resposta)
        fmt_tempo = staticmethod(str)
        carregar_config = staticmethod(lambda *a: {})
    import math
    ns = dict(cortes=Cortes, math=math)
    exec(compile(ast.Module(body=[auxiliar, func], type_ignores=[]), 'ranquear', 'exec'), ns)
    trechos = trechos or [(100, 190)]
    return ns['_ranquear'](trechos, [[] for _ in trechos], dict(titulo='teste', canal='teste'), n, 60, lambda _: None)


class Correcoes(unittest.TestCase):
    def test_limites_ia(self):
        for inicio, fim in [(-20, 40), (9000, 9060), (100, float('inf')), (float('nan'), 150)]:
            resultado = ranquear_isolado({'momentos': [dict(inicio=inicio, fim=fim)]})
            self.assertTrue(all(100 <= m['inicio'] < m['fim'] <= 190 for m in resultado))

    def test_sobreposicao(self):
        resultado = ranquear_isolado({'momentos': [dict(inicio=100, fim=150), dict(inicio=120, fim=180)]})
        self.assertEqual(len(resultado), 1)

    def test_candidato_curto(self):
        resultado = ranquear_isolado({}, [(0, 12)])
        self.assertEqual((resultado[0]['inicio'], resultado[0]['fim']), (0, 12))

    def test_anonimos(self):
        t = detector.Termometro('teste')
        for _ in range(10):
            t.mensagem(100, '', 'kkkkkk')
        self.assertEqual(t._janela(101)[:2], (0, 10))

    def test_autor_repetido(self):
        t = detector.Termometro('teste')
        for _ in range(10):
            t.mensagem(100, 'pessoa', 'kkkkkk')
        self.assertEqual(t._janela(101)[:2], (1, 10))

    def test_busca_especifica(self):
        videos = [dict(id='a', titulo='Conversa sobre futebol', canal='Canal A', duracao=600, views=100),
                  dict(id='b', titulo='Outro assunto', canal='Canal B', duracao=600, views=10000)]
        with patch.object(tendencias, 'buscar_assuntos', return_value=[dict(termo='Outro assunto')]), \
             patch.object(tendencias, 'buscar_youtube', return_value=videos) as buscar, \
             patch.object(tendencias, 'em_alta_api') as geral, \
             patch.object(tendencias, '_ja_cortados', return_value=set()), \
             patch.object(tendencias, '_salvar'):
            resultado = tendencias.radar(['futebol'], detalhar=0, log=lambda _: None)
            self.assertEqual([v['id'] for v in resultado], ['a'])
            self.assertEqual(buscar.call_count, 1)
            geral.assert_not_called()

    def test_fila_recupera_e_prioriza(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / 'fila.db'
            fila = FilaTarefas(caminho)
            fila.adicionar(dict(tipo='corte', prioridade=0))
            fila.adicionar(dict(tipo='corte', prioridade=100))
            tarefa = fila.proxima(apenas_manual=True)
            self.assertEqual(tarefa['prioridade'], 100)
            fila.db.close()
            retomada = FilaTarefas(caminho)
            self.assertEqual(len(retomada), 2)
            tarefa = retomada.proxima()
            retomada.concluir(tarefa)
            self.assertEqual(len(retomada), 1)
            retomada.db.close()

    def test_falha_tem_backoff_e_limite(self):
        with tempfile.TemporaryDirectory() as pasta:
            fila = FilaTarefas(Path(pasta) / 'fila.db')
            fila.adicionar(dict(tipo='corte'))
            for tentativa in range(3):
                tarefa = fila.proxima()
                estado = fila.falhar(tarefa, 'falha simulada')
                self.assertIsNone(fila.proxima())
                fila.db.execute('UPDATE tarefas SET disponivel=0')
                fila.db.commit()
            self.assertEqual(estado, 'falhou')
            self.assertEqual(fila.resumo()['falhou'], 1)
            fila.db.close()

    def test_nao_apaga_fonte_necessaria_para_retry(self):
        with tempfile.TemporaryDirectory() as pasta:
            fila = FilaTarefas(Path(pasta) / 'fila.db')
            fila.adicionar(dict(tipo='corte', fonte=str(Path(pasta) / 'live.ts'), prioridade=10))
            fila.adicionar(dict(tipo='apagar', pasta=pasta, prioridade=-1))
            corte = fila.proxima()
            fila.falhar(corte, 'rede indisponivel')
            self.assertIsNone(fila.proxima())
            fila.db.execute("UPDATE tarefas SET disponivel=0")
            fila.db.commit()
            corte = fila.proxima()
            fila.concluir(corte)
            self.assertEqual(fila.proxima()['tipo'], 'apagar')
            fila.db.close()


if __name__ == '__main__':
    unittest.main()
