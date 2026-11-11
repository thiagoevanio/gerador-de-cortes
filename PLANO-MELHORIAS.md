# Evolução do Gerador de Cortes

Início: 02/11/2026. Pendências de implementação listadas na última revisão concluídas em 02/11/2026. Próxima etapa combinada com o usuário: testar o fluxo real. Implementação não equivale a comprovação de aumento de precisão ou de views.

## Finalização das sete pendências de código

1. Avaliação editorial: quatro critérios independentes, evidências verificadas, bordas narrativas por versão e fallback identificado.
2. Falante: extração de características do áudio, associação com movimento visual, suporte mínimo e abstenção em caso de dúvida.
3. Sincronização: relógio cliente/servidor, compensação de transporte, ajuste por canal, confirmação perceptual de quadro e rejeição de marcações fora do alcance.
4. Ferramentas semânticas: busca por significado com evidência, cobertura em lotes de transcrições longas, conceitos locais e agrupamento opcional com IA.
5. Autonomia: calibração por aprovação humana com mínimo de amostra, limite estatístico conservador, critérios por etapa e separação por perfil.
6. Aprendizado: YouTube/TikTok separados, parsing de horário, proteção contra importação ambígua, comparação com incerteza, horários normalizados e A/B replicado.
7. Recuperação: escolhas persistidas antes de enfileirar filhos, nome estável por tarefa, promoção atômica do MP4 e checkpoint de saída independente da fila.

**Resultado da finalização: 51 testes Python aprovados**, incluindo renderização e recuperação real sem nova saída, além do teste funcional do service worker. As telas finais foram construídas sem erros. Chamadas de IA nos testes foram simuladas; não houve publicação nem treinamento com dados artificiais no perfil do usuário.

O código dos mecanismos está concluído. A calibração precisa das avaliações reais do usuário e a confirmação de precisão depende do fluxo real, conforme combinado.

## Segundo lote — implementação e evidências

O uso está descrito em `GUIA-NOVAS-FUNCOES.md`.

| Área | Implementação atual | Validação |
|---|---|---|
| Recuperação | Fila, agendamentos, aprovações, retomada, cancelamento pendente, proteção das fontes e IDs estáveis | Testes locais com reinício simulado e concorrência |
| Comunicação | POST, token por sessão, origem restrita, confirmação de comandos e reenvio do chat | Servidor HTTP real local e service worker em ambiente simulado |
| Monitor | Sondagens de rede e análise pesada de áudio fora do ciclo de atendimento; histórico e etapas no painel | Integração local; live real pendente |
| Precisão | Replays revisados com contexto, candidatos de cobertura e opção de análise textual ampla; limites finitos/sem sobreposição | Regressões locais; qualidade narrativa em fonte real pendente |
| Legendas | Confiança por palavra, vocabulário por perfil, segunda transcrição seletiva, editor e receita para nova renderização sem IA | Renderização real com legenda de teste e vídeo revisado |
| Enquadramento | Continuidade de rosto, detecção heurística de mudança de cena e sinalização de falante condicionada à fala transcrita | Código integrado; benchmark com rostos e vozes reais pendente |
| Qualidade | Duração, trilhas, decodificação completa, avisos de preto/congelamento/pico e prévia leve | FFmpeg real com mídia sintética |
| Tendências | Modos e filtros persistidos, medições sucessivas, crescimento e comparação por canal, agrupamento textual | Testes determinísticos; consulta pública por assunto retornou dois resultados |
| Aprendizado | Janela 24–30h, separação por perfil, comparações por estrato e feedback editorial | Testes de janela e isolamento dos perfis |
| Ferramentas | Central de edição, evidências, três intervalos de prévia, busca textual e aprovação por nota editorial | Telas construídas em teste nativo; comportamento automatizado parcial |
| Recursos | Threads, disco, orçamento diário de tentativas de IA, limite para descobertas, retenção opt-in e captura segmentada opcional | Testes de orçamento; HLS sintético e recorte real |
| Manutenção | JSON atômico, exclusividade de render, proteção de dados na atualização, diagnóstico e constraints das versões diretas | Testes locais e importações |

Rodada integrada: **25 testes Python aprovados**, incluindo FFmpeg, HLS, renderização com legenda e nova renderização revisada. `node test_extensao.cjs` aprovado. Os scripts JavaScript alterados também passaram na verificação de sintaxe.

O teste nativo inicial de interface, Central e Qualidade passou fora da restrição que impedia o Tcl de carregar; não foi necessário reparar a instalação. O teste final das telas também passou, sem salvar configurações. A construção nativa não substitui revisão visual e uso interativo de todos os fluxos.

## Limites que permanecem explícitos

