# Histórico de versões

As mudanças mais novas ficam em cima.

## 3.14 — Janelinha da live, faixas novas, IA local por tamanho e Tendências por canal

- **📺 Janelinha da live:** quando um canal vigiado entra ao vivo, a live abre numa janela pequena no
  canto da tela (Edge/Chrome em modo aplicativo) enquanto o robô grava e corta. Mostra o tempo de
  gravação, os cortes feitos, o calor do chat, os últimos momentos detectados e o botão ✂ CORTAR AGORA.
  Funciona com Twitch, Kick e YouTube; várias lives viram abas. Botão novo na aba Automático e opção
  para desligar a abertura automática.
- **Faixas:** dois formatos novos, **Balão de fala** e **Neon**, e o botão **👁 Ver formatos** na aba
  Visual, que mostra uma amostra de cada faixa com as cores do perfil (clique para escolher).
- **IA local por tamanho:** escolha o modelo do Ollama de 1,9 GB a 9 GB (Leve, Média, Forte, Máxima).
  O programa mede a RAM do PC, recomenda o modelo que cabe e avisa antes de escolher um pesado demais.
  Um modelo que já está no PC não é baixado de novo.
- **Tendências só nos canais:** o modo "Só nos canais" aceita `@nome`, link ou só o nome do canal, não
  busca mais os assuntos do Brasil nem vídeos soltos, e um canal que falha não derruba os outros.
  Digitar um `@` ou link troca para esse modo sozinho.
- **Correção — "baixando modelo" em todo corte:** o Whisper consultava a internet toda vez que era
  carregado (a barra "Fetching files"). Agora abre direto do PC e só baixa quando o modelo não existe.

## 3.13 — Repositório, atualização segura, aviso de música, capa escolhível e código organizado

- **Projeto no git e no GitHub**, com histórico de cada mudança. O atualizador, quando a pasta é um
  repositório git, atualiza com `git pull` e se recusa a rodar enquanto houver alteração local não
  salva — antes ele copiava a versão nova por cima e apagava melhorias feitas no PC.
- **Aviso de música de fundo** (sem IA): o áudio do trecho é analisado nos intervalos entre as falas e
  por notas sustentadas. Se parecer ter música (rádio, playlist, trilha de jogo), o corte ganha um
  aviso na galeria do PC e do celular e na confirmação antes de agendar no YouTube — música com
  direitos autorais é o que mais muta ou bloqueia corte de live. A ficha guarda `musica_de_fundo`.
  É uma estimativa: detecta música a partir de ~25% do volume da fala; muito baixinha pode passar.
  Desligar: `"checar_musica": false`.
- **Capa escolhível**: botão 🖼 no cartão da galeria mostra 3 opções (o começo, onde passa a prévia do
  gancho, e dois momentos do meio) mais a atual; a escolhida vira o `.capa.jpg` e a miniatura da
  galeria (PC e celular).
- **Revisão rápida**: o cartão mostra o resumo do trecho e o motivo da nota que a IA escreveu, e avisa
  quando a IA não respondeu e a pergunta foi feita no PC.
- **Código organizado**: a IA dos cortes foi para `ia_cortes.py` e o render para `render.py`; o
  `cortes.py` caiu de 3.179 para ~2.050 linhas. Documentação nova: README, proposta e arquitetura.
- Correção: descartar pelo celular agora leva junto a capa, a transcrição e o relatório de qualidade.

## Novidades da 3.12 — IA mais completa, mais esperta e muito mais leve

**Qualidade da IA** (Contas & IA): escolha entre três níveis.
- **Econômica**: Haiku em tudo. Já sai melhor que antes (prompt novo) e gasta cerca de metade.
- **Equilibrada** (padrão): Sonnet nas decisões que mais pesam (pergunta, título, nota, onde cortar e
  quais momentos virar corte) e Haiku no resto. Mais rápida (~10s por corte, contra ~25s antes).
