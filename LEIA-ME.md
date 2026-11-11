# Gerador de Cortes 9:16

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

**Novas funções locais (02/11/2026):** Central de edição com evidências e prévias, revisão de legendas com nova renderização, pesquisa por assunto/canal, fila recuperável e controles de qualidade/recursos. Veja **[GUIA-NOVAS-FUNCOES.md](GUIA-NOVAS-FUNCOES.md)** para usar e conhecer os limites de validação. Após atualizar, reinicie o monitor e recarregue a extensão do Chrome e as abas das lives.

Faz cortes verticais no estilo dos cortes brasileiros: foto no topo, faixa com pergunta chamativa e vídeo embaixo com legenda palavra por palavra. Roda no seu PC.

## Instalar (PC novo)

Dois cliques em **`INSTALAR.bat`**. Ele pede permissão de administrador e instala tudo sozinho: Python, ffmpeg, bibliotecas e a IA que você escolher. Também cria atalhos na área de trabalho e no menu Iniciar, e coloca o programa em **Configurações → Aplicativos**, com opção de desinstalar.

Depois, abra o programa, vá em **🔑 Contas & IA** e clique em **Conectar conta** na IA que for usar. Esse login só precisa ser feito uma vez, por você.

## Usar

Abra pelo atalho, ou com dois cliques em `interface.bat`.

### ✂ Corte
- **Normal:** cole o link, coloque início e fim e clique em GERAR CORTE.
- **🔎 Achar os melhores momentos sozinho:** marque a caixinha, diga quantos cortes quer e clique. O sistema escolhe os trechos.
- **Topo:** escolha entre *Automático* (thumbnail do YouTube ou um frame), *Estilo thumbnail ✨* (a IA escolhe o frame e ele ganha zoom, cores fortes e um emoji) ou *Frame escolhido pela IA*.
- **Perfil:** *Automático (pelo canal)* escolhe o perfil sozinho pelo canal de origem, ou você força um.

### 🔥 Tendências (vídeos bombando agora)
- Coloque seus **nichos** (podcast, react, futebol, BBB...) e clique em **BUSCAR EM ALTA**.
- O programa junta: **assuntos em alta no Brasil** (Google), **busca no YouTube ordenada por views** da semana/do dia e o **"Em alta" oficial do YouTube** (se estiver conectado).
- Cada vídeo ganha uma nota: **views por hora** desde que saiu, engajamento, se cita um **assunto em alta**, se já tem o gráfico de "mais repetidos" e se você já cortou.
- **✂ Cortar melhores momentos:** um clique e ele acha os trechos e gera os cortes.
- **Cortar sozinho os mais em alta:** com o monitor ligado, a cada 6h ele pega os vídeos mais quentes (até X por dia) e corta.
- Os assuntos em alta também vão pra IA (só quando têm relação direta com o trecho) pra entrar no título e nas hashtags. E cortes que citam um assunto em alta **passam na frente na fila**.

### 📊 Resultados (o programa aprende com os seus números)
- **⟳ Atualizar números do YouTube:** views, likes, comentários e **retenção** de cada Short postado pelo programa, além dos inscritos.
- **📥 Importar relatório do TikTok:** no TikTok Studio → Análises → Conteúdo → Baixar dados (CSV/Excel). Ele liga cada linha ao corte pelo título. Também dá pra digitar as views no botão 📈 da Galeria.
- **🧠 O que funciona no seu canal:** compara pergunta curta x longa, com nome x sem nome, formato da faixa, duração, horário, canal de origem e os testes A/B. Esse resumo vai junto pra IA, então **as próximas perguntas saem no estilo que dá mais views pra você**. Começa a funcionar a partir de 6 cortes com números.
- Gráfico de views por dia, top cortes, resultado por canal de origem e **progresso da monetização do TikTok** (10 mil seguidores e 100 mil views em 30 dias).
- **🎬 Compilação da semana:** junta os 5 melhores cortes num vídeo **horizontal** pro YouTube normal (paga mais por view), com intro, contagem regressiva, título e capítulos prontos. Aparece na Galeria pra postar.