- Não houve publicação, acesso a contas nem chamadas reais aos provedores de IA nos testes.
- A consulta pública validou pesquisa por assunto, não todos os canais/formatos/períodos do YouTube.
- A associação audiovisual usa características acústicas e movimento visual, com abstenção; não foi instalado um modelo externo pré-treinado.
- A busca semântica usa a IA configurada quando disponível; o fallback é por conceitos locais. Com análise ampla desativada, cobre apenas os candidatos transcritos.
- As três versões têm objetivos e bordas narrativas, mas sua qualidade editorial deve ser conferida no material real.
- Há compensação temporal e confirmação por quadro quando possível. Sem confirmação visual, a posição continua sendo uma estimativa, sinalizada na Galeria.
- Cancelamento atua em tarefas pendentes; não encerra uma renderização em andamento.
- A revisão técnica não comprova sincronismo perceptivo, precisão da fala ou chance de viralização.
- Falta comparar cortes com referências reais de podcast, gameplay, conversa calma e live, medindo aprovação, precisão e consumo.

## Entregue no primeiro lote

- Busca específica sem acrescentar assuntos gerais. Modos Assunto, Canal e Descoberta na interface.
- Canal por @, link ou ID; resolução de nome exato sem escolher homônimos silenciosamente.
- Verificação de origem e período no detalhamento de vídeos do canal.
- Orçamento de detalhamento intercalado entre termos pesquisados.
- Horários da IA finitos, não negativos, dentro dos candidatos e sem sobreposição.
- Ranking de candidatos por áudio preservado no fallback; janelas curtas respeitadas.
- Mensagens anônimas não contam como pessoas distintas; tentativa de identificar autor do Kick.
- Presença da extensão com aba oculta, timeout HTTP e reenvio limitado do chat após falha.
- Fila SQLite com prioridades, recuperação de trabalho interrompido e três tentativas com espera crescente.
- Persistência de cancelamento e atualização da nota de tarefas pendentes.
- Identificadores dos cortes filhos para evitar reinserir o mesmo intervalo em uma tentativa repetida.
- Proteção da gravação enquanto houver tarefas dependentes pendentes, executando ou com falha.
- Pastas temporárias exclusivas dentro de `_trabalho`.
- Monitor não inicia outro trabalhador quando a porta do painel está ocupada.

## Validação realizada

- Nove testes locais em `test_correcoes.py`, sem chamadas externas: passaram.
- Sintaxe de todos os arquivos Python e dos scripts alterados da extensão: aprovada.
- Importação de cortes e monitor: aprovada, sem iniciar o monitor.
- FFmpeg real: fonte sintética de seis segundos, recorte de 1 a 4 segundos com áudio; duração 3,024 segundos.
- O atalho WinGet do FFmpeg apresentou acesso negado neste ambiente. O teste passou usando a instalação Essentials existente, com PATH alterado somente no processo de teste.
- Busca real no YouTube, leitura DOM do Kick, live, interface visual, postagem e renderização completa com IA ainda não validadas.

## Plano original de referência (implementações acima; aceitação externa abaixo)

1. Completar estabilidade: persistir agendamentos/aprovações com referência à gravação, recuperar tarefas falhadas pela interface, corrigir o registro antecipado de tendências como feitas, dar confirmação real aos comandos e permitir retomada manual de falhas permanentes.
2. Segurança e comunicação: pareamento por token, POST para mutações, origem restrita, status por pedido, progresso/cancelamento e reconexão. Evitar conflito entre processos nos arquivos finais e nas configurações globais.
3. Precisão: alinhar relógio/player/gravação; buscar margem de contexto; revisar semanticamente os replays; incluir sinais de transcrição além de volume; manter mapa de tempo das edições.
4. Legendas e enquadramento: vocabulário por perfil, confiança por palavra, segunda transcrição seletiva, editor sincronizado, acompanhamento de pessoas e identificação audiovisual de falante.
5. Qualidade: prévia leve e revisão de tela preta, congelamento, áudio, sincronismo e áreas seguras.
6. Tendências: snapshots sucessivos, crescimento recente, histórico por canal, dados comparáveis no ranking, filtros adicionais e explicação de pontuação. Persistir o modo escolhido também na configuração do robô.
7. Aprendizado: janelas equivalentes, separar plataformas/perfis/temas/duração, amostra mínima para horários e A/B e feedback editorial.
8. Inovação: editor com evidências, três versões de prévia, busca por acontecimento, memória editorial, autonomia por confiança e agrupamento de coberturas.
9. Recursos e manutenção: limites de CPU/disco/IA, gravações segmentadas, retenção configurável, dependências controladas e diagnóstico de instalação.
10. Validação final: referências de podcast/gameplay/conversa calma/live, falhas e reinícios, comparação de aprovação editorial, tempo e consumo; atualizar documentação de uso.

## Critério de conclusão

Não marcar uma etapa como validada com base apenas em sintaxe. Exigir testes de comportamento e revisão de vídeos quando a mudança afetar mídia. Nenhuma postagem faz parte dos testes automáticos.

## Recuperação

Originais dos arquivos modificados existentes estão em `_backup_melhorias_20261102`.
A fila operacional é criada ao iniciar o monitor em `fila_tarefas.sqlite3`; não apagar esse arquivo para reiniciar o programa. Ele contém trabalho e histórico.
