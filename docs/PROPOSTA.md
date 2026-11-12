# Proposta — Gerador de Cortes 9:16

**Versão do documento:** 1.0 · **Versão do sistema:** 3.13 · **Data:** 11/11/2026

---

## 1. Sumário executivo

O Gerador de Cortes 9:16 automatiza a produção de vídeos curtos verticais a partir de lives e vídeos
longos. O sistema encontra os melhores momentos, edita no padrão dos cortes virais brasileiros, escreve
pergunta, título e legenda com inteligência artificial, confere o próprio trabalho e aprende com os
números do canal. Tudo roda no computador do criador, sem servidores, usando a assinatura de IA que ele
já possui.

A versão 3.13 entrega o ciclo completo — da fonte ao corte pronto para postar — com 167 testes
automáticos, controle de versão no GitHub e custo de IA medido por corte.

## 2. Contexto e problema

Canais de cortes vivem de volume e de velocidade: quem publica primeiro o melhor momento de uma live
capta a maior parte da audiência. O processo manual, porém, é lento e caro:

- assistir horas de conteúdo para achar poucos minutos que prendem;
- recortar sem cortar frases ao meio, enquadrar em 9:16 e seguir o rosto de quem fala;
- legendar palavra por palavra, escrever gancho, título e hashtags;
- repetir tudo para cada plataforma e ainda acompanhar o que deu resultado.

Além do tempo, há riscos que derrubam o trabalho: música com direitos autorais no fundo, conteúdo sem
edição tratado como "reutilizado" pelas plataformas e textos que prometem algo que o vídeo não entrega.

## 3. Objetivos

1. **Reduzir o tempo** de um corte de dezenas de minutos para poucos minutos de máquina e segundos de
   revisão humana.
2. **Elevar a qualidade** do corte (gancho, legenda, edição) a um padrão profissional e consistente.
3. **Manter o custo de IA baixo e previsível**, medido por corte.
4. **Aprender com os resultados** do próprio canal em vez de seguir regras fixas.
5. **Proteger o criador**: fidelidade ao conteúdo, aviso de risco de direitos e revisão antes de publicar.

## 4. Solução

Um sistema local em Python que combina processamento de áudio e vídeo (ffmpeg, Whisper, visão
computacional) com IA generativa usada de forma econômica e verificada.

**Diferenciais:**

| Diferencial | Como se materializa |
|---|---|
| IA conferida | Juiz local reprova perguntas genéricas, sem ligação com o trecho ou com números inventados; resposta ruim é refeita uma vez em modelo mais forte. |
| Custo sob controle | Uma chamada por corte (ou uma por vídeo, em lote), chamada enxuta de ~5 mil tokens e painel de uso. |
| Aprendizado real | Glossário de nomes por canal, gosto do dono e comparação de desempenho por template, pergunta, horário e modelo de IA. |
| Edição profissional | 11 templates, legenda animada, zoom nas palavras-chave, trilha com ducking, zona segura por plataforma, capa e A/B. |
| Operação autônoma | Robô que grava lives, detecta picos pelo chat e pelo áudio e corta sozinho, com fila recuperável. |
| Sem nuvem | Nada de servidor: o PC faz o trabalho e o celular acessa a galeria pela rede de casa. |

## 5. Escopo entregue (versão 3.13)

| Área | Entregue |
|---|---|
| Captura | YouTube, Twitch, lives gravadas (com segmentos), vídeos do PC, chat de VODs e pasta vigiada. |
| Seleção de momentos | Gráfico de replays, picos de chat, energia do áudio, análise ampla opcional e escolha por IA com nota. |
| Limpeza | Silêncios, vícios de linguagem, frase completa, abertura limpa e aparo das pontas pela IA. |
| Texto | Correção de legenda, resumo, pergunta e alternativas, título, chamada, hashtags, nota e motivo. |
| Edição | Templates, legendas `.ass`, faixa ou estilo clean, layouts de podcast e jogo, gancho antecipado, zoom, emojis, trilha, final em loop ou chamada, versão em espanhol. |
| Qualidade | Revisão técnica do vídeo, juiz de texto, aviso de música de fundo, revisão rápida na galeria. |
| Publicação | Agendamento no YouTube, apoio ao TikTok, galeria no celular, capa escolhível. |
| Aprendizado | Métricas do YouTube e do TikTok, testes A/B, horário inteligente, template que aprende. |
| Engenharia | 167 testes, repositório git, atualização segura, módulos separados por responsabilidade. |