### 🖼 Galeria (revisar e postar)
- Mostra todos os cortes com miniatura, nota da IA e status.
- **YouTube:** agenda o Short no próximo horário livre (ex: 12h, 18h, 21h). Ele sobe como privado e **o próprio YouTube publica na hora**, mesmo com o PC desligado.
  - Na primeira vez, clique em **Conectar YouTube**. O passo a passo completo (com prints do que clicar) está em **TUTORIAL-YOUTUBE.md**.
- **TikTok:** copia a legenda, abre a página de upload e a pasta do vídeo. Você arrasta, aperta Ctrl+V e clica Publicar. (A API do TikTok só posta como privado sem uma auditoria deles.)
- Cada corte mostra **views**, se é versão **A/B**, se é **espanhol**, o **perfil** e um **⚠** se já existem cortes parecidos no YouTube.
- **YouTube por perfil:** cada perfil pode postar num canal diferente. Escolha o perfil no topo e clique em **Conectar YouTube**. Cada canal também tem a sua agenda de horários.
- **📈:** digitar as views do TikTok à mão.
- **✏ Refazer:** gera de novo com outra pergunta na faixa.
- **🗑:** move pra pasta `_descartados`.
- **📱 Celular:** abre a galeria no navegador do celular (mesmo Wi-Fi). Aponte a câmera pro QR code e digite o PIN. Lá dá pra assistir, aprovar, **baixar o vídeo pra postar no app do TikTok**, copiar a legenda e agendar no YouTube. Se o Windows perguntar sobre o Firewall, marque **Redes privadas** e clique Permitir.

### 🤖 Automático
- Coloque os canais e clique em **LIGAR MONITOR**:
  - **Twitch (ao vivo):** grava as lives e corta quando o chat explode. Também corta os **clips mais vistos do dia**.
  - **Kick e YouTube (lives):** grava e acha os momentos mais agitados pelo áudio; a IA escolhe os melhores.
  - **YouTube (vídeos novos):** usa os trechos mais repetidos; sem esse gráfico, usa áudio + IA.
- **⚡ Corte de live na hora (termômetro):** a cada 30 segundos o programa mede o "calor" de cada live gravada somando vários sinais:
  - **pessoas diferentes** falando no chat (spam e bot não enganam);
  - **risada e choque** (KKKK, KEKW, ???, MEU DEUS);
  - **links de clip** no chat (os viewers clipando);
  - **pico de volume** no áudio;
  - **salto de espectadores** (vem da extensão).
  
  Tudo comparado com o normal daquele canal. Quando passa do limite, o corte entra na fila na hora, com prioridade, e fica pronto em poucos minutos.
  - **Ignora falso pico:** comandos (!sorteio), bots, copypasta repetida, trem de sub e sorteio.
  - **Sensibilidade:** Baixa (só lances muito fortes), Média ou Alta (corta mais). Pra um canal só: escreva `gaules:alta` na lista.
  - **Pedir minha aprovação:** em vez de cortar sozinho, o momento aparece na extensão com ✅/❌ (some em 10 min se ninguém aprovar).
  - **🩺 Modo diagnóstico:** anota cada pico (e os quase-picos) na pasta `diagnostico`. O botão **ver** mostra um resumo e diz se vale subir ou baixar a sensibilidade. Esse arquivo serve pra calibrar.
- **🖥 Painel das 4 lives:** até 4 lives da Twitch lado a lado, cada uma com **✂ CORTAR AGORA**.
- **🧩 Extensão do Chrome** (`chrome://extensions` → Modo do desenvolvedor → Carregar sem compactação → pasta `extensao_chrome`; se já tinha, clique no ↻ dela). Com o monitor ligado:
  - **Twitch e Kick:** aparece um painel no canto da live.
    - **Grava ao abrir:** abriu a live, o programa já começa a gravar, então o lance não se perde. Fechou a aba, ele para depois de 10 min (se o canal não estiver na sua lista).
    - **🔥 Alerta de chat:** a extensão lê o chat da página e pisca quando ele explode (KKKK, ???). Um clique corta.
    - **✂ CORTAR (Alt+C)** com **30s / 60s / 90s**, ou **⏱ marcar (Alt+M)** o começo do lance e cortar até agora.
    - **Nota pra IA:** depois de cortar, escreva o que aconteceu (opcional) e aperte Enter. A IA usa isso pra criar a pergunta da faixa.
    - Mostra se está gravando e quantos cortes estão na fila, e **o Chrome avisa quando o corte fica pronto**.
    - **🌡 Termômetro:** barra com o calor da live em tempo real (fica vermelha quando vai cortar) e a lista dos **momentos que o programa detectou sozinho**, com ❌ pra descartar (ou ✅ pra aprovar, se você ligou a aprovação).
    - **Kick:** o chat lido pela extensão também passa a ser usado pra achar os picos automaticamente.
  - **YouTube:** **⏱ Início**, **⏱ Fim** e **✂ GERAR** em qualquer vídeo (Alt+I, Alt+F, Alt+G).

