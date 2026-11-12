# Novas funções — 02/11/2026

Abra `interface.bat`. Reinicie o monitor após atualizar. Em `chrome://extensions`, recarregue a extensão e depois as abas das lives; a ponte local agora usa POST e token de sessão.

## Central de edição

O botão **Central de edição**, no topo, aceita arquivo local ou URL. Escolha o perfil e analise os momentos. Cada linha mostra o intervalo e o motivo; o painel abaixo permite inspecionar as evidências.

Escolha **direta**, **contexto** ou **historia** para gerar uma prévia leve ou o corte final. A IA propõe bordas e justificativas narrativas para cada versão; intervalos inválidos são rejeitados. Quando a IA não fornece uma alternativa válida, o programa usa bordas de falas e identifica a origem local. Versões iguais são sinalizadas nas evidências. São edições do material original, sem inventar falas ou dublagem.

**Buscar por significado** aceita uma descrição do acontecimento. Quando há IA configurada, ela avalia paráfrases e deve citar evidência literal de um candidato existente. IDs e citações inventados são descartados. Sem IA, há busca por conceitos locais e termos relacionados, identificada no resultado. Ativando **Análise ampla do áudio**, a busca também cobre os segmentos da transcrição completa, processados em lotes; pode consumir várias chamadas de IA. A busca guarda resultados em cache durante a sessão.

Os botões Aprovado, Rejeitado e Ajustado guardam sua explicação no perfil selecionado. Esse feedback entra como preferência editorial nos próximos prompts. Ele não treina um novo modelo nem demonstra aumento de views.

## Legendas editáveis

Na Galeria, use **Legenda**. Cada linha corresponde a uma palavra. Palavras de confiança baixa ficam destacadas. Posicione o cursor e clique **Ouvir no ponto do cursor** para conferir o áudio.

Você pode salvar o SRT ou gerar um novo vídeo com as correções. A receita preservada na pasta `_edicao` permite renderizar novamente sem repetir a chamada de IA e sem substituir o vídeo anterior. Cortes antigos, versões B e versões traduzidas podem não ter receita editável; nesses casos, gere um novo corte pelo fluxo principal.

Guardar a receita ocupa espaço adicional porque mantém o trecho intermediário e os elementos visuais. Os arquivos de edição não aparecem como cortes na Galeria ou no celular.

## Tendências

- **Assunto:** mantém relação textual com os termos pesquisados.
- **Canal:** usa @, endereço ou ID do canal; nomes ambíguos exigem @ ou link. A origem é conferida no detalhamento.
- **Descoberta:** amplia a pesquisa com assuntos gerais e vídeos populares.

Os filtros de duração e idioma se aplicam à busca manual. O filtro de idioma exclui resultados cujo idioma não foi identificado. O robô preserva o modo e os filtros de duração/idioma escolhidos. A opção **Agrupar acontecimentos com IA**, em Qualidade, usa título e descrição para reunir coberturas do mesmo evento; sem ela, a comparação usa conceitos locais. A IA não pode omitir nem duplicar vídeos nos grupos.

O crescimento recente só aparece após pelo menos duas medições separadas por dez minutos. A comparação com outros vídeos do canal exige histórico adicional. Dados parciais são identificados como provisórios. O método de agrupamento não comprova sozinho que duas coberturas mostram exatamente o mesmo acontecimento; confira os vídeos antes de decidir.

## Robô e extensão

O painel em `http://localhost:8765` mostra tarefas, etapas, tentativas e erros. Tarefas pendentes podem ser canceladas; falhadas podem ser retomadas. Cancelamento não interrompe um FFmpeg que já começou.

A fila, aprovações, marcações e escolhas das análises são persistidas. Cada corte automático possui nome estável e checkpoint independente da confirmação da fila. Se ocorrer uma queda depois de concluir o arquivo, a retomada reconhece a saída validada. Uma saída incompleta é substituída no mesmo destino; não recebe outro nome. O MP4 definitivo só é promovido após a revisão técnica. Gravações necessárias para tarefas pendentes, falhadas ou em revisão são protegidas contra limpeza. Após reiniciar, aprovações recuperadas também aparecem no painel.

A extensão mantém presença em abas ocultas, sincroniza seu relógio com o monitor e informa o atraso do player. Há ajuste adicional por canal no botão **Sincronização**. Quando o navegador permite ler o quadro, um hash perceptual confirma a posição na gravação. Imagens repetidas, anúncios e quadros ambíguos não provocam correção automática. Sem confirmação visual, a Galeria sinaliza sincronização estimada. Marcações antigas ou mais de três minutos atrás do ao vivo são recusadas. No YouTube, os botões de marcação são bloqueados durante anúncios identificados.

## Qualidade e recursos

No botão **Qualidade**, configure vocabulário e revisão editorial por perfil; CPU, disco e orçamento de IA são controles gerais.