## 6. Arquitetura (resumo)

O fluxo é linear e cada etapa tem um módulo dono: captura → seleção → limpeza → transcrição → IA →
juiz → edição → render → galeria → resultados, que realimentam a IA. As configurações ficam num único
lugar (`config.json`, com perfis por canal) e os dados do usuário nunca saem do PC. Detalhes em
[ARQUITETURA.md](ARQUITETURA.md).

## 7. Indicadores de sucesso

| Indicador | Como medir | Referência atual |
|---|---|---|
| Tempo por corte | Log do pipeline | Minutos de máquina; IA em 10–24 s (Equilibrada) |
| Custo de IA por corte | Painel 📊 Uso da IA | ~US$ 0,003 (Econômica) a ~0,038 (Equilibrada), valor de tabela |
| Cortes aprovados sem edição | Galeria (aprovado × refeito × descartado) | A medir com uso real |
| Views e retenção por corte | Aba Resultados (YouTube e TikTok) | A medir com uso real |
| Precisão do aviso de música | Conferência humana dos avisos | Sem falso alarme nos testes; detecta a partir de ~25% do volume da fala |

O sistema mede e compara; ele não promete viralização. Ganhos de audiência só podem ser afirmados com
os números reais do canal ao longo do tempo.

## 8. Custos operacionais

- **Infraestrutura:** nenhuma além do PC. Não há servidor nem mensalidade de hospedagem.
- **IA:** usa a assinatura que o criador já tem; o consumo por corte está na seção 7 e pode ser
  reduzido escolhendo o nível Econômico.
- **Armazenamento:** uma live de 4 h em 720p ocupa de 6 a 12 GB durante a gravação; o programa pode
  apagar a gravação depois de cortar.

## 9. Riscos e mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| Direitos autorais (música, conteúdo de terceiros) | Corte mutado, bloqueado ou sem monetização | Aviso de música antes de postar, crédito da fonte, preferência por canais que autorizam cortes, revisão humana |
| Conteúdo "reutilizado" sem edição | Perda de monetização | Edição transformadora (faixa, legenda, zoom, efeitos, marca) |
| Texto infiel ao vídeo | Desconfiança do público, denúncias | Transcrição tratada como material, juiz local, revisão antes de publicar |
| Limite da IA ou indisponibilidade | Cortes sem texto | Reserva automática entre provedores, pausa inteligente e pergunta gerada no PC como último recurso |
| Mudanças nas plataformas (download, APIs) | Falhas de captura ou postagem | Download com novas tentativas, atualização de baixadores e código modular |
| Perda de código local | Retrabalho | Repositório git no GitHub e atualizador que não sobrescreve alterações |

## 10. Roteiro proposto

**Fase 1 — Operação (curto prazo)**
- Teste de ponta a ponta do robô com a IA nova em lives reais (momentos → lote → postagem).
- Acesso à galeria pelo celular fora de casa, por túnel seguro gratuito, e aviso no celular quando um
  corte fica pronto.

**Fase 2 — Distribuição (médio prazo)**
- Postagem no Instagram Reels.
- Agenda única das três plataformas, com o melhor horário de cada uma.

**Fase 3 — Qualidade avançada (longo prazo)**
- Remoção opcional da música de fundo mantendo a voz (separação de fontes por IA), avaliando custo de
  processamento no PC.
- Testes automáticos rodando no GitHub a cada alteração.

## 11. Próximos passos

1. Validar a Fase 1 em uso real por duas semanas, acompanhando os indicadores da seção 7.
2. Revisar a calibração do aviso de música com casos reais confirmados.
3. Priorizar a Fase 2 conforme os resultados por plataforma.