- **🌙 Modo madrugada:** os cortes automáticos esperam o horário escolhido (ex: 01h às 07h), quando o PC está livre. Os manuais (extensão, Corte) rodam na hora. Opcional: **desligar o PC** quando terminar.
- **🎬 Compilação automática** todo domingo à noite.

### 🎨 Visual e perfis
- **Perfis (modo agência):** cada streamer ou canal seu pode ter o seu estilo: cor e formato da faixa, @, horários de postagem, efeitos e a conta do YouTube. Em **Canais deste perfil**, coloque os canais de origem que usam aquele perfil. Dá pra vender o serviço de cortes pra streamers com a marca de cada um.
- **Teste A/B:** gera também uma versão B com outra pergunta. Poste as duas (ex: uma no YouTube e outra no TikTok) e veja em Resultados qual estilo ganhou. A vencedora ensina a IA.
- **Versão em espanhol:** a IA traduz a pergunta, a legenda e o título (1 chamada curta) e gera o corte na pasta `espanhol`, pra um 2º canal voltado pra América Latina.
- **Checar se é inédito:** antes de montar, procura no YouTube se outros canais já postaram aquele lance esta semana.
- Posição, tamanho e cor da legenda, cor e **formato da faixa** (Rasgada, Pincelada, Fita adesiva, Adesivo ou Reta clássica) e selo do canal, com prévia ao vivo.
- **Efeitos:**
  - **Seguir o rosto:** a câmera acompanha quem fala, em vez de cortar sempre o meio.
  - **Tirar silêncios:** corta as pausas longas.
  - **Zoom + boom no gancho:** zoom rápido e um efeito sonoro no momento mais forte (a IA escolhe).
  - **Gancho no 1º segundo:** o corte abre com ~2s do momento mais forte e depois volta pro começo (o truque que mais segura a pessoa).
  - **Tirar é/tipo/né:** corta "é…" arrastado, "tipo," solto, "né?", "hum". É conservador: o "é" de "ele é louco" fica.
  - **Áudio no padrão:** volume igual em todos os cortes (-14 LUFS, o padrão do TikTok/Shorts), sem grave sujo e com a voz mais presente.
  - **Baixar em 1080p:** vídeo mais nítido (prefere H.264, que é leve de processar). As lives também gravam em 1080p — ocupa mais espaço (uns 3 GB por hora).
- **Legenda que acerta nomes:** o Whisper recebe o nome do canal e o título do vídeo antes de transcrever, então erra bem menos nome próprio. É automático e não gasta IA.
- **Qualidade (sem gastar IA):**
  - **Layout automático:** o programa olha os rostos do vídeo e escolhe sozinho:
    - **Podcast (2 pessoas lado a lado):** tela dividida, uma pessoa em cima e a outra embaixo. Quem está calado fica um pouco mais escuro e a legenda muda de cor conforme quem fala (branca = de cima, azul = de baixo).
    - **Jogo + facecam:** a câmera do streamer (no canto) vai pra cima, ampliada, e o jogo fica embaixo.
    - **Normal:** foto em cima, vídeo embaixo (como sempre).
    - Dá pra forçar um layout na caixinha **Layout**.
  - **Legenda animada:** cada bloco "pula" quando aparece.
  - **Emojis na legenda:** até 3 emojis nas palavras mais fortes (a IA escolhe na mesma chamada de sempre — não gasta nada a mais).
  - **Revisor automático:** antes de montar, confere se o corte começa ou termina no meio da frase (e ajusta), se a legenda ou a faixa vão ficar em cima de um rosto (e muda de lugar). Tudo no seu PC.
  - **Revisão com IA (+1 imagem):** opcional. Depois de pronto, a IA olha 4 quadros numa imagem só e, se achar legenda/faixa em cima de rosto, refaz uma vez.
  - **Corte em série:** em trechos longos (mais de ~95s), a IA escolhe o ponto de suspense e sai **Parte 1** (termina com "CONTINUA NA PARTE 2") e **Parte 2** (começa relembrando o fim da 1). Uma série faz o público procurar o seu perfil.
  - **Horário inteligente:** com uns 10 cortes postados e com números, troca os horários do perfil pelos que mais deram views (veja em Resultados → ⏰). Sempre mantém 1 horário de teste.
