# Manual de uso

Faz cortes verticais no estilo dos cortes brasileiros: foto no topo, faixa com pergunta chamativa e vídeo embaixo com legenda palavra por palavra. Roda no seu PC.

## Instalar (PC novo)

### Jeito mais fácil: o instalador `.exe`

Mande pra pessoa o arquivo **`Instalar-Gerador-de-Cortes-<versão>.exe`** (um arquivo só, uns 3 MB). Ela dá dois cliques, clica **Avançar → Instalar** e pronto:

- o programa vai para `%LOCALAPPDATA%\Programs\Gerador de Cortes` (sem escolher pasta);
- aparece o atalho **Gerador de Cortes**, com o ícone do programa, na área de trabalho e no menu Iniciar (lá também fica o **Examinar o PC**);
- em seguida abre a janela azul do instalador, que faz os mesmos passos de baixo (Python, bibliotecas, ffmpeg, PATH e a escolha da IA);
- no fim, dá pra marcar **Abrir o Gerador de Cortes agora**.

Pra desinstalar: **Configurações → Aplicativos → Gerador de Cortes 9:16**. Ele remove o programa e o que baixou (`.venv`, `ffmpeg`) e pergunta se apaga também seus cortes e configurações (o padrão é guardar). Instalar uma versão nova por cima mantém seus cortes, contas e configurações.

**Gerar o `.exe`** (no seu PC): dê dois cliques em **`GERAR-SETUP.bat`**. Ele instala o Inno Setup (grátis) se precisar e cria o arquivo na pasta `dist`. Só entram os arquivos do programa que estão no git: suas contas, tokens, configurações, cortes e gravações **nunca** vão junto.

### Copiando a pasta

Copie a pasta para o PC novo (pendrive, zip ou `git clone`) e dê dois cliques em **`INSTALAR.bat`**. Ele pede permissão de administrador e faz tudo sozinho:

1. **Python 3.12:** acha ou instala (pelo winget ou direto do python.org, conferindo a assinatura). Ele fica separado dos outros Pythons do PC: se o PC já tiver o 3.13 ou o 3.14, nada muda neles. As bibliotecas do programa só funcionam no 3.12, e misturar versões era a causa do erro mais comum ao levar o programa pra outro PC.
2. **Doutor de instalação** (`doutor.py`): examina o PC e conserta o que faltar.
   - Cria o ambiente do programa (pasta `.venv`) e instala as bibliotecas nele.
   - Instala o Microsoft Visual C++ (sem ele dá "DLL load failed").
   - Baixa o ffmpeg completo (com legenda) pra pasta `ferramentas`, conferindo o hash oficial.
   - Arruma o PATH do Windows: o programa já acha tudo na hora, sem reiniciar o PC.
   - Se um passo der erro, ele lê o erro, reconhece os problemas comuns e tenta outro conserto. Ainda falhou e você tem uma IA instalada? Ele manda o erro pra ela, que escolhe o conserto **só entre os consertos seguros do doutor** (nunca roda comando inventado) e explica o que fazer à mão, se precisar.
3. **IA:** você escolhe Claude, Codex, Gemini ou Local. A Local já baixa o modelo recomendado pra memória do PC.
4. Cria atalhos na área de trabalho e no menu Iniciar, e coloca o programa em **Configurações → Aplicativos**, com opção de desinstalar.

Copiou a pasta de um PC que já tinha o programa? Sem problema: o doutor percebe que o `.venv` veio de outro PC e refaz. O atalho também se vira sozinho: se faltar alguma coisa, ele abre o instalador em vez de dar erro.