- **Reserva de disco:** impede novos cortes e interrompe gravações quando falta espaço.
- **Chamadas de IA:** limite de tentativas por dia; não é uma estimativa monetária ou de tokens. Zero deixa sem limite.
- **Limite de fila:** controla novas descobertas automáticas; pedidos manuais continuam aceitos.
- **Retenção:** zero desativa. Quando habilitada, remove pastas antigas de gravação sem dependências; não remove cortes finais.
- **Gravação segmentada:** opcional, aplicada a novas gravações. Segmentos completos ficam disponíveis em uma playlist finita para análise/recorte. A captura HLS foi validada com mídia sintética; ainda requer teste de uma live real com Streamlink/yt-dlp.
- **Segunda transcrição:** revisita até três janelas incertas; consome mais CPU.
- **Nota editorial mínima:** quando maior que zero, habilita a autonomia calibrada. São exigidos os quatro critérios com evidências, contexto/conclusão mínimos, confiança da transcrição e pelo menos 20 avaliações humanas comparáveis no perfil. O limite inferior da taxa de aprovação humana deve sustentar a decisão; caso contrário, a tarefa fica em revisão. Avaliações repetidas do mesmo trecho não aumentam a amostra. Zero mantém esse controle desativado.
- **Hipótese A/B:** identifica a mesma hipótese em vários pares de cortes. Uma diferença isolada fica como exploratória; a conclusão só alimenta o guia após repetição e evidência suficiente.

A conferência básica (duração e trilhas) roda sempre. A revisão técnica completa é opcional (⚙ Qualidade) e verifica a decodificação inteira; também sinaliza imagem escura, imagem parada e picos de áudio. Sincronismo perceptivo, fidelidade da legenda e qualidade narrativa ainda dependem de revisão humana.

## Resultados e validação

O aprendizado comparativo usa observações da janela de 24–30 horas. Vídeos antigos sem essa medição não são tratados como equivalentes a recém-publicados. O guia agora mantém YouTube e TikTok separados por plataforma e perfil. O TikTok aceita horário explícito de postagem ou coluna de primeiras 24h; data sem horário não é transformada em uma medição precisa. Linhas ambíguas de relatório são ignoradas com aviso, em vez de serem atribuídas ao primeiro título parecido. As comparações exigem pelo menos cinco observações por grupo e estimativa de incerteza. Com o YouTube conectado, o robô mede as views sozinho a cada 3h, então a janela de 24–30h é capturada sem você precisar clicar. Os horários são normalizados por origem e duração para reduzir a confusão entre canal grande e horário melhor. A/B exige pares equivalentes e repetições da mesma hipótese.

Execute os testes locais:

```
python -X utf8 -B -m unittest test_correcoes test_evolucao test_finalizacao test_midia -v
node test_extensao.cjs
```

O teste de mídia gera conteúdo sintético e faz renderização real. Nenhum desses testes publica vídeos, acessa contas ou consulta serviços de IA. As versões diretas instaladas foram registradas em `requirements-constraints.txt`; isso não substitui validação das APIs externas.

## Associação audiovisual

O modo podcast agora extrai características acústicas, associa grupos de voz ao movimento visual e exige suporte dos dois sinais. Trechos silenciosos, sinais contraditórios ou associação insuficiente ficam sem identificação de falante. É processamento local com NumPy, sem modelo externo baixado automaticamente. O teste real deve verificar o desempenho com suas vozes e câmeras.

## Avaliação editorial

Gancho, contexto, desenvolvimento e conclusão têm notas independentes e citações verificadas contra a transcrição do trecho. A avaliação estrutural local fica identificada quando faltam evidências da IA. Essas notas não são previsão de views. O feedback da Central fornece os dados para calibrar a aprovação no seu perfil; nenhum histórico artificial foi inserido.

## Evolução v3.7 — Economia Extrema de Tokens e Motor Local de Retenção (`otimizador_corte.py`)

1. **Correções de legenda por Delta Esparso (`correcoes_delta`, ativo por padrão no modo econômico):**
   - Em vez de obrigar a IA a repetir todas as ~180–250 palavras do corte no JSON de saída, ela envia apenas o dicionário `"correcoes": {"indice": "PalavraCerta"}` com os nomes próprios, gírias ou acentos que realmente precisavam de correção (~75% menos tokens de saída).
   - Se a IA (ou modelo clássico) enviar a lista `"palavras"` completa com 1 ou 2 palavras a mais/menos, o **Reconciliador Tolerante (`SequenceMatcher`)** resgata as correções palavra a palavra sem perder os timestamps do Whisper e sem desperdiçar a chamada.
2. **Detector Local Multimodal de Gancho (`achar_gancho_multimodal`):**
   - Mesmo sem IA (`IA_PRINCIPAL="nenhuma"`, `"local"` ou quando a IA omite `"gancho"`), o sistema cruza impacto semântico (revelação, choque, conflito, pergunta) + pico acústico para cravar o segundo exato do clímax e ativar o **preview no 1º segundo** e o **zoom + boom**.
3. **Seletor Computacional de Melhor Quadro (`escolher_melhor_quadro`):**
   - Avalia nitidez Laplaciana (evita motion blur), exposição (evita quadros escuros/estourados), centralidade do rosto e contraste de expressão facial para escolher a melhor foto de topo quando a IA não define uma.
4. **Gerador Local de Pergunta Contextual (`gerar_pergunta_local`):**
   - Quando sem IA, extrai a frase de maior impacto da transcrição/título para montar a pergunta em maiúsculas com `??` e palavras de destaque em amarelo, em vez de repetir sempre uma frase fixa.
5. **Curva de Retenção Local e CLI de Auditoria (`analisar_ritmo_retencao`):**
   - Todo corte pronto ganha no `.json` o bloco `retencao_local` (`nota_retencao`, palavras por minuto `ppm`, `densidade_fala`, `buracos_ritmo` e diagnóstico).
   - Uso direto no terminal:
     - `python otimizador_corte.py --relatorio`
     - `python otimizador_corte.py --auditar cortes_prontos/meu_corte.mp4`