- **Máxima**: Opus nessas decisões e Sonnet no resto.
Os modelos de cada degrau ficam em `claude_modelo_leve`, `claude_modelo_medio` e `claude_modelo_forte`.

**Chamada enxuta**: cada pedido ao Claude carregava ~38 mil tokens do "manual" do Claude Code que não
servem pra cortes. Agora vai só o necessário (~5 mil por corte), sem salvar sessão no seu histórico
do Claude Code e sem abrir MCP/skills.

**Pedido 2.0 pra IA**: a transcrição vai com marcas de tempo ([12s]) e de pausa (‖), então a IA
respeita "3 primeiros segundos" e acha o começo e o fim das frases; a IA primeiro escreve um resumo do
que acontece e só depois a pergunta; exemplos do nível esperado; transcrição e chat vão marcados como
material (uma fala do tipo "ignore as instruções" não manda na IA).
Novos campos na ficha de cada corte: `resumo`, `motivo_nota` (por que a nota) e `chamada` (pergunta
pro público responder nos comentários — já entra na legenda do post e no .txt).

**Juiz das perguntas (sem gastar IA)**: confere se a pergunta é genérica ("VOCÊ VIU ISSO??"), se cita
algo do trecho e se tem número que não foi dito. Se a principal vier fraca e uma alternativa for
melhor, troca sozinho. No modo Econômico, se a resposta vier ruim de vez, refaz 1 vez no Sonnet.

**Aprende com o uso**:
- Glossário de nomes por canal: nomes que a IA corrigiu (em 2 cortes) ou que você corrigiu no editor
  de legenda passam a ir pro Whisper e pra IA nos próximos cortes do mesmo canal.
- Gosto do dono: quando você troca a pergunta (✏), a troca vira exemplo do seu gosto pra IA.
- A aba de resultados passa a comparar views por modelo de IA.

**Mais confiável**:
- Resposta com defeito (bloco de código, vírgula sobrando, aspas soltas, resposta cortada no fim) é
  consertada em vez de jogada fora; resposta sem JSON é pedida de novo 1 vez.
- IA que acabou o limite ou ficou sem login entra em pausa e a reserva assume direto, sem perder
  minutos tentando de novo a cada corte.
- Sem resposta de nenhuma IA, a pergunta e o gancho são feitos no PC (em vez de "VOCÊ VIU ISSO??").
- No lote, um corte que não veio inteiro na resposta pede a IA sozinho (os outros aproveitam).
- O Claude agora recebe o nome da imagem dos quadros no modo lote (antes ele não conseguia vê-la).
- A escolha de momentos dá nota a cada um; momento claramente fraco (nota abaixo de 4) nem é baixado.
- A IA pode aparar até ~20-25s de uma ponta do trecho quando o começo é resto de conversa.

**Uso da IA** (Contas & IA → 📊 Uso da IA): chamadas, falhas, tempo e tokens dos últimos 7 dias, por
IA e por tarefa (arquivo `analises/uso_ia.jsonl`).

## Novidades da 3.11 — IA apara o trecho, template que aprende e pergunta nova sem gastar IA

- **Começo e fim escolhidos pela IA**: na mesma chamada de sempre, a IA diz onde o corte deve abrir e
  fechar, e o sistema apara as pontas fracas (resto do assunto anterior, frase pela metade, conversa
  depois do desfecho). Travas: no máximo ~12s de cada ponta, sobra pelo menos 55% do trecho e o
  gancho nunca fica de fora. O log mostra o que foi aparado. Desligar: `"aparar_ia": false`.
- **Template que aprende**: no modo "Automático (IA escolhe)", o sistema compara as views dos seus
  cortes (janela de 24–30h, por perfil e plataforma) e passa a preferir o template que mais rende.
  Só troca com pelo menos 4 cortes medidos por template e vantagem de 15%; em ~25% dos cortes mantém a
  escolha pelo tom, pra continuar testando os outros. Desligar: `"template_aprende": false`.
