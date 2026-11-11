"""Teste de integração de mídia: FFmpeg real, sem internet e sem chamadas de IA."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cortes
from gravacao_segmentada import snapshot, duracao
from projeto_edicao import renderizar_revisao
from qualidade import inspecionar, previa
import conclusao_tarefas


class Midia(unittest.TestCase):
    def test_render_legenda_revisada_e_segmentos(self):
        cortes.checar_ffmpeg()
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            fonte = pasta/'fonte.mp4'
            subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','testsrc2=size=320x180:rate=25',
                            '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','3','-c:v','libx264',
                            '-g','25','-c:a','aac',str(fonte)], check=True,capture_output=True)
            segmentos = pasta/'segmentos';segmentos.mkdir()
            subprocess.run(['ffmpeg','-y','-v','error','-i',str(fonte),'-c','copy','-f','hls','-hls_time','1',
                            '-hls_list_size','0','-hls_playlist_type','event','-hls_segment_filename',str(segmentos/'segmento_%03d.ts'),
                            str(segmentos/'captura.m3u8')], check=True,capture_output=True)
            self.assertAlmostEqual(duracao(snapshot(segmentos)),3,delta=0.1)
            palavras = [dict(t=t,ini=i*.4,fim=i*.4+.3,confianca=.9) for i,t in enumerate(['Este','é','um','teste.'])]
            cfg = dict(cortes.CONFIG_PADRAO, seguir_rosto=False,tirar_silencios=False,tirar_vicios=False,layout='normal',
                       revisor=False,serie=False,checar_inedito=False,ia_principal='nenhuma',efeito_gancho=False,
                       gancho_inicio=False,revisao_tecnica=True,guardar_projeto_edicao=True)
            with patch.object(cortes,'carregar_config',return_value=cfg), patch.object(conclusao_tarefas,'BASE',pasta/'jobs'):
                final = cortes.gerar_corte(fonte,0,2,pergunta='TESTE DE LEGENDA',transcricao_teste=palavras,
                                           usar_claude=False,pasta_saida=pasta/'render',_job_id='teste_fluxo')
                self.assertTrue(inspecionar(final,2,True)['aprovado'])
                self.assertTrue(final.with_suffix('.qualidade.json').is_file())
                # Simula a fila ainda pendente após o arquivo e checkpoint terem sido gravados.
                with patch.object(cortes,'_gerar_corte',side_effect=AssertionError('Renderização duplicada')):
                    retomado=cortes.gerar_corte(fonte,0,2,_job_id='teste_fluxo')
                    self.assertEqual(retomado,final)
                self.assertEqual(len(list((pasta/'render').glob('*.mp4'))),1)
                palavras[-1]['t']='CORRIGIDO.'
                revisado = renderizar_revisao(final,palavras)
                self.assertTrue(inspecionar(revisado,2,True)['aprovado'])
                self.assertIn('CORRIGIDO.', revisado.with_suffix('.srt').read_text(encoding='utf-8'))
                self.assertTrue(final.exists())
                p = previa(revisado,pasta/'previa.mp4',0,1)
                self.assertTrue(inspecionar(p,1,True,False)['aprovado'])


if __name__ == '__main__':
    unittest.main()
