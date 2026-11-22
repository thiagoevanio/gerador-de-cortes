"""Revisão de momentos, busca textual e memória editorial por perfil."""
import hashlib
import json
import os
import queue
import re
import threading
import time
import unicodedata
from pathlib import Path
from infraestrutura import salvar_json, exclusividade

BASE = Path(__file__).resolve().parent


def registrar_feedback(perfil, decisao, motivo, trecho=None):
    if decisao not in ('aprovado', 'rejeitado', 'ajustado'):
        raise ValueError('Decisão inválida.')
    ident = hashlib.sha256(perfil.encode()).hexdigest()[:16]
    pasta = BASE / 'feedback_editorial'
    pasta.mkdir(exist_ok=True)
    arquivo = pasta / (ident + '.json')
    with exclusividade(pasta / (ident + '.lock'), timeout=10):
        try:
            dados = json.loads(arquivo.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            dados = []
        dados.append(dict(perfil=perfil, decisao=decisao, motivo=motivo[:500], trecho=trecho, quando=time.time()))
        salvar_json(arquivo, dados[-200:])


def memoria(perfil=None):
    if perfil is None:
        import cortes
        perfil = cortes.PERFIL_EM_USO
    arquivo = BASE / 'feedback_editorial' / (hashlib.sha256(perfil.encode()).hexdigest()[:16] + '.json')
    try:
        dados = json.loads(arquivo.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return [f"Preferência editorial explícita ({x['decisao']}): {x['motivo']}" for x in dados[-8:] if x.get('motivo')]


def termos(texto):
    texto = unicodedata.normalize('NFKD', texto.lower()).encode('ascii', 'ignore').decode()
    ignorar = {'para', 'como', 'quando', 'sobre', 'esse', 'essa', 'ele', 'ela', 'uma', 'que', 'com', 'dos', 'das'}
    return {x for x in re.findall(r'\w+', texto) if len(x) > 2 and x not in ignorar}


def buscar(momentos, consulta, usar_ia=False):
    from inteligencia_editorial import buscar_semantico
    ia=None;namespace=''
    if usar_ia:
        import cortes
        if cortes.IA_PRINCIPAL!='nenhuma':
            ia=lambda p: cortes.ia_json(p, tarefa="busca")
            namespace=f'{cortes.IA_PRINCIPAL}:{cortes.MODELO_LOCAL}:{cortes.GEMINI_MODELO}:{cortes.ECONOMICO}'
    return buscar_semantico(momentos,consulta,ia,namespace)


def agrupar(videos):
    from inteligencia_editorial import agrupar_semantico
    import cortes
    cfg=cortes.carregar_config()
    ia=(lambda p: cortes.ia_json(p, tarefa="busca")) if cfg.get('agrupamento_semantico_ia',False) and cortes.IA_PRINCIPAL!='nenhuma' else None
    return agrupar_semantico(videos,ia)


def abrir(parent):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, simpledialog
    import cortes
    janela = tk.Toplevel(parent)
    janela.title('Central de edição — momentos e evidências')
    janela.geometry('1000x720')
    fonte, consulta = tk.StringVar(), tk.StringVar()
    perfil = tk.StringVar(value='Padrão')
    versao = tk.StringVar(value='direta')
    status = tk.StringVar(value='Informe uma URL ou um arquivo. A busca cobre os candidatos analisados.')
    estado = dict(momentos=[], banco=[], meta={}, fonte='', ocupado=False)
    eventos = queue.Queue()
    linha = ttk.Frame(janela, padding=10); linha.pack(fill='x')
    ttk.Entry(linha, textvariable=fonte).pack(side='left', fill='x', expand=True)
    ttk.Button(linha, text='Arquivo', command=lambda: fonte.set(filedialog.askopenfilename() or fonte.get())).pack(side='left')
    ttk.Combobox(linha, textvariable=perfil, values=cortes.nomes_perfis(), state='readonly', width=16).pack(side='left', padx=5)
    tabela = ttk.Treeview(janela, columns=('ini', 'fim', 'motivo'), show='headings', height=10)
    for nome, largura in [('ini', 80), ('fim', 80), ('motivo', 720)]:
        tabela.heading(nome, text=nome.capitalize()); tabela.column(nome, width=largura)
    detalhe = tk.Text(janela, height=9, wrap='word')

    def trabalho(fn):
        if estado['ocupado']:
            return
        estado['ocupado'] = True
        status.set('Processando…')
        def rodar():
            try:
                eventos.put(('ok', fn()))
            except Exception as e:
                eventos.put(('erro', str(e)))
        threading.Thread(target=rodar, daemon=True).start()

    def mostrar():
        if consulta.get().strip() and estado['meta'].get('transcricao_completa'):
            segmentos = estado['meta']['transcricao_completa']
            palavras = termos(consulta.get())
            for a,b,txt in segmentos:
                if palavras & termos(txt) and not any(m['inicio'] <= a <= m['fim'] for m in estado['momentos']):
                    ini, fim = max(0,a-8), min(estado["meta"].get("duracao", b+12), b+12)
                    estado['momentos'].append(dict(inicio=ini, fim=fim, motivo='Correspondência textual à busca; revisar contexto',
                        transcricao=txt, evidencias=dict(limites_validados=False, revisao_humana=True)))
        tabela.delete(*tabela.get_children())
        for m in buscar(estado['momentos'], consulta.get()):
            idx = next(i for i,x in enumerate(estado['momentos']) if x['inicio']==m['inicio'] and x['fim']==m['fim'])
            tabela.insert('', 'end', iid=str(idx), values=(cortes.fmt_tempo(m['inicio']), cortes.fmt_tempo(m['fim']), m['motivo']))

    def pesquisa_semantica():
        consulta_atual, candidatos, p = consulta.get(), list(estado['banco'] or estado['momentos']), perfil.get()
        if estado['meta'].get('transcricao_completa'):
            for a,b,txt in estado['meta']['transcricao_completa']:
                candidatos.append(dict(inicio=max(0,a-8),fim=min(estado['meta'].get('duracao',b+12),b+12),
                                        transcricao=txt,motivo='Correspondência semântica: revisar contexto'))
        def fn():
            with cortes.contexto_render():
                cortes.aplicar_config(cortes.carregar_config(p))
                return ('busca',buscar(candidatos,consulta_atual,True))
        trabalho(fn)

    def analisar():
        origem, p = fonte.get().strip(), perfil.get()
        if not origem:
            return
        def fn():
            import momentos
            with cortes.contexto_render():
                cortes.aplicar_config(cortes.carregar_config(p))
                achados, meta = momentos.achar_momentos(origem, log=lambda t:eventos.put(('log', t)), completo=True)
            return ('analise', origem, achados, meta)
        trabalho(fn)

    ttk.Button(linha, text='Analisar momentos', command=analisar).pack(side='left')
    pesquisa = ttk.Frame(janela, padding=10); pesquisa.pack(fill='x')
    ttk.Entry(pesquisa, textvariable=consulta).pack(side='left', fill='x', expand=True)
    ttk.Button(pesquisa, text='Buscar por significado', command=pesquisa_semantica).pack(side='left')
    tabela.pack(fill='both', expand=True, padx=10)

    def selecionado():
        sel = tabela.selection()
        if not sel:
            raise ValueError('Selecione um momento.')
        m = estado['momentos'][int(sel[0])]
        intervalo = m.get('versoes', {}).get(versao.get(), m)
        return m, intervalo

    def detalhes(_=None):
        try:
            m, _ = selecionado()
        except ValueError:
            return
        detalhe.delete('1.0', 'end')
        detalhe.insert('1.0', json.dumps(m, ensure_ascii=False, indent=2))
    tabela.bind('<<TreeviewSelect>>', detalhes)
    detalhe.pack(fill='x', padx=10, pady=8)
    botoes = ttk.Frame(janela, padding=10); botoes.pack(fill='x')
    ttk.Combobox(botoes, textvariable=versao, values=['direta','contexto','historia'], state='readonly', width=12).pack(side='left')

    def executar(gerar=False):
        try:
            m, intervalo = selecionado()
        except ValueError as e:
            return messagebox.showinfo('Momento', str(e), parent=janela)
        origem, p = estado['fonte'], perfil.get()
        meta = dict(estado['meta'], editorial=m.get('evidencias', {}))
        def fn():
            if gerar:
                video = cortes.gerar_corte(origem, intervalo['inicio'], intervalo['fim'], perfil=p, meta=meta)
                return ('arquivo', str(video)) if video else ('mensagem', 'Descartado pela nota mínima.')
            import qualidade, tempfile
            pasta = BASE / 'analises' / 'previas'; pasta.mkdir(parents=True, exist_ok=True)
            # Download apenas do trecho quando a origem é remota.
            with tempfile.TemporaryDirectory(dir=pasta) as temp:
                fonte_local, a, b = origem, intervalo['inicio'], intervalo['fim']
                if re.match(r'^https?://', origem):
                    with cortes.contexto_render():
                        fonte_local, _ = cortes.baixar_trecho(origem, a, b, Path(temp))
                    a, b = 0, cortes.duracao_video(fonte_local)
                nome = hashlib.sha256((origem+str(intervalo)).encode()).hexdigest()[:16]+'.mp4'
                video = qualidade.previa(fonte_local, pasta/nome, a, b)
            return ('arquivo', str(video))
        trabalho(fn)

    ttk.Button(botoes, text='Prévia leve', command=executar).pack(side='left', padx=5)
    ttk.Button(botoes, text='Gerar corte escolhido', command=lambda: executar(True)).pack(side='left')
    def feedback(decisao):
        try:
            m, _ = selecionado()
        except ValueError:
            return
        motivo = simpledialog.askstring('Feedback editorial', 'O que deve ser aprendido neste perfil?', parent=janela)
        if motivo:
            registrar_feedback(perfil.get(), decisao, motivo, dict(m,fonte=estado["fonte"]))
            status.set('Feedback salvo no perfil selecionado.')
    for decisao in ['aprovado','rejeitado','ajustado']:
        ttk.Button(botoes, text=decisao.capitalize(), command=lambda d=decisao:feedback(d)).pack(side='left', padx=3)
    ttk.Label(janela, textvariable=status, wraplength=950).pack(fill='x', padx=10, pady=8)

    def receber():
        if not janela.winfo_exists():
            return
        while not eventos.empty():
            tipo, valor = eventos.get()
            if tipo == 'log':
                status.set(valor); continue
            estado['ocupado'] = False
            if tipo == 'erro':
                status.set('Falha: '+valor); continue
            if valor[0] == 'analise':
                _, origem, achados, meta = valor
                estado.update(momentos=achados, banco=list(achados), meta=meta, fonte=origem)
                pasta = BASE/'analises'; pasta.mkdir(exist_ok=True)
                salvar_json(pasta/(hashlib.sha256(origem.encode()).hexdigest()[:16]+'.json'), estado)
                mostrar(); status.set(f'{len(achados)} momentos. Revise as evidências e escolha uma versão.')
            elif valor[0] == 'busca':
                estado['momentos'] = valor[1]
                consulta.set(''); mostrar()
                status.set('Resultados por significado. O campo busca informa se houve avaliação da IA ou por conceitos locais.')
            elif valor[0] == 'arquivo':
                if os.name == 'nt': os.startfile(valor[1])
                status.set(valor[1])
            else:
                status.set(valor[1])
        janela.after(150, receber)
    receber()
    return janela


def editar_legenda(parent, video):
    import tkinter as tk
    from tkinter import ttk, messagebox
    import cortes
    video = Path(video)
    arquivo = video.with_suffix('.transcricao.json')
    try:
        palavras = json.loads(arquivo.read_text(encoding='utf-8'))['palavras']
    except (OSError, ValueError, KeyError):
        return messagebox.showinfo('Legenda', 'Este vídeo não tem transcrição editável. Gere novamente para criar o arquivo.')
    janela = tk.Toplevel(parent); janela.title('Revisar palavras e exportar SRT'); janela.geometry('700x500')
    incertas = sum(p.get('confianca', 1) < 0.6 for p in palavras)
    ttk.Label(janela, text=f'Uma palavra por linha, na mesma ordem. {incertas} palavras com confiança baixa, destacadas em amarelo.').pack(fill='x')
    texto = tk.Text(janela); texto.pack(fill='both', expand=True)
    texto.insert('1.0', '\n'.join(p['t'] for p in palavras))
    texto.tag_configure('incerta', background='#ffd600', foreground='#222222')
    for i, p in enumerate(palavras, 1):
        if p.get('confianca', 1) < 0.6:
            texto.tag_add('incerta', f'{i}.0', f'{i}.end')
    def ouvir():
        import qualidade
        i = min(len(palavras)-1, int(texto.index('insert').split('.')[0])-1)
        a, b = max(0, palavras[i]['ini']-1), palavras[i]['fim']+2
        pasta = BASE/'analises'/'previas'; pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta/'revisao_palavra.mp4'
        def fn():
            try:
                qualidade.previa(video, destino, a, b)
                if os.name == 'nt': os.startfile(str(destino))
            except Exception:
                pass
        threading.Thread(target=fn, daemon=True).start()
    ttk.Button(janela, text='Ouvir no ponto do cursor', command=ouvir).pack()
    def salvar():
        linhas = texto.get('1.0', 'end-1c').splitlines()
        if len(linhas) != len(palavras) or any(not l.strip() for l in linhas):
            return messagebox.showerror('Legenda', 'Mantenha a quantidade de palavras e não deixe linhas vazias.', parent=janela)
        revisadas = [dict(p, t=l.strip()) for p,l in zip(palavras, linhas)]
        salvar_json(arquivo, {'palavras': revisadas})
        cortes.gerar_srt(revisadas, linhas, video.with_suffix('.srt'))
        messagebox.showinfo('Salvo', 'Transcrição e SRT atualizados. Para queimar no vídeo, renderize novamente.', parent=janela)
    ttk.Button(janela, text='Salvar transcrição e SRT', command=salvar).pack()
    retorno = queue.Queue()
    revisando = {'ativo':False}
    def renderizar():
        if revisando['ativo']: return
        linhas = texto.get('1.0', 'end-1c').splitlines()
        if len(linhas) != len(palavras) or any(not l.strip() for l in linhas):
            return messagebox.showerror('Legenda', 'Mantenha uma palavra por linha.', parent=janela)
        revisadas = [dict(p, t=l.strip()) for p,l in zip(palavras,linhas)]
        revisando['ativo'] = True
        botao.configure(state='disabled', text='Renderizando…')
        def fn():
            try:
                from projeto_edicao import renderizar_revisao
                retorno.put((True, str(renderizar_revisao(video, revisadas))))
            except Exception as e: retorno.put((False, str(e)))
        threading.Thread(target=fn, daemon=True).start()
    botao = ttk.Button(janela, text='Gerar vídeo com legenda revisada', command=renderizar); botao.pack()
    def receber_revisao():
        if not janela.winfo_exists(): return
        if not retorno.empty():
            ok, resultado = retorno.get(); revisando['ativo']=False
            botao.configure(state='normal', text='Gerar vídeo com legenda revisada')
            if ok: messagebox.showinfo('Vídeo revisado', resultado, parent=janela)
            else: messagebox.showerror('Revisão', resultado, parent=janela)
        janela.after(200, receber_revisao)
    receber_revisao()


def configurar(parent):
    import tkinter as tk
    from tkinter import ttk, messagebox
    import cortes
    cfg = cortes.carregar_config()
    janela = tk.Toplevel(parent); janela.title('Qualidade e recursos'); janela.geometry('720x760')
    viewport=tk.Canvas(janela,highlightthickness=0)
    rolagem=ttk.Scrollbar(janela,orient='vertical',command=viewport.yview)
    viewport.configure(yscrollcommand=rolagem.set)
    rolagem.pack(side='right',fill='y');viewport.pack(side='left',fill='both',expand=True)
    conteudo=ttk.Frame(viewport)
    item=viewport.create_window(0,0,window=conteudo,anchor='nw')
    conteudo.bind('<Configure>',lambda e:viewport.configure(scrollregion=viewport.bbox('all')))
    viewport.bind('<Configure>',lambda e:viewport.itemconfigure(item,width=e.width))
    perfil_config = tk.StringVar(value='Padrão')
    cb = ttk.Combobox(conteudo, textvariable=perfil_config, values=cortes.nomes_perfis(), state='readonly')
    cb.pack(fill='x', padx=15, pady=5)
    campos = {}
    for chave, titulo, padrao in [
        ('vocabulario', 'Nomes e termos para a transcrição do perfil', ''),
        ('hipotese_ab', 'Hipótese para próximos testes A/B (ex.: pergunta curta)', ''),
        ('cpu_threads', 'Threads de CPU', 4),
        ('max_tarefas_pendentes', 'Limite de fila para novas descobertas automáticas', 100),
        ('retencao_gravacoes_dias', 'Apagar gravações sem dependências após dias (0 = desativado)', 0), ('min_disco_gb', 'Reserva mínima de disco (GB)', 2),
        ('max_chamadas_ia_dia', 'Máximo de chamadas de IA por dia (0 = livre)', 0),
        ('timeout_ffmpeg_seg', 'Tempo máximo por operação FFmpeg (segundos)', 3600),
        ('autonomia_confianca', 'Nota editorial mínima para automáticos (0 = desligado)', 0),
        ('duracao_longo_seg', 'Corte longo 16:9: tamanho alvo em segundos (180 a 480)', 240),
        ('compilacao_minutos', 'Compilação: tamanho alvo em minutos', 8)]:
        ttk.Label(conteudo, text=titulo).pack(anchor='w', padx=15, pady=(7,0))
        v = tk.StringVar(value=str(cfg.get(chave, padrao))); campos[chave] = v
        ttk.Entry(conteudo, textvariable=v).pack(fill='x', padx=15)
    tecnica = tk.BooleanVar(value=cfg.get('revisao_tecnica', False))
    segmentada = tk.BooleanVar(value=cfg.get('gravacao_segmentada', False))
    ttk.Checkbutton(conteudo, text='Gravar lives em segmentos recuperáveis (novas gravações)', variable=segmentada).pack(anchor='w', padx=15)
    ampla = tk.BooleanVar(value=cfg.get('analise_ampla', False))
    ttk.Checkbutton(conteudo, text='Análise ampla do áudio para busca textual (mais lenta)', variable=ampla).pack(anchor='w', padx=15)
    grupos_ia=tk.BooleanVar(value=cfg.get('agrupamento_semantico_ia',False))
    ttk.Checkbutton(conteudo,text='Agrupar acontecimentos com IA (chamada adicional no radar)',variable=grupos_ia).pack(anchor='w',padx=15)
    transcricao = tk.BooleanVar(value=cfg.get('retranscrever_incertos', False))
    ttk.Label(conteudo, text='Legenda do corte final (a busca de momentos usa sempre o base, rápido):').pack(anchor='w', padx=15, pady=(10,0))
    nomes_whisper = {'small (recomendado)': 'small', 'base (mais rápido)': 'base', 'turbo (mais preciso, ~3x mais lento; baixa 1,6 GB uma vez)': 'turbo'}
    v_whisper = tk.StringVar(value=next((k for k, v in nomes_whisper.items() if v == cfg.get('whisper_final', 'small')), 'small (recomendado)'))
    ttk.Combobox(conteudo, textvariable=v_whisper, values=list(nomes_whisper), state='readonly').pack(fill='x', padx=15)
    ttk.Label(conteudo, text='Economia (desligado = gasta menos IA e processador):').pack(anchor='w', padx=15, pady=(10,0))
    extras_eco = {}
    for chave, texto, padrao in [
            ('avaliacao_editorial', 'Avaliação editorial pela IA em todo corte (+tokens por corte)', False),
            ('analise_heatmap_ia', 'Conferir com IA mesmo quando o YouTube tem o gráfico "mais repetidos"', False),
            ('whisper_preciso', 'Transcrição mais precisa (beam 3, ~2x mais lenta)', False),
            ('guardar_projeto_edicao', 'Guardar receita pra corrigir legenda sem IA (ocupa disco)', True),
            ('atualizar_numeros_auto', 'Robô atualiza as views do YouTube sozinho a cada 3h', True),
            ('ia_lote', 'Vários cortes do mesmo vídeo = 1 chamada de IA só', True),
            ('correcoes_delta', 'IA envia só palavras corrigidas em vez da transcrição inteira (-75% tokens)', True),
            ('usar_chat_vod', 'Live antiga: baixar o chat e usar onde ele explodiu (sem IA)', True),
            ('compilacao_deitada', 'Compilação com o trecho original deitado (tela cheia)', True),
            ('usar_gpu_encoder', 'Usar o acelerador de vídeo do PC (Intel/Nvidia/AMD) quando tiver', True),
            ('reduzir_chiado', 'Reduzir chiado do microfone (desligue se a live tiver música alta)', True)]:
        extras_eco[chave] = tk.BooleanVar(value=cfg.get(chave, padrao))
        ttk.Checkbutton(conteudo, text=texto, variable=extras_eco[chave]).pack(anchor='w', padx=15)
    ttk.Checkbutton(conteudo, text='Revisão técnica completa após renderizar', variable=tecnica).pack(anchor='w', padx=15)
    ttk.Checkbutton(conteudo, text='Segunda transcrição seletiva de palavras incertas', variable=transcricao).pack(anchor='w', padx=15)
    calibracao_texto=tk.StringVar()
    ttk.Label(conteudo,textvariable=calibracao_texto,wraplength=650).pack(anchor='w',padx=15,pady=8)
    def selecionar(_=None):
        selecionado = cortes.carregar_config(perfil_config.get())
        for k in ('vocabulario','autonomia_confianca','hipotese_ab'):
            campos[k].set(str(selecionado.get(k, '' if k in ('vocabulario','hipotese_ab') else 0)))
        transcricao.set(selecionado.get('retranscrever_incertos', False))
        from calibracao import amostras
        calibracao_texto.set(f'Avaliações humanas utilizáveis neste perfil: {len(amostras(perfil_config.get()))}. A autonomia exige pelo menos 20 comparáveis e evidências suficientes.')
    cb.bind('<<ComboboxSelected>>', selecionar)
    selecionar()
    def salvar():
        try:
            novos = {k:v.get() for k,v in campos.items()}
            for k in ('cpu_threads','max_chamadas_ia_dia','timeout_ffmpeg_seg','max_tarefas_pendentes','retencao_gravacoes_dias','duracao_longo_seg','compilacao_minutos'):
                novos[k] = int(novos[k])
            for k in ('min_disco_gb','autonomia_confianca'):
                novos[k] = float(novos[k])
            import math
            if not all(math.isfinite(novos[k]) for k in ('min_disco_gb','autonomia_confianca')) or not (1 <= novos['cpu_threads'] <= 128 and novos['min_disco_gb'] >= 0 and novos['max_chamadas_ia_dia'] >= 0 and novos['timeout_ffmpeg_seg'] >= 60 and 0 <= novos['autonomia_confianca'] <= 10 and novos['max_tarefas_pendentes'] >= 1 and novos['retencao_gravacoes_dias'] >= 0
                    and 60 <= novos['duracao_longo_seg'] <= 900 and 2 <= novos['compilacao_minutos'] <= 30):
                raise ValueError()
        except ValueError:
            return messagebox.showerror('Configuração', 'Verifique os números informados.', parent=janela)
        atual = cortes.carregar_config(); atual.update({k:v for k,v in novos.items() if k not in cortes.CHAVES_PERFIL}, revisao_tecnica=tecnica.get(), gravacao_segmentada=segmentada.get(), analise_ampla=ampla.get(), agrupamento_semantico_ia=grupos_ia.get(), **{k: v.get() for k, v in extras_eco.items()}, whisper_final=nomes_whisper.get(v_whisper.get(), 'small'))
        cortes.salvar_config(atual)
        do_perfil = cortes.carregar_config(perfil_config.get()); do_perfil.update(novos, retranscrever_incertos=transcricao.get())
        cortes.salvar_perfil(do_perfil, perfil_config.get())
        if hasattr(parent, 'cfg'): parent.cfg.update(atual)
        janela.destroy()
    ttk.Button(conteudo, text='Salvar', command=salvar).pack(pady=8)
    def diagnosticar():
        from recursos import diagnostico
        resultado = diagnostico()
        messagebox.showinfo('Diagnóstico local', json.dumps(resultado, ensure_ascii=False, indent=2), parent=janela)
    ttk.Button(conteudo, text='Diagnóstico de instalação', command=diagnosticar).pack()