- **✏ Refazer sem gastar IA**: o botão agora mostra as perguntas alternativas que a IA já tinha criado
  (1 clique) ou um campo pra escrever outra, e troca só a pergunta reaproveitando a edição pronta: sem
  baixar, sem transcrever e sem IA (menos de 1 minuto). Vale pros cortes feitos a partir desta versão;
  os antigos continuam sendo refeitos do zero.
- **Correções da revisão geral**: emoji e cartaz do fim não caem mais em cima da faixa/legenda quando a
  legenda sobe; a zona segura vale também pro revisor de rostos; descartar/refazer leva junto a capa, a
  transcrição e o relatório de qualidade; o A/B de template tem hipótese própria nos resultados; a
  versão em espanhol ganhou os efeitos e a música.

## Novidades da 3.10 — Acabamento profissional, teste A/B de template e chave protegida

- **Zoom nas palavras-chave**: além do zoom por frase, um "soco" curto de zoom cai exatamente nas
  palavras que a IA marcou como importantes (intensidade por template; Clássico e Minimalista não usam).
- **Final do corte** (aba Visual > "Final do corte"): **Chamada** mostra um cartaz nos últimos segundos
  (`cta_texto`, padrão "SEGUE PRA MAIS CORTES"); **Loop** termina colado na última fala, sem fade, pra
  emendar com o começo quando o vídeo repete; **Nada** deixa como antes.
- **Zona segura da legenda** (aba Visual): a legenda e os emojis ficam fora da área que os botões e a
  descrição do TikTok/Reels/Shorts cobrem. "Todas as plataformas" usa o pior caso (legenda a pelo menos
  480 px do fundo); "Desligada" volta a obedecer só a "Margem da legenda". Os números são aproximados
  (os apps mudam o layout) e ficam em `acabamento.py`.
- **Abertura limpa**: a IA indica a palavra que deve abrir o corte e o sistema pula a enrolação dos
  primeiros segundos ("Então,", "Bom,", "Cara,"). Sem IA, só tira muletas isoladas por vírgula.
  Desligar: `"limpar_abertura": false`.
- **Teste A/B de template**: com o Teste A/B ligado, a versão B pode trocar o template em vez da
  pergunta. `ab_variar`: `alternar` (padrão: um corte testa pergunta, outro testa template),
  `pergunta`, `template` ou `ambos`. A ficha guarda o que mudou e a aba de resultados já compara
  por template.
- **Capa**: cada corte ganha um `.capa.jpg` (o quadro mais nítido com a pergunta) pra usar de capa no
  TikTok/Reels. Desligar: `"capa": false`.
- **Chave do Gemini protegida**: no `config.json` ela agora fica criptografada pelo Windows (só a sua
  conta deste PC abre). Em outro PC é só colar a chave de novo.
- **Código dividido**: a faixa/foto do topo foi para `faixas.py` e as legendas para `legendas.py`
  (o `cortes.py` ficou ~700 linhas menor). Nada muda no uso.

## Novidades da 3.9 — Música de fundo, download resistente e cortes mais fortes

- **Música de fundo com ducking**: coloque músicas livres de direitos em `musicas/` (subpastas
  `animada`, `tensa`, `emocionante`, `calma`; arquivos soltos servem para qualquer clima). O sistema
  escolhe pelo tom que a IA já manda (sem gastar IA), evita repetir a mesma faixa, faz fade no começo e
  no fim e **abaixa a música sozinho quando alguém fala**. Liga/desliga na aba Visual ("Música de fundo");
  volume em `musica_volume` no config.json (padrão 0.16). Sem músicas na pasta, nada muda.
- **Download que não desiste na primeira falha**: se o yt-dlp/ffmpeg cair no meio, tenta de novo (até 3
  vezes); a última tentativa usa um formato de arquivo único, que falha menos. Vídeo privado/removido
  não fica insistindo.
- **Prévia do gancho só quando vale**: o "momento mais forte no começo" só entra se o gancho estiver a 10s
  ou mais do início (`gancho_distancia_min`) e não repetir o que já se ouve nos primeiros segundos.
