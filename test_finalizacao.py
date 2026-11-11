"""Casos adversos das implementações finais; provedores de IA são simulados."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import calibracao
import conclusao_tarefas
import resultados
from inteligencia_editorial import avaliar,buscar_semantico,versoes,agrupar_semantico,CRITERIOS
from identificacao_falante import associar,vetores_voz
from sincronia_live import posicao,escolher,dhash
from estatistica_editorial import contraste
from infraestrutura import salvar_json


class Finalizacao(unittest.TestCase):
    def test_rubrica_com_citacoes(self):
        texto='Por que isso aconteceu? O problema começou ontem. Ele explicou a solução. Tudo ficou resolvido.'
        r=avaliar(texto,{k:dict(nota=8,evidencia=texto) for k in CRITERIOS})
        self.assertTrue(r['verificavel']);self.assertEqual(r['nota'],8)
        self.assertEqual(len(r['criterios']),4)

    def test_citacao_inventada_e_nan_nao_valem(self):
        r=avaliar('Texto verdadeiro.',{k:dict(nota=float('nan'),evidencia='inventado') for k in CRITERIOS})
        self.assertFalse(r['verificavel'])
        self.assertTrue(r['alertas'])

    def test_versoes_rejeitam_limites_inventados(self):
        r=versoes([(0,'Premissa.'),(10,'Ideia.'),(35,'Fim.')],10,30,(0,50),{'direta':dict(inicio=-1,fim=30)})
        self.assertEqual(r['direta']['origem'],'falas_locais')
        self.assertTrue(all(0<=v['inicio']<v['fim']<=50 for v in r.values()))

    def test_busca_encontra_parafrase_com_evidencia(self):
        ms=[dict(transcricao='O lançamento trouxe muitos defeitos.',motivo='Comentário')]
        ia=lambda _: {'resultados':[dict(id=0,relevancia=.9,evidencia='muitos defeitos')]}
        r=buscar_semantico(ms,'Quando ele reclama da qualidade?',ia)
        self.assertEqual(r[0]['busca']['metodo'],'ia_com_evidencia')

    def test_busca_ignora_ids_e_citacoes_fabricados(self):
        r=buscar_semantico([dict(transcricao='Receita de pão.')],'automovel',lambda _: {'resultados':[dict(id=20,relevancia=1,evidencia='Receita'),dict(id=0,relevancia=1,evidencia='carro quebrado')]})
        self.assertEqual(r,[])

    def test_conceitos_locais(self):
        r=buscar_semantico([dict(transcricao='O game apresenta um defeito.')],'problema no jogo')
        self.assertEqual(len(r),1)

    def test_busca_cobre_fim_de_transcricao_longa(self):
        ms=[dict(inicio=i,fim=i+1,transcricao='Receita de pão.') for i in range(121)]
        ms[-1]['transcricao']='O foguete explodiu no lançamento.'
        def ia(prompt):
            return {'resultados':[dict(id=0,relevancia=.9,evidencia='O foguete explodiu')]} if 'O foguete explodiu' in prompt else {'resultados':[]}
        r=buscar_semantico(ms,'acidente espacial',ia)
        self.assertEqual(r[0]['inicio'],120)

    def test_grupo_ia_nao_pode_sumir_com_video(self):
        vs=[dict(titulo='Receita de pão'),dict(titulo='Lançamento de foguete')]
        gs=agrupar_semantico(vs,lambda _: {'grupos':[[0]]})
        self.assertEqual(sum(map(len,gs)),2)

    def test_calibracao_sem_historico_pede_revisao(self):
        r=calibracao.decidir(dict(verificavel=True,nota=8),[dict(confianca=.99)],'A',7,observacoes=[])
        self.assertFalse(r['automatico'])

    def test_calibracao_aprovacao_e_rejeicao(self):
        a=dict(verificavel=True,nota=8,criterios={k:dict(nota=8) for k in CRITERIOS});p=[dict(confianca=.99)]
        self.assertTrue(calibracao.decidir(a,p,'A',7,observacoes=[(8,1)]*30)['automatico'])
        self.assertFalse(calibracao.decidir(a,p,'A',7,observacoes=[(8,0)]*30)['automatico'])

    def test_clock_compensa_rede_e_player(self):
        self.assertEqual(posicao(100,5,2,-1,990,1000),86)
        with self.assertRaises(ValueError):posicao(100,181)
        with self.assertRaises(ValueError):posicao(100,capturado_em=0,agora=1000)

    def test_frame_ambiguo_nao_corrige(self):
        self.assertFalse(escolher([(0,0),(5,0),(10,0)],'0000000000000000',5)['confirmado'])
        r=escolher([(0,0xffff),(5,0),(10,0xffffffffffffffff)],'0000000000000000',3)
        self.assertTrue(r['confirmado']);self.assertEqual(r['instante'],5)

    def test_dhash_dimensoes(self):
        self.assertEqual(dhash(bytes(range(72))),0)
        with self.assertRaises(ValueError):dhash(b'')

    def test_voz_pessoa_associada_e_abstencao(self):
        v=[np.array([1.,0.])]*12+[np.array([0.,1.])]*12
        a=[8.]*12+[1.]*12;b=[1.]*12+[8.]*12
        labels,rel=associar(v,a,b,[True]*24)
        self.assertTrue(rel['confiavel']);self.assertEqual(labels[:12],['A']*12);self.assertEqual(labels[12:],['B']*12)
        labels,rel=associar(v,[3.]*24,[3.]*24,[True]*24)
        self.assertFalse(rel['confiavel']);self.assertTrue(all(x is None for x in labels))

    def test_sem_audio_nao_inventa_identidade(self):
        vetores=vetores_voz(np.zeros(32000,dtype=np.float32),[.4,.8,1.2])
        self.assertEqual(vetores,[None,None,None])

    def test_extracao_acustica_distingue_sinais_e_associa_movimento(self):
        t=np.arange(32000)/16000
        audio=np.concatenate([.2*np.sin(2*np.pi*220*t),.2*np.sin(2*np.pi*800*t)]).astype(np.float32)
        tempos=[.4+i*.2 for i in range(7)]+[2.4+i*.2 for i in range(7)]
        v=vetores_voz(audio,tempos)
        labels,rel=associar(v,[8.]*7+[1.]*7,[1.]*7+[8.]*7,[True]*14)
        self.assertTrue(rel['confiavel'])
        self.assertEqual(labels,['A']*7+['B']*7)

    def test_bootstrap_exige_amostra_e_separacao(self):
        self.assertFalse(contraste([100]*3,[1]*3)['conclusivo'])
        self.assertFalse(contraste([10]*10,[10]*10)['conclusivo'])
        self.assertTrue(contraste([100]*10,[10]*10)['conclusivo'])

    def test_tiktok_data_brasileira_e_plataformas(self):
        agora=dt.datetime(2026,11,2,13,tzinfo=dt.timezone.utc)
        f=dict(tt_stats=dict(data='01/11/2026 09:00',views=150))
        # Horário explícito local: usa a mesma conversão de timezone do aplicativo.
        data=dt.datetime(2026,11,1,9).astimezone()
        resultados.registrar_medicao(f,'tiktok',data+dt.timedelta(hours=25))
        self.assertEqual(resultados.views_comparaveis(f,'tiktok'),150)
        self.assertIsNone(resultados.views_comparaveis(f,'youtube'))
        f2=dict(tt_stats=dict(data='01/11/2026',views=150))
        resultados.registrar_medicao(f2,'tiktok',agora)
        self.assertNotIn('views_24h',f2)

    def test_ab_sem_repeticoes_nao_declara_vencedor(self):
        a=dict(grupo_ab='g',variante='A',fonte='x',inicio=0,fim=60,pergunta='A',views_24h={'youtube':500})
        b=dict(a,variante='B',pergunta='B',views_24h={'youtube':100})
        with patch.object(resultados,'fichas',return_value=[(None,a),(None,b)]):
            r=resultados.comparar_ab()
        self.assertEqual(r[0]['estado'],'exploratorio');self.assertNotIn('vencedora',r[0])

    def test_aprendizado_separa_youtube_e_tiktok(self):
        fichas=[]
        for longa in (False,True):
            for i in range(8):
                f=dict(perfil='P',canal='C',duracao=60,idioma='pt',pergunta='Pergunta muito longa que ultrapassa trinta e cinco caracteres?' if longa else 'CURTA?',
                       views_24h=dict(youtube=10 if longa else 100,tiktok=100 if longa else 10))
                fichas.append((None,f))
        with tempfile.TemporaryDirectory() as d,patch.object(resultados,'fichas',return_value=fichas),patch.object(resultados,'ARQ_APRENDIZADO',Path(d)/'aprendizado.json'):
            r=resultados.gerar_aprendizado()
        self.assertTrue(any('curta' in l and '10.0x' in l for l in r['por_plataforma']['youtube']['linhas']))
        self.assertTrue(any('longa' in l and '10.0x' in l for l in r['por_plataforma']['tiktok']['linhas']))
        json.dumps(r)  # A estrutura de plataformas não pode conter referência circular.

    def test_ab_replicado_mesma_hipotese(self):
        fichas=[]
        for i in range(6):
            a=dict(grupo_ab=str(i),hipotese_ab='tamanho',variante='A',fonte=str(i),inicio=0,fim=60,pergunta='A',views_24h={'youtube':500})
            b=dict(a,variante='B',pergunta='B',views_24h={'youtube':100})
            fichas.extend([(None,a),(None,b)])
        with patch.object(resultados,'fichas',return_value=fichas):r=resultados.comparar_ab()
        self.assertTrue(all(x.get('vencedora')=='A' and x['repeticoes']==6 for x in r))

    def test_horario_nao_confunde_canal_grande_com_hora_melhor(self):
        fichas=[]
        for canal,hora,views in [('pequeno',12,10),('grande',18,1000)]:
            for i in range(16):
                f=dict(perfil='P',canal=canal,duracao=60,youtube_quando=f'2026-11-01T{hora}:00:00',views_24h={'youtube':views})
                fichas.append((None,f))
        with patch.object(resultados,'fichas',return_value=fichas):r=resultados.melhores_horarios('P')
        self.assertEqual(r,[])

    def test_checkpoints_de_descarte(self):
        with tempfile.TemporaryDirectory() as d,patch.object(conclusao_tarefas,'BASE',Path(d)):
            conclusao_tarefas.confirmar('job',None)
            self.assertEqual(conclusao_tarefas.recuperar('job'),(True,None))

    def test_retomada_analise_nao_muda_escolhas_nem_duplica_filhos(self):
        import monitor
        from fila_tarefas import FilaTarefas
        with tempfile.TemporaryDirectory() as d:
            fila=FilaTarefas(Path(d)/'fila.db')
            try:
                tarefa=dict(_job_id='p',tipo='yt_transcricao',url='https://example.invalid',
                             base=dict(tipo='corte',fonte='https://example.invalid',meta={}))
                fila.adicionar(tarefa);t=fila.proxima()
                cfg=dict(cortes_por_video_youtube=1,duracao_corte_seg=60)
                with patch.object(monitor.momentos,'achar_momentos',return_value=([dict(inicio=10,fim=70)],{})) as analisar:
                    monitor.executar(t,cfg,fila)
                    monitor.executar(t,cfg,fila)
                    self.assertEqual(analisar.call_count,1)
                self.assertEqual(len(list(fila)),1)
            finally:fila.db.close()

    def test_conclusao_fraca_bloqueia_mesmo_com_media_alta(self):
        a=dict(verificavel=True,nota=8,criterios={k:dict(nota=9) for k in CRITERIOS})
        a['criterios']['conclusao']['nota']=2
        self.assertFalse(calibracao.decidir(a,[dict(confianca=.99)],'A',7,observacoes=[(8,1)]*30)['automatico'])

    def test_saida_confirmada_recupera_sem_fila(self):
        with tempfile.TemporaryDirectory() as d,patch.object(conclusao_tarefas,'BASE',Path(d)/'jobs'):
            job='job';p=Path(d)/('corte_'+conclusao_tarefas.identificador(job)+'.mp4');p.write_bytes(b'x'*200)
            salvar_json(p.with_suffix('.json'),{'_job_id':job})
            salvar_json(p.with_suffix('.qualidade.json'),{'aprovado':True})
            conclusao_tarefas.confirmar(job,p)
            with patch('qualidade.inspecionar',return_value={'aprovado':True}):
                self.assertEqual(conclusao_tarefas.recuperar(job),(True,p))
            p.unlink()
            self.assertFalse(conclusao_tarefas.recuperar(job)[0])


if __name__=='__main__':unittest.main()
