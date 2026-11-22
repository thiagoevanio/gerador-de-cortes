"""Receita local para corrigir legendas sem executar novamente a análise com IA."""
import json
import shutil
from pathlib import Path
from infraestrutura import salvar_json


def guardar(saida, video, topo, faixa, extras, boom, receita):
    saida = Path(saida)
    pasta = saida.parent / '_edicao' / saida.stem
    pasta.mkdir(parents=True, exist_ok=True)
    def copiar(arquivo):
        if not arquivo:
            return None
        arquivo = Path(arquivo)
        destino = pasta/arquivo.name
        if arquivo.resolve() != destino.resolve():
            shutil.copy2(arquivo, destino)
        return destino.name
    er = dict(receita.get('estilo_render') or {})
    if er.get('sfx'):
        er['sfx'] = [dict(x, arquivo=copiar(x['arquivo'])) for x in er['sfx'] if x.get('arquivo')]
    if (er.get('musica') or {}).get('arquivo') and Path(er['musica']['arquivo']).exists():
        er['musica'] = dict(er['musica'], arquivo=copiar(er['musica']['arquivo']))
    else:
        er.pop('musica', None)
    if receita.get('foto') and Path(receita['foto']).exists():
        receita = dict(receita, foto=copiar(receita['foto']))
    else:
        receita = dict(receita, foto=None)
    receita = dict(receita, estilo_render=er, video=copiar(video), topo=copiar(topo), faixa=copiar(faixa), boom=copiar(boom),
                   extras=[dict(e, png=copiar(e['png'])) for e in extras])
    salvar_json(pasta/'receita.json', receita)
    return str(pasta.relative_to(saida.parent))


def _previa(receita):
    """A prévia do gancho (3.21+) é montada no render: a revisão precisa dela, senão a legenda
    (que já está na linha do tempo com a prévia) sai fora de sincronia."""
    p = receita.get('previa')
    return (float(p[0]), float(p[1])) if isinstance(p, (list, tuple)) and len(p) == 2 else None


def renderizar_revisao(video, palavras):
    import cortes
    video = Path(video).resolve()
    ficha = json.loads(video.with_suffix('.json').read_text(encoding='utf-8'))
    projeto = ficha.get('projeto_edicao')
    if not projeto:
        raise ValueError('Este corte não tem receita de edição. Gere-o novamente para habilitar essa função.')
    pasta = (video.parent/projeto).resolve()
    if not pasta.is_relative_to((video.parent/'_edicao').resolve()):
        raise ValueError('Receita fora da pasta de edição.')
    if not (pasta/'receita.json').exists():
        raise ValueError('O projeto de edição deste corte foi apagado na limpeza automática (projetos antigos). Gere o corte de novo pra reeditar.')
    r = json.loads((pasta/'receita.json').read_text(encoding='utf-8'))
    def local(nome):
        if not nome:
            return None
        arquivo = (pasta/nome).resolve()
        if not arquivo.is_relative_to(pasta):
            raise ValueError('Recurso fora da receita.')
        return arquivo
    textos = [p['t'] for p in palavras]
    try:                                   # nomes que você corrigiu no editor entram no glossário do canal
        import ia_aprende
        antigas = json.loads(video.with_suffix('.transcricao.json').read_text(encoding='utf-8'))['palavras']
        if len(antigas) == len(palavras):
            ia_aprende.aprender_correcoes(ficha.get('canal'), [p['t'] for p in antigas], textos, 'dono')
    except Exception:
        pass
    with cortes.contexto_render():
        cortes.checar_ffmpeg()
        cfg = cortes.carregar_config(); cfg.update(r['config_visual'])
        cortes.aplicar_config(cfg)
        ass = cortes.gerar_ass(palavras, textos, pasta/'revisada.ass', duracao=r['duracao'],
                              margem=r['margem'], falantes=r.get('falantes'),
                              textos_extra=[tuple(x) for x in r.get('textos_extra') or []],
                              template=r.get('template') or 'Clássico')
        destino = video.with_name(video.stem+'_revisado.mp4')
        i = 2
        while destino.exists():
            destino = video.with_name(video.stem+f'_revisado_{i}.mp4'); i += 1
        cortes.renderizar(local(r['video']), local(r['topo']), ass, destino, r['modo'],
                          local(r['faixa']), r['y_faixa'], r.get('expr_x'), r.get('gancho_t'), local(r.get('boom')),
                          layout=r.get('layout'), extras=[dict(e, png=local(e['png'])) for e in r.get('extras', [])],
                          estilo_render=r.get('estilo_render'), previa=_previa(r))
        cortes.gerar_srt(palavras, textos, destino.with_suffix('.srt'))
        nova = {k:v for k,v in ficha.items() if k not in ('youtube_id','youtube_quando','yt_stats','tt_stats','tiktok','grupo_ab','variante','views_24h','medicoes')}
        nova.update(status='novo', revisado_de=video.name)
        salvar_json(destino.with_suffix('.json'), nova)
        salvar_json(destino.with_suffix('.transcricao.json'), dict(palavras=palavras))
        return destino