- **Nota mínima no automático**: cortes que o robô faz sozinho descartam nota abaixo de 6
  (`nota_minima_automatico`), mesmo com a "Nota mín." da aba Visual em 0. Cortes pedidos por você
  continuam seguindo só a "Nota mín.".

- **Legenda maior e piso por template**: o tamanho padrão do seu perfil subiu de 55 para 78, e os
  templates "pequenos" (Notícia, Podcast Premium, Minimalista, Documentário) não encolhem mais abaixo de
  um piso de leitura (62 a 66). O controle "Tamanho da legenda" da aba Visual continua mandando.

## Novidades da 3.8 — Templates de edição + IA mais esperta
- **11 templates de edição** (aba 🎨 Visual → **Template de edição**, por perfil): *Clássico* (o de sempre), *Viral Dinâmico*, *Hormozi*, *Karaokê*, *Marca-texto*, *Neon*, *Gamer*, *Podcast Premium*, *Minimalista*, *Notícia* e *Documentário*. Cada um junta fonte/cores/animação da legenda + efeitos:
  - **zoom de ritmo** a cada frase (efeito "jump cut"), **barra de progresso** no topo, **flash** no gancho, **correção de cor** (vivo/cinema/frio/quente), **vinheta** e **"pop" sonoro** quando o emoji aparece.
  - **Automático (IA escolhe):** a IA diz o clima do trecho (humor, polêmica, emoção, suspense, gameplay...) na MESMA chamada e o programa escolhe o template. Zero IA a mais.
  - A prévia da aba Visual agora mostra a legenda de verdade do template (mesmo gerador do vídeo final).
- **Palavras-chave coloridas:** a IA marca até 6 palavras (nomes, números, palavras fortes) que ganham outra cor na legenda.
- **Pergunta/gancho melhor:** a IA usa fórmulas de gancho (curiosidade, conflito, citação, fato), é proibida de usar frase genérica ("VOCÊ VIU ISSO??") e devolve **2 perguntas alternativas** guardadas na ficha. Com A/B ligado, a versão B usa uma delas. A nota agora segue uma régua clara.
- **Pergunta sempre limpa:** maiúsculas, até 60 letras, sem terminar em "…NO??"/"…DE??".
- **Imagem mais nítida:** redimensionamento lanczos + nitidez leve quando a fonte é menor que 1080p.
- **Aprendizado:** "O que funciona no seu canal" agora compara também **template** e **tom** — o programa descobre qual estilo dá mais views pra você.
- **Modelo do Claude configurável:** em `config.json`, `"claude_modelo": "sonnet"` dá perguntas e ganchos melhores (gasta mais do limite). Vazio = Haiku no modo econômico, como antes.
- A legenda agora quebra o bloco no fim da frase (não junta o fim de uma ideia com o começo da outra).
- Corrigir legenda pela Central reaproveita o template e os efeitos do corte original.