- **Seu @:** marca d'água no canto do vídeo.
- **Nota mínima:** a IA dá uma nota de 0 a 10 pra cada corte; abaixo da mínima, o corte é descartado antes de gastar tempo montando. 0 = não descarta.

### 🔑 Contas & IA
- **⚡ INSTALAR TUDO QUE FALTA:** um clique só.
- **IAs:**
  - **Claude:** assinatura do Claude.
  - **Codex:** conta do ChatGPT.
  - **Gemini:** grátis. Clique em **🔑 Colar chave da API** e cole a chave do Google AI Studio (fica salva só no seu PC, no `config.json` — não mande esse arquivo pra ninguém). Ou use o Gemini CLI com login da conta Google.
  - **Local:** grátis, roda no PC, mais lenta e mais simples.
  - **Nenhuma.**
- **Reserva:** se a IA escolhida falhar ou bater o limite, o sistema usa outra.
- **💰 Modo econômico:** o Claude usa o modelo mais leve (Haiku).

## Como o sistema economiza IA

- **Uma chamada por corte:** legenda, pergunta, título, hashtags e foto vêm todos de uma vez.
- **Imagens:** a IA vê um mosaico com 6 quadros numerados (1 imagem), não 6 imagens separadas. No modo podcast/jogo nem isso: o topo é vídeo, então não manda imagem nenhuma.
- **Emojis, ponto da série e revisor** vêm na mesma chamada (ou nem usam IA).
- **Achar momentos:**
  - Primeiro usa o gráfico do YouTube, que é de graça.
  - Se não tiver, mede o áudio no PC e transcreve só cerca de 8 trechos candidatos.
  - A IA lê só esses candidatos, nunca o vídeo inteiro.
- **Na live:** quem acha o pico é a contagem do chat. A IA só entra na hora de montar o corte.

## Dicas pro seu PC (sem placa de vídeo)
- O que pesa é gerar o corte, e eles são feitos um por vez.
- Uma live de 4h em 720p ocupa uns 6 a 12 GB enquanto grava. O programa pode apagar a gravação depois de cortar.
- Se o YouTube ou a Twitch pararem de baixar: **Contas & IA → Atualizar baixadores**.

## TikTok x YouTube
- O **TikTok** só paga vídeo com **60 segundos ou mais** (e pede 10 mil seguidores + 100 mil views em 30 dias). Por isso o padrão dos cortes é **65 segundos**.
- Nas duas plataformas, corte de conteúdo dos outros sem edição pode ser barrado da monetização como "não original". Faixa, legenda, zoom, efeitos e seu @ ajudam a mostrar que tem edição.

## Atualizações automáticas
Clique no botão **v3.6.0 ⟳** no topo e coloque o seu repositório do GitHub (ex: `seuusuario/gerador-de-cortes`). Quando você publicar uma **Release** nova lá (ex: `v3.1.0`), o botão fica amarelo e um clique atualiza: o programa troca os arquivos, guarda a versão anterior em `_versao_anterior` e **não mexe** nas suas configurações, contas, cortes e gravações. O arquivo `.gitignore` já impede que suas chaves e cortes subam pro GitHub.

## Importante
Revise antes de postar: a IA pode errar nome ou escolher um momento fraco. Prefira canais que permitem cortes.