**Só examinar:** `EXAMINAR-PC.bat` (ou o botão **🩺 Examinar o PC** em Contas & IA) mostra o que o PC tem e o que falta, sem instalar nada. O registro completo de cada instalação fica em `instalacao.log`.

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
- **Só nos canais:** escolha esse modo e digite os canais separados por vírgula (`@flowpodcast`, o link do canal ou só o nome). Aparecem **só os vídeos desses canais** no período escolhido, sem assuntos do Brasil nem vídeos aleatórios. Se você digitar um `@` ou um link, o modo troca sozinho.
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
  - Na primeira vez, clique em **Conectar YouTube**. O passo a passo completo (com prints do que clicar) está em **[TUTORIAL-YOUTUBE.md](TUTORIAL-YOUTUBE.md)**.
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
- **📺 Janelinha da live:** quando um canal da lista entra ao vivo, a live abre numa janela pequena no canto da tela (Edge ou Chrome, sem barra nem abas) enquanto o robô grava e corta. Embaixo do vídeo aparecem há quanto tempo está gravando, quantos cortes saíram, o calor do chat e os últimos momentos detectados, além do **✂ CORTAR AGORA** (Twitch e Kick). Com mais de uma live, cada uma vira uma aba. Dá pra abrir pelo botão **📺 Janelinha da live** ou desligar a abertura automática na caixinha.
- **🖥 Painel das 4 lives:** até 4 lives da Twitch lado a lado, cada uma com **✂ CORTAR AGORA**.
- **🧩 Extensão do Chrome 3.0** (`chrome://extensions` → Modo do desenvolvedor → Carregar sem compactação → pasta `extensao_chrome`; se já tinha, clique no ↻ dela e recarregue as abas abertas). Com o monitor ligado:
  - **Painel novo** em Twitch, Kick e YouTube, com abas **Cortar**, **Momentos** e **Bot**. Dá pra arrastar pelo topo (ele lembra onde você deixou) e minimizar numa **bolinha** que pisca quando acontece algo.
  - **Ícone da extensão** (barra do Chrome): mostra se o programa está ligado, a IA do bot, as lives gravando (com o calor), a fila e os últimos cortes prontos. Lá também ficam as **configurações**: ligar ou desligar o painel em cada site, o bot comentando sozinho e o bot usando a IA.
  - **Twitch e Kick:**
    - **Grava ao abrir:** abriu a live, o programa já começa a gravar, então o lance não se perde. Fechou a aba, ele para depois de 10 min (se o canal não estiver na sua lista).
    - **Chat agora:** gráfico das mensagens dos últimos 5 minutos, mensagens por minuto, quantas vezes acima do normal, % de risada e as palavras do momento.
    - **🔥 Alerta de chat:** pisca quando o chat explode (KKKK, ???). Um clique corta.
    - **✂ CORTAR (Alt+C)** com **30s / 60s / 90s**, ou **⏱ marcar (Alt+M)** o começo do lance e cortar até agora.
    - **Nota pra IA:** depois de cortar, escreva o que aconteceu (opcional) e aperte Enter. A IA usa isso pra criar a pergunta da faixa.
    - **🌡 Termômetro** com o calor da live em tempo real e, na aba **Momentos**, o que o programa detectou sozinho (✅ aprovar / ❌ descartar) e os cortes que você fez nesta live. **O Chrome avisa quando o corte fica pronto.**
    - **Kick:** o chat lido pela extensão também passa a ser usado pra achar os picos automaticamente.
  - **YouTube:**
    - **⏱ Início**, **⏱ Fim**, **↶ últimos 30s/60s** e **✂ GERAR** (Alt+I, Alt+F, Alt+G), com a duração na hora e **▶ assistir o trecho**.
    - **Momentos:** os **picos do gráfico "mais assistidos de novo"** do YouTube e os **minutos citados nos comentários** (4:05, 4:08 e 4:10 viram um lance só). ▶ vai até o ponto e ✂ marca 1 minuto em volta.
  - **🤖 Bot:** um assistente dentro do painel. Botões prontos (**Vale cortar agora?**, **O que rolou?**, **Sugere um título**, **Melhores momentos**) ou pergunte o que quiser.
    - **Com IA** (a que estiver em Contas & IA: Claude, Codex, Gemini ou Local): lê o chat recente, os números do chat, os momentos detectados, o título e os comentários, e responde com **nota de 0 a 10**, o **gancho da faixa** (com botão de copiar), títulos e **botões de ação** (✂ cortar 60s, ⏱ marcar, ▶ ir para 4:05, ✂ marcar trecho).
    - **Sem IA:** responde com os números do chat e os momentos achados (modo básico).
    - **Sozinho:** quando o chat explode, ele comenta o que está rolando e, com IA, já diz se vale cortar (no máximo 1 análise a cada 3 min).
    - **Segurança:** o chat e os comentários vão pra IA só como material (se alguém no chat tentar "mandar" no bot, ele ignora) e as sugestões viram botões: **nada acontece sem o seu clique**. No YouTube, o bot só marca o trecho; gerar continua sendo com você.