## Novidades da 3.6 (junção das duas 3.5 — a sua e a minha)
Tudo das duas versões junto, mais 3 ajustes:
- **Acelerador de vídeo de verdade:** o teste que descobre a GPU agora usa um vídeo de tamanho normal (o Quick Sync da Intel recusava a imagem minúscula do teste antigo e o programa caía no processador sem avisar). O log mostra qual ficou (ex.: "🎞 acelerando o vídeo com vídeo integrado Intel (Quick Sync)"). Se a GPU falhar num arquivo, o programa refaz aquele no processador sozinho — o corte nunca se perde.
- **Emendas sem estalo no vídeo final:** cada pedaço que sobra depois de tirar silêncios e "é/tipo/né" ganha um micro-fade de 12 ms na entrada e na saída (antes só o áudio da transcrição e as pontas tinham).
- **Redutor de chiado opcional:** continua ligado, mas dá pra desligar em ⚙ Qualidade (em live com música ou jogo alto ele pode abafar a voz).
- **Estilo Clean (sem faixa):** aba 🎨 Visual → **Estilo do corte** → *Clean (sem faixa)*. O vídeo ocupa a tela toda (a câmera segue o rosto), a pergunta aparece como **texto** nos 3 primeiros segundos (dá pra desligar), e a legenda fica mais alta, longe dos botões do TikTok/Shorts. Podcast e jogo continuam em tela dividida, só sem a faixa. Como não tem foto no topo, a IA nem recebe imagem (gasta menos). O estilo com faixa continua igual e é escolha por perfil.
- **Corte de live no momento certo:** quando o termômetro dispara, o programa pega um trecho LARGO (a história antes + a reação depois) e a IA escolhe o pedaço exato — começando onde o assunto começa e terminando depois da reação — **na mesma chamada que já fazia a pergunta e a legenda** (zero IA a mais). Sem IA, o programa corta pelas pausas e frases em volta do lance. E a IA dá nota: abaixo da **Nota mín.** (Automático, padrão 6) o corte da live é descartado — chega de corte fraco.

### Da sua 3.5 (Pacote de Qualidade de Estúdio)
- **Uma passada só + detecção de GPU:** os cortes de silêncio, vícios de linguagem ("é…/tipo/né") e ajuste de frase completa agora são somados matematicamente e executados em **uma única passada de vídeo** (antes recodificava até 3 vezes seguidas), mantendo o áudio sincronizado na memória com corte em *zero-crossing*. Também detecta sozinho se o PC tem encoder de vídeo integrado/GPU (`NVENC`, `QSV`, `AMF`) e usa `CRF 19` para imagem mais nítida.
- **Áudio de estúdio:** filtro redutor de chiado de microfone (`afftdn`) antes do compressor, micro-fades nas emendas de silêncio/vícios, trava estéreo 48 kHz compatível com qualquer FFmpeg e novos efeitos sonoros multicamada sintetizados em estéreo (*sub-drop + punch* no `boom`, *whoosh* cinematográfico na transição do gancho inicial e *pop*).
- **Câmera virtual suave + foco dinâmico no Podcast:** o acompanhamento de rosto agora usa suavização bidirecional e curva *ease-in-out* (*smoothstep*), sem trancos robóticos. No modo Podcast, quem domina a fala por mais de 3,5s ganha leve zoom de destaque e indicador lateral ativo.
- **Legendas mais vivas e correção nos cortes longos:** a palavra falada agora cresce levemente (`114%`) além de mudar de cor. Nos cortes longos 16:9, a chamada única da IA também devolve um dicionário enxuto de correções de nomes próprios/gírias (ou reaproveita de graça as correções do corte curto).
- **Compilação 16:9 sem queda de ritmo:** cartões de abertura mais rápidos (1,8s com zoom suave, barra de progresso e som de transição *whoosh + impacto* em vez de 3s de silêncio mudo), rodapé animado com barra de tempo e áudio nivelado entre clipes.

