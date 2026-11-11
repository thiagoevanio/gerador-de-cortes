import datetime as dt
import http.client
import json
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest
from pathlib import Path
from unittest.mock import patch

import cortes
import editorial
import efeitos
import historico_metricas
import monitor
import recursos
import resultados
from fila_tarefas import FilaTarefas
from infraestrutura import salvar_json


class Evolucao(unittest.TestCase):
    def test_previa_nao_altera_estilo_do_render(self):
        antes = cortes.TAMANHO_LEGENDA
        resultado = []
        with cortes.contexto_render():
            cfg = dict(cortes.CONFIG_PADRAO, legenda_tamanho=antes+10)
            t=threading.Thread(target=lambda:resultado.append(cortes.aplicar_config(cfg)))
            t.start();t.join(timeout=2)
            self.assertEqual(resultado,[False])
            self.assertEqual(cortes.TAMANHO_LEGENDA,antes)

    def test_contexto_render_libera_apos_falha(self):
        with self.assertRaises(ValueError):
            with cortes.contexto_render():
                raise ValueError('falha simulada')
        self.assertIsNone(cortes._dono_render)

    def test_metricas_exigem_observacoes_separadas(self):
        with tempfile.TemporaryDirectory() as d:
            arquivo = Path(d)/'metricas.db'
            self.assertEqual(historico_metricas.medir(dict(id='v', canal='c', views=100), 10000, arquivo), {})
            self.assertEqual(historico_metricas.medir(dict(id='v', canal='c', views=120), 10060, arquivo), {})
            r = historico_metricas.medir(dict(id='v', canal='c', views=200), 13600, arquivo)
            self.assertEqual(r['velocidade_recente'], 81.36)

    def test_medicao_na_janela(self):
        agora = dt.datetime(2026,11,2,12,tzinfo=dt.timezone.utc)
        ficha = dict(youtube_quando=(agora-dt.timedelta(hours=25)).isoformat(), yt_stats=dict(views=500))
        resultados.registrar_medicao(ficha, agora=agora)
        self.assertEqual(resultados.views_comparaveis(ficha), 500)
        ficha2 = dict(youtube_quando=(agora-dt.timedelta(hours=100)).isoformat(), yt_stats=dict(views=5000))
        resultados.registrar_medicao(ficha2, agora=agora)
        self.assertIsNone(resultados.views_comparaveis(ficha2))

    def test_orcamento_ia(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d)/'consumo.db'
            self.assertTrue(recursos.reservar_ia(1, f, 'dia1'))
            self.assertFalse(recursos.reservar_ia(1, f, 'dia1'))
            self.assertTrue(recursos.reservar_ia(1, f, 'dia2'))

    def test_tempos_sobrepostos(self):
        self.assertEqual(efeitos.mapear_tempo(10, [(1,4),(3,6)]), 5)

    def test_nao_remove_primeira_frase_so_por_comecar_falando(self):
        palavras = [dict(t='Frase.' if i==4 else ('Palavra' if i==0 else 'palavra'), ini=i*.5, fim=i*.5+.4) for i in range(10)]
        ini, _ = efeitos.ajustar_frase(palavras, [p['t'] for p in palavras], 30)
        self.assertEqual(ini, 0)        # começou com maiúscula = começo de frase de verdade

    def test_remove_resto_de_frase_no_comeco(self):
        palavras = [dict(t='fim.' if i==4 else ('Nova' if i==5 else 'palavra'), ini=i*.5, fim=i*.5+.4) for i in range(60)]
        ini, _ = efeitos.ajustar_frase(palavras, [p['t'] for p in palavras], 30.5)
        self.assertAlmostEqual(ini, 2.35)  # entrou no meio ("palavra...") → começa em "Nova"

    def test_versoes_da_live_usam_tempo_absoluto(self):
        from momentos import deslocar_momento
        m=dict(inicio=1,fim=10,versoes={'direta':dict(inicio=1,fim=10)},evidencias={'candidato':[0,20]})
        r=deslocar_momento(m,100)
        self.assertEqual(r['versoes']['direta']['inicio'],101)
        self.assertEqual(r['evidencias']['candidato'],[100,120])
        self.assertEqual(m['evidencias']['candidato'],[0,20])

    def test_concorrencia_nao_entrega_tarefa_duas_vezes(self):
        with tempfile.TemporaryDirectory() as d:
            fila = FilaTarefas(Path(d)/'fila.db')
            try:
                for i in range(10): fila.adicionar(dict(_job_id=str(i),tipo='corte'))
                with ThreadPoolExecutor(max_workers=4) as pool:
                    tarefas=list(pool.map(lambda _:fila.proxima(),range(20)))
                ids=[t['_job_id'] for t in tarefas if t]
                self.assertEqual(len(ids),10)
                self.assertEqual(len(set(ids)),10)
            finally:
                fila.db.close()

    def test_revisao_preserva_gravacao(self):
        with tempfile.TemporaryDirectory() as d:
            fila=FilaTarefas(Path(d)/'fila.db')
            try:
                fila.adicionar(dict(_job_id='c',tipo='corte',fonte=str(Path(d)/'live.ts')))
                t=fila.proxima();fila.aguardar_revisao(t,'Revisar contexto')
                self.assertTrue(fila.fonte_em_uso(d))
                self.assertTrue(fila.retomar('c'))
                self.assertTrue(fila.proxima()['_aprovado'])
            finally:
                fila.db.close()

    def test_busca_editorial(self):
        momentos = [dict(transcricao='Ele explicou o problema no jogo', motivo='Explicação'), dict(transcricao='receita de bolo')]
        resultado=editorial.buscar(momentos, 'problema no jogo')
        self.assertEqual([m['transcricao'] for m in resultado],[momentos[0]['transcricao']])
        self.assertEqual(resultado[0]['busca']['metodo'],'conceitos_locais')

    def test_feedback_separado_por_perfil(self):
        with tempfile.TemporaryDirectory() as d, patch.object(editorial, 'BASE', Path(d)):
            editorial.registrar_feedback('A', 'rejeitado', 'Faltou contexto')
            self.assertIn('Faltou contexto', editorial.memoria('A')[0])
            self.assertEqual(editorial.memoria('B'), [])

    def test_retomada_cancelamento(self):
        with tempfile.TemporaryDirectory() as d:
            fila = FilaTarefas(Path(d)/'fila.db')
            fila.adicionar(dict(_job_id='teste',tipo='corte'))
            self.assertTrue(fila.cancelar('teste'))
            self.assertIsNone(fila.proxima())
            self.assertTrue(fila.retomar('teste'))
            self.assertEqual(fila.proxima()['_job_id'], 'teste')
            self.assertFalse(fila.cancelar('teste'))
            fila.db.close()

    def test_agendamento_recuperado_sem_live(self):
        with tempfile.TemporaryDirectory() as d:
            fonte=Path(d)/'live.ts'; fonte.write_bytes(b'teste')
            fila = FilaTarefas(Path(d)/'fila.db')
            agenda = [dict(id='mom',quando=0,fonte=str(fonte),ini=10,alvo=40,pasta='canal',meta=dict(titulo='Teste'))]
            with patch.object(cortes, 'duracao_video', return_value=60):
                monitor.processar_agendados({}, {}, agenda, fila)
            t = fila.proxima()
            self.assertEqual(t['fonte'], str(fonte))
            self.assertEqual(t['_job_id'], 'momento:mom')
            self.assertFalse(agenda)
            fila.db.close()

    def test_http_sessao_origem_e_post(self):
        srv=monitor.ThreadingHTTPServer(('127.0.0.1',0),monitor.Painel)
        porta=srv.server_address[1]
        t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
        def pedir(metodo,path,headers=None):
            c=http.client.HTTPConnection('127.0.0.1',porta,timeout=3)
            c.request(metodo,path,headers=headers or {})
            r=c.getresponse();codigo=r.status;corpo=r.read();c.close()
            return codigo,corpo
        try:
            with patch.object(monitor,'PORTA',porta):
                self.assertEqual(pedir('GET','/cortar?canal=teste')[0],405)
                self.assertEqual(pedir('POST','/tarefa?id=a&acao=retomar')[0],403)
                self.assertEqual(pedir('GET','/sessao',dict(Origin='https://evil.example'))[0],403)
                codigo,raw=pedir('GET','/sessao'); self.assertEqual(codigo,200)
                token=json.loads(raw)['token']
                with tempfile.TemporaryDirectory() as d:
                    fila=FilaTarefas(Path(d)/'fila.db');fila.adicionar(dict(_job_id='a',tipo='corte'));fila.cancelar('a')
                    with patch.object(monitor,'FILA_ATIVA',fila):
                        codigo,raw=pedir('POST','/tarefa?id=a&acao=retomar',{'X-Cortes-Token':token})
                        self.assertEqual(codigo,200);self.assertTrue(json.loads(raw)['ok'])
                    fila.db.close()
        finally:
            srv.shutdown();srv.server_close();t.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