- **🌙 Modo madrugada:** os cortes automáticos esperam o horário escolhido (ex: 01h às 07h), quando o PC está livre. Os manuais (extensão, Corte) rodam na hora. Opcional: **desligar o PC** quando terminar.
- **🎬 Compilação automática** todo domingo à noite.

### 🎨 Visual e perfis
- **Perfis (modo agência):** cada streamer ou canal seu pode ter o seu estilo: cor e formato da faixa, @, horários de postagem, efeitos e a conta do YouTube. Em **Canais deste perfil**, coloque os canais de origem que usam aquele perfil. Dá pra vender o serviço de cortes pra streamers com a marca de cada um.
- **Teste A/B:** gera também uma versão B com outra pergunta. Poste as duas (ex: uma no YouTube e outra no TikTok) e veja em Resultados qual estilo ganhou. A vencedora ensina a IA.
- **Versão em espanhol:** a IA traduz a pergunta, a legenda e o título (1 chamada curta) e gera o corte na pasta `espanhol`, pra um 2º canal voltado pra América Latina.
- **Checar se é inédito:** antes de montar, procura no YouTube se outros canais já postaram aquele lance esta semana.
- Posição, tamanho e cor da legenda, cor e **formato da faixa** (Rasgada, Pincelada, Fita adesiva, Adesivo, Balão de fala, Neon ou Reta clássica) e selo do canal, com prévia ao vivo. O botão **👁 Ver formatos** mostra uma amostra de cada faixa com as suas cores; é só clicar na que você quer.
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
  - **Local:** grátis, roda no PC, mais lenta e mais simples. Em **Modelo da IA local** escolha o tamanho: *Leve* (1,9 GB, qualquer PC), *Média* (4,7 GB, 16 GB de RAM), *Forte* (8,1 GB) ou *Máxima* (9 GB, PC forte ou placa de vídeo). O programa mostra a memória do seu PC e qual é o recomendado. Clique em **Instalar / baixar modelo**: baixa uma vez só; um modelo que já está no PC não baixa de novo.
  - **Nenhuma.**
- **Reserva:** se a IA escolhida falhar ou bater o limite, o sistema usa outra.
- **Qualidade da IA:** *Econômica* (Haiku em tudo), *Equilibrada* (Sonnet nos cortes e na escolha de momentos, Haiku no resto) ou *Máxima* (Opus nos cortes). O botão **📊 Uso da IA** mostra chamadas, falhas, tempo e tokens dos últimos 7 dias.

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

## Atualizações
O jeito recomendado é manter a pasta do programa como repositório git (é assim que ela está no GitHub):
para atualizar, clique no botão de versão no topo ou rode `git pull` na pasta. O atualizador nunca
sobrescreve alteração sua: se houver algo não salvo (commit), ele avisa e não mexe em nada.

Sem git, o botão de versão também funciona com **Releases** do GitHub: coloque o repositório
(ex.: `seuusuario/gerador-de-cortes`), e quando houver uma release mais nova ele baixa e troca os
arquivos, guardando a versão anterior em `_versao_anterior` (configurações, contas, cortes e gravações
não são mexidos).

## Importante
Revise antes de postar: a IA pode errar nome ou escolher um momento fraco. Prefira canais que permitem cortes.