## Novidades da 3.4
Tudo é **a mais** — o corte curto 9:16 continua igual e sendo o padrão.
- **Cortes longos 16:9 (3 a 8 min) pro YouTube normal.** Em **Formato** (aba Corte) ou **Formato do robô** (aba Automático): *Curto 9:16*, *Longo 16:9* ou *Os dois ⭐*. O longo abre o contexto em volta do mesmo momento (60% antes, 40% depois), em tela cheia, com legenda embaixo, a pergunta no topo nos primeiros segundos e o seu @. Em "Os dois", o longo usa o título/pergunta do curto: **zero IA a mais**. Postado como vídeo normal (sem #shorts). Galeria → filtro **Longos 16:9**.
  - Por quê: a partir de fev/2027 o YouTube pede 8 mil horas em vídeo longo pra monetizar canal novo, e os Shorts só pagam com 10 milhões de views em 90 dias.
- **Compilação mais forte:** vai somando os melhores cortes até chegar no tamanho alvo (8 min, em ⚙ Qualidade), usa o **trecho original deitado em tela cheia** (ou o corte longo, se existir) com rodapé "#3 — título", e tem **compilação de um canal** só (Resultados → 🎬 Compilação de um canal). Se não der pra pegar o original, usa o estilo antigo.
- **Legenda melhor sem gastar IA:** a busca de momentos continua no Whisper *base* (rápido) e só o corte escolhido (~1 min) usa o *small* — quase metade dos erros. Dá pra trocar em Transcrição (aba Corte) ou em ⚙ Qualidade (*base / small / turbo*).
- **Chat de lives antigas:** em VOD da Twitch e live antiga do YouTube, o programa baixa o chat e usa os momentos em que ele explodiu (com o lance começando uns segundos ANTES da reação). Também lê um arquivo de chat que você tenha (botão **💬 Chat** — TwitchDownloader, chat-downloader, yt-dlp ou texto) e acha sozinho um chat com o mesmo nome do vídeo na pasta. Sem IA.
- **Uma chamada de IA por vídeo:** quando saem vários cortes do mesmo vídeo, a pergunta, o título, a correção da legenda e a foto de TODOS vêm numa chamada só (antes era uma por corte). Se essa resposta vier quebrada, cada corte pede separado — nunca fica sem corte.
- **Momento exato:** a IA agora escolhe pelas frases numeradas (F12 até F20) e o programa encaixa o corte nas pausas: começa 0,25s antes da primeira frase e termina logo depois da última, sem pegar pedaço da vizinha.
- **Vídeo do PC:** botão **📁 Vídeo do PC** na aba Corte (funciona com "achar momentos" e com chat), e a **📂 Pasta vigiada** no Automático: jogou um vídeo lá, o robô acha os momentos e corta sozinho.

## Novidades da 3.3 (junção das duas versões)
- **Base nova mais forte:** fila que sobrevive a quedas, extensão com senha de sessão, um corte por vez entre o programa e o robô, limite de núcleos do processador, reserva de disco, editor de legenda (corrige sem gastar IA) e a Central de edição.
- **Economia de volta (tudo que gasta mais vem DESLIGADO — ligue em ⚙ Qualidade se quiser):**
  - Vídeo do YouTube com gráfico "mais repetidos" volta a sair **sem IA e sem baixar o áudio**.
  - No máximo 8 trechos candidatos (16 só na Central de edição ou com "Análise ampla").
  - A avaliação editorial (4 notas com citações) e as 3 versões só entram na **Central de edição** ou se você ligar.
  - **A resposta da IA fica guardada por tarefa:** se o corte falhar depois e o robô tentar de novo, ou se você aprovar um corte "em revisão", **não paga a IA de novo**.
  - Transcrição rápida de novo (beam 1). A "precisa" (beam 3, ~2x mais lenta) é opcional.
  - A revisão técnica completa (assistir o vídeo inteiro de novo) é opcional; a conferência básica continua sempre.
- **Revisor de frase religado:** o corte volta a não começar nem terminar no meio da frase.
- **Quem fala no podcast:** tenta pela voz + boca; se ficar em dúvida, usa o movimento da boca (o destaque e a cor da legenda voltaram).
- **Aprendizado e horário inteligente funcionando de verdade:** o robô atualiza as views do YouTube sozinho a cada 3h (precisa do YouTube conectado), e o mínimo caiu pra 5 vídeos medidos por grupo.
- **Nome dos arquivos legível** de novo (título do corte + um código curto).

**Novas funções locais (02/11/2026):** Central de edição com evidências e prévias, revisão de legendas com nova renderização, pesquisa por assunto/canal, fila recuperável e controles de qualidade/recursos. Veja **[docs/GUIA-FUNCOES-AVANCADAS.md](docs/GUIA-FUNCOES-AVANCADAS.md)** para usar e conhecer os limites de validação. Após atualizar, reinicie o monitor e recarregue a extensão do Chrome e as abas das lives.