_ESTATISTICAS = ('youtube_id', 'youtube_quando', 'yt_stats', 'tt_stats', 'tiktok', 'grupo_ab', 'variante',
                 'views_24h', 'medicoes', 'capa', 'ab_variou', 'hipotese_ab')


def pode_trocar_pergunta(video):
    """True se dá pra refazer só a pergunta deste corte sem baixar nem chamar IA (cortes da 3.11+)."""
    try:
        video = Path(video)
        ficha = json.loads(video.with_suffix('.json').read_text(encoding='utf-8'))
        r = json.loads((video.parent/ficha['projeto_edicao']/'receita.json').read_text(encoding='utf-8'))
        return 'clean' in r and video.with_suffix('.transcricao.json').exists()
    except (OSError, ValueError, KeyError, TypeError):
        return False


def trocar_pergunta(video, pergunta, destaque=None):
    """Refaz o corte só com outra pergunta (faixa ou texto do gancho), reaproveitando a edição pronta:
    sem download, sem transcrição e sem IA. Devolve o novo .mp4 (com ficha e receita próprias)."""
    import cortes
    import acabamento
    video = Path(video).resolve()
    ficha = json.loads(video.with_suffix('.json').read_text(encoding='utf-8'))
    projeto = ficha.get('projeto_edicao')
    if not projeto:
        raise ValueError('Este corte não tem receita de edição.')
    pasta = (video.parent/projeto).resolve()
    if not pasta.is_relative_to((video.parent/'_edicao').resolve()):
        raise ValueError('Receita fora da pasta de edição.')
    if not (pasta/'receita.json').exists():
        raise ValueError('O projeto de edição deste corte foi apagado na limpeza automática (projetos antigos). Gere o corte de novo pra reeditar.')
    r = json.loads((pasta/'receita.json').read_text(encoding='utf-8'))
    if 'clean' not in r:
        raise ValueError('Corte antigo: a receita não guarda os dados da faixa.')
    arq_palavras = video.with_suffix('.transcricao.json')
    palavras = json.loads(arq_palavras.read_text(encoding='utf-8'))['palavras'] if arq_palavras.exists() else []
    textos = [p['t'] for p in palavras]

    def local(nome):
        if not nome:
            return None
        arquivo = (pasta/nome).resolve()
        if not arquivo.is_relative_to(pasta):
            raise ValueError('Recurso fora da receita.')
        return arquivo
    with cortes.contexto_render():
        cortes.checar_ffmpeg()
        cfg = cortes.carregar_config(); cfg.update(r['config_visual'])
        cortes.aplicar_config(cfg)
        pergunta = cortes._limpar_pergunta(pergunta) or str(pergunta).strip().upper()
        destaque = destaque if destaque is not None else acabamento.destaque_auto(pergunta)
        temporarios = []
        trabalho = pasta/'_troca'
        trabalho.mkdir(exist_ok=True)
        extras_txt = [tuple(x) for x in r.get('textos_extra') or []]
        if r['clean']:                                   # a pergunta é o texto do gancho na tela
            tinha = [x for x in extras_txt if x[3] in ('Gancho', 'GanchoMeio')]
            extras_txt = [x for x in extras_txt if x[3] not in ('Gancho', 'GanchoMeio')]
            if tinha:
                pos = cortes.posicao_gancho(tinha[0][2])     # mantém o lugar (desviando do rosto)
                extras_txt.append((tinha[0][0], tinha[0][1], pos + cortes.texto_gancho_ass(pergunta, destaque),
                                   tinha[0][3]))
            topo, faixa, y_faixa = local(r['topo']), local(r['faixa']), r['y_faixa']
        else:
            foto = local(r.get('foto'))
            if not foto and not r.get('so_faixa'):
                raise ValueError('A receita não guardou a foto do topo.')
            topo, faixa, yb = cortes.montar_topo(foto, pergunta, destaque, r.get('canal', ''), trabalho,
                                                 inteira=bool(r.get('eh_thumbnail')), so_faixa=bool(r.get('so_faixa')))
            y_faixa = yb + (r['y_faixa'] - r.get('y_base_faixa', r['y_faixa']))
            # o render lê as imagens pelo nome, na pasta do vídeo: nome único pra não pegar a faixa antiga
            import uuid
            marca = uuid.uuid4().hex[:8]

            def trazer(img, prefixo):
                if not img:
                    return None
                alvo = pasta/f'{prefixo}_{marca}{Path(img).suffix}'
                shutil.copy2(img, alvo)
                return alvo
            topo, faixa = trazer(topo, 'topo'), trazer(faixa, 'faixa')
            temporarios = [x for x in (topo, faixa) if x]
        ass = None
        if (r.get('legenda', True) and palavras) or extras_txt or cortes.MARCA:
            ass = cortes.gerar_ass(palavras, textos, pasta/'troca.ass', duracao=r['duracao'],
                                   legenda=r.get('legenda', True), margem=r['margem'], falantes=r.get('falantes'),
                                   textos_extra=extras_txt, template=r.get('template') or 'Clássico')
        destino = video.with_name(video.stem+'_pergunta.mp4')
        i = 2
        while destino.exists():
            destino = video.with_name(video.stem+f'_pergunta_{i}.mp4'); i += 1
        extras = [dict(e, png=local(e['png'])) for e in r.get('extras', [])]
        cortes.renderizar(local(r['video']), topo, ass, destino, r['modo'], faixa, y_faixa, r.get('expr_x'),
                          r.get('gancho_t'), local(r.get('boom')), layout=r.get('layout'), extras=extras,
                          estilo_render=r.get('estilo_render'), previa=_previa(r))
        if palavras:
            cortes.gerar_srt(palavras, textos, destino.with_suffix('.srt'))
            salvar_json(destino.with_suffix('.transcricao.json'), dict(palavras=palavras))
        antigas = [ficha.get('pergunta')] + list(ficha.get('perguntas_alternativas') or [])
        nova = {k: v for k, v in ficha.items() if k not in _ESTATISTICAS}
        nova.update(status='novo', pergunta=pergunta, refeito_de=video.name,
                    perguntas_alternativas=[q for q in dict.fromkeys(antigas) if q and q != pergunta][:4])
        er = dict(r.get('estilo_render') or {})
        for chave in ('sfx',):
            if er.get(chave):
                er[chave] = [dict(x, arquivo=str(local(x['arquivo']))) for x in er[chave] if x.get('arquivo')]
        if (er.get('musica') or {}).get('arquivo'):
            er['musica'] = dict(er['musica'], arquivo=str(local(er['musica']['arquivo'])))
        receita = dict(r, estilo_render=er, y_faixa=y_faixa, textos_extra=extras_txt,
                       foto=str(local(r['foto'])) if r.get('foto') else None)
        for chave in ('video', 'topo', 'faixa', 'boom', 'extras'):
            receita.pop(chave, None)
        nova['projeto_edicao'] = guardar(destino, local(r['video']), topo, faixa, extras, local(r.get('boom')),
                                         receita)
        try:
            capa = acabamento.gerar_capa(destino, destino.with_suffix('.capa.jpg'), 1.8)
            if capa:
                nova['capa'] = capa.name
        except Exception:
            pass
        txt = video.with_suffix('.txt')
        if txt.exists():
            shutil.copy2(txt, destino.with_suffix('.txt'))
        salvar_json(destino.with_suffix('.json'), nova)
        try:                               # a troca ensina o gosto do dono pra IA
            import ia_aprende
            ia_aprende.registrar_troca_pergunta(ficha.get('perfil'), ficha.get('pergunta'), pergunta,
                                                da_lista=pergunta in (ficha.get('perguntas_alternativas') or []))
        except Exception:
            pass
        shutil.rmtree(trabalho, ignore_errors=True)
        for x in temporarios:                     # as cópias já estão na receita nova
            x.unlink(missing_ok=True)
        return destino
