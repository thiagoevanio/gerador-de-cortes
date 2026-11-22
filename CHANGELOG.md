# Histórico de versões

As mudanças mais novas ficam em cima.

## 3.27 — Gancho fora do rosto, legenda fora do texto do vídeo e silêncio pelo volume

- **Pergunta do gancho não tampa mais o rosto** (estilo clean): o revisor vê onde o rosto fica e, se
  a pergunta cair em cima dele, ela vai pra cima do rosto (se couber abaixo dos botões do app) ou logo
  abaixo dele — sem descer até a legenda. Trocar a pergunta na Central de edição mantém o lugar.
- **Legenda não briga com texto que já vem no vídeo**: legenda do jogo, vídeo que já veio legendado...
  O revisor acha a faixa de letras gravadas embaixo (letras alinhadas, centralizadas, que mudam com o
  tempo — logo de camiseta, janela clara e letreiro parado não contam) e põe a nossa logo acima dela.
- **Tirar silêncios pelo volume do próprio vídeo**: antes o corte era em -32 dB fixo e, com microfone
  baixo, comia final de palavra (no teste, o mesmo áudio 16 dB mais baixo perdia 4,4 s de fala). Agora
  o limite acompanha a fala do vídeo — áudio normal continua igual. Trava: se as "pausas" passarem de
  40% do corte, não corta nada (é medida errada, não pausa).
- **Modo PC fraco** agora usa mesmo o Whisper "base" na legenda (o "small" de fábrica sempre ganhava).
- ⚙ Qualidade: a opção **turbo** da legenda do corte diz o que custa (~3x mais lenta, baixa 1,6 GB uma vez).

## 3.26.2 — Correções da análise completa

- **Prévia da aba Visual**: não quebra mais quando a limpeza automática do Windows apaga a pasta Temp
  com o programa aberto (a pasta é recriada na hora).
- **Reels do Instagram**: com um vídeo aberto no player o Windows não deixa renomear; antes a pasta
  podia ficar com nomes `~1a2b3c4d_ID.mp4` e esses reels baixavam de novo, duplicados. Agora ela desfaz
  o que mexeu e organiza na próxima vez (e avisa pra fechar o vídeo). Pasta já em ordem não é mexida.
- **Examinar PC (Doutor)**: o conserto "reinstalar bibliotecas" reinstalava a biblioteca errada (a
  lista estava desalinhada — faltando o Whisper, reinstalava o streamlink). Corrigido.
- **Galeria no celular**: PIN de **6 dígitos** (o de 4 é trocado sozinho) e, depois de 5 PINs errados,
  ninguém entra por 5 minutos — ninguém no mesmo Wi-Fi consegue ficar chutando.
- **Extensão**: o programa agora só conversa com a extensão do Cortes (ID fixo); outra extensão do
  Chrome não consegue mais pegar a senha interna nem mandar comando. **Remova a extensão em
  chrome://extensions e carregue de novo** (Carregar sem compactação → pasta `extensao_chrome`).
- **Legenda da versão em espanhol**: recebeu a mesma correção da 3.23 — cada frase é dividida pra
  caber numa linha e nenhuma encavala na outra (não pula nem pisca).
- Monitor: quando recusava um pedido (sessão vencida), às vezes a conexão caía antes da resposta e a
  extensão via "desligado" em vez da mensagem. Agora a resposta sempre chega.
- O gerador de instalador deixa só os 2 mais novos na pasta `dist`; limpeza de código sem uso.

## 3.26.1 — Reels sempre do mais recente pro mais antigo

- A pasta do perfil fica em ordem: `001 - 2026-11-19 - ID.mp4` (o **001 é sempre o mais recente**; chegou
  reel novo, a pasta é renumerada). A "data de modificação" de cada arquivo vira a data da postagem — no
  Windows fica em ordem por nome ou por data. Antes os arquivos tinham só o código do reel e a pasta
  parecia embaralhada (o download já era do mais novo pro mais velho).
- Reels **fixados** no topo do perfil (que podem ser antigos) vão pro fim da fila e não ocupam a vaga
  dos mais recentes quando você pede 12, 30...
- A data e a hora exatas da postagem ficam no `reels.json`. Pastas baixadas antes são reorganizadas no
  próximo download (os já baixados continuam sem baixar de novo).

## 3.26 — 📥 Reels do Instagram (sem marca d'água)

- Baixa os reels de um perfil no **arquivo original** que o Instagram guarda (o mesmo que o cobalt faz):
  sem o logo, sem o @ flutuando e sem a tela do final que o botão "baixar" do app coloca. Qualidade
  original (testado: 1080×1920 e até 1440×2560).
- O Instagram não deixa programa nenhum listar os reels de um perfil (testado: o yt-dlp falha no
  perfil), então quem lista é a **extensão**: na página do perfil aparece o painel **Baixar reels**
  (12, 30, 60, 150 ou todos); ela abre a aba Reels, rola a página sozinha juntando os links (só os deste
  perfil — as sugestões de outras contas ficam de fora) e o programa baixa um por um.
- No programa: botão **📥 Instagram** na aba Corte — digite o @, ele liga o monitor, abre o perfil no
  Chrome e a extensão começa sozinha. **📁 Pasta dos reels** abre `reels_instagram/@perfil`.
- Pausa de 2-5 s entre um reel e outro (ritmo de gente); os já baixados não baixam de novo; um reel
  ruim não para os outros; se o Instagram começar a bloquear (3 falhas seguidas pedindo login), para e
  avisa — o que já baixou fica. Botão ■ parar.
- `reels.json` na pasta do perfil com a legenda, a data e a duração de cada reel.
- Sem login o Instagram mostra só uns 12 reels: o painel avisa pra entrar na conta (no seu Chrome) e
  clicar de novo. Com a aba do Instagram escondida a página não carrega mais — o painel espera você voltar.
- Extensão 3.2 (recarregue em chrome://extensions); opção "Painel no Instagram" no ícone da extensão.

## 3.25 — 🤖 IA corta os melhores momentos (extensão, YouTube)

- Novo cartão no topo da aba **Momentos** do painel do YouTube: escolha quantos cortes (1-5) e a
  duração (30-90 s) e clique em **ACHAR E CORTAR SOZINHA**. Atalho na aba Cortar.
- A IA usa o "achar momentos" do programa (ouve os trechos candidatos, começo e fim nas frases certas) e
  agora recebe o que só a extensão vê na página: os **minutos citados nos comentários** viram candidatos
  fortes (como o chat de uma live, com o texto dos comentários indo pra IA) e os **picos do gráfico de
  replays** completam o que o yt-dlp não trouxe. Aqui a IA sempre confere (nada de cortar só pelo gráfico
  com 60 s fixos).
- Os cortes vão pra fila do monitor (prioridade alta) com o motivo da IA como contexto; o painel mostra a
  etapa em andamento e, no fim, a lista dos cortes com nota e motivo. Recarregou a página? O andamento
  volta. Um trabalho por vez (achar momentos é pesado no processador).
- Testado com um vídeo real de 40 min: com um comentário citando 33:45, a IA escolheu exatamente esse
  lance (33:30–34:35, nota 7) e mais um trecho; ~7 min no total.
- Extensão 3.1 (recarregue em chrome://extensions).

## 3.24.1 — Assistir antes de queimar

- Aba Legendar: **▶ Assistir com a legenda** gera em segundos uma versão leve (lado menor 540 px) com o
  texto revisado e o estilo atual e abre no player do PC — dá pra ajustar e assistir de novo antes de
  queimar a definitiva. Vídeo longo: os primeiros 4 min. **▶ Original** abre o vídeo sem legenda.

## 3.24 — Aba 📝 Legendar

Nova aba pra **só legendar um vídeo que já está editado** no PC — sem cortar, sem mudar o formato, sem
mexer no áudio.
- Vertical, horizontal ou quadrado: a legenda é desenhada na tela do próprio vídeo (o lado menor vale
  1080, então tamanho e posição significam o mesmo em qualquer formato) e o fps original é mantido.
- **Prévia no seu vídeo**: um quadro de verdade com a legenda no template escolhido (↻ troca o quadro).
- Os mesmos templates dos cortes, já com a legenda que não pula nem pisca (3.23); posição, tamanho e
  palavras por vez ajustáveis.
- IA opcional: corrige nomes (com a trava contra palavra duplicada) e escolhe as palavras-chave coloridas
  (só palavra forte, no máximo 1 a cada ~8). Vídeo longo vai em pedaços.
- **Revisão antes de queimar**: o texto aparece uma frase por linha, com o tempo; mudou a quantidade de
  palavras, o tempo da frase é redividido sozinho; apagar o texto da linha tira a frase.
- Tira "hum/éé" da legenda (o vídeo não muda). Seu @ é opcional.
- Sai `nome_legendado.mp4` + `.srt` ao lado do original (nunca sobrescreve). Áudio copiado como está
  (só vira AAC se o formato não couber num .mp4). Passa pela revisão técnica antes de salvar.
- `gerar_ass` aceita a tela do vídeo (`largura`, `altura`) e o tamanho base.

## 3.23 — Legenda que não pula nem pisca

**Legenda pulando pra cima e voltando (2 causas, as duas corrigidas)**
- **Quebra de linha no meio do bloco:** quando as palavras do bloco eram longas (ou a palavra falada
  crescia no "pop"), o bloco não cabia na largura e virava 2 linhas — a legenda subia ~70 px e descia
  no bloco seguinte. Agora o programa mede cada bloco com a fonte de verdade (o mesmo tamanho que o
  libass desenha) e, se não couber, divide em blocos menores: a legenda é **sempre uma linha, sempre na
  mesma altura**. Palavra gigante sozinha encolhe pra caber. Medido: o salto caiu de 71 px pra 9 px
  (só o "pop" normal da palavra falada) no template Clássico.
- **Duas legendas ao mesmo tempo:** com palavras quase coladas no Whisper (< 0,1 s), a legenda de uma
  palavra ficava na tela junto com a do bloco seguinte e as duas eram desenhadas uma por cima da outra.
  Agora a linha do tempo da legenda é limpa: nunca encavala, destaque de 1 quadro vira parte do
  anterior e buraco de até 0,15 s entre blocos é emendado (sem "apaga e acende").

**Central de edição em sincronia**
- Revisar a legenda e trocar a pergunta remontavam o corte **sem a prévia do gancho** (que desde a 3.21
  é montada no render) — a legenda saía ~2 s fora de sincronia. A receita agora guarda a prévia.

**IA local**
- **Liga sozinha:** depois de reiniciar o PC o Ollama fica desligado e a IA local falhava em todo
  corte. Agora o programa liga o Ollama quando precisa.
- **Pré-carrega o modelo** enquanto o Whisper transcreve (o 1º corte não espera ~2 min de disco).
- Blindagem contra os vícios de modelo pequeno: pergunta com "???" ou "?" vira "??"; palavras-chave em
  sequência (0,1,2,3) ou vazias ("o", "que", "é") são descartadas ("NÃO" e nomes continuam valendo);
  gancho em palavra vazia ou na 1ª palavra é refeito pelo áudio; destaque em "O QUE" vira as palavras
  fortes da pergunta; chamada copiada da pergunta é descartada.
- O log do download do modelo mostra o andamento de 10 em 10% (antes enchia de "rodinhas").

## 3.22 — IA local completa, legenda que não duplica e posição livre

**Legenda no lugar que você escolher**
- A barra **Posição da legenda** agora manda de verdade: antes a "zona segura" do TikTok (480 px) e um
  ajuste do estilo clean (+330 px) empurravam a legenda pra cima por mais que você descesse a barra.
- A barra vai de 10 (colada no rodapé) a 1500 (quase no topo), com botões **▼ ▲** pra ajuste fino.
- A área dos botões do app virou só um **guia vermelho tracejado** na prévia ("Mostrar botões do app").
- O revisor que desvia do rosto só **desce** a legenda; nunca sobe além do que você escolheu.
- Com a legenda colada no rodapé, o seu **@** vai pro canto de cima (pra não encostar na legenda).

**Legenda sem palavra duplicada**
- **Trava da legenda:** correção da IA que repetiria palavra (ex.: "Renato" → "Renato Cariani" com
  "Cariani" logo depois), que deslocaria a lista ou que não tem nada a ver com o áudio é desfeita.
- **Whisper sem eco:** sem `condition_on_previous_text` (o que causava frase repetida em loop) e uma
  limpeza remove a palavra emitida 2 vezes no mesmo instante e loops de alucinação.

**IA local (Ollama) que faz tudo**
- **Memória do tamanho do pedido** (`num_ctx`): o Ollama usava 2-4 mil tokens e cortava o começo dos
  pedidos grandes sem avisar — a IA local respondia sem ver a transcrição inteira. Esse era o maior erro.
- Agora ela também corrige a legenda, marca o gancho, as palavras-chave, os emojis, a abertura, o trecho
  da live e a divisão em partes (antes só fazia pergunta e título). Só a foto continua sendo escolhida
  no PC (modelo local não enxerga imagem).
- **Molde de JSON** no fim do pedido (modelo pequeno erra menos copiando um formato), temperatura baixa,
  o modelo fica carregado 15 min entre cortes e o tempo limite nunca é menor que 4 min.
- Respostas conferidas: nota fora de 0-10, emoji escrito em texto, tipos trocados — tudo vira o padrão.
- A pergunta feita no PC concorre com a da IA local; o juiz fica com a melhor.
- Vários cortes de uma vez: com IA local vai 1 por chamada (o lote confundia modelo pequeno).
- Avisa quando o modelo escolhido não está baixado no Ollama.

## 3.21 — Mais qualidade de imagem, de som e de edição

O corte final saía "magro" (4,5 Mbps; as plataformas recomendam 8–12 e recomprimem ao receber) e o
vídeo passava por até 4 recompressões seguidas. Agora:
- **O dobro de bitrate no vídeo final:** o Quick Sync liga o modo **look-ahead** (olha os quadros
  seguintes antes de gastar os bits) — ~10 Mbps com a mesma velocidade. Se o chip não tiver o modo,
  usa qualidade fixa mais alta; o teste é feito 1 vez por sessão.
- **Uma recompressão a menos:** a prévia do gancho entra **direto na montagem final** (antes era um
  arquivo re-comprimido no meio). Também poupa ~20 s por corte.
- **Etapas do meio quase sem perda:** o recorte do trecho e a edição de pausas/vícios agora saem em
  qualidade 15 (eram 20 e 17) — menos "pele borrada" de perda em cima de perda.
- **60 fps automático:** fonte em 60 fps (gameplay) sai em 60 fps. Desligado no Modo PC fraco
  (`fps_auto` na config). Keyframe a cada 2 s, como as plataformas pedem.
- **Volume sem "bombeamento":** o nivelamento (loudnorm) agora mede primeiro e aplica de forma
  linear (2 passadas). Áudio final em 256k.
- **Exposição automática:** vídeo escuro (gameplay noturno, podcast mal iluminado) ganha um
  levantamento suave de gama antes de montar.
- **Zoom lento de retenção:** zoom quase imperceptível do início ao fim, novo efeito de template
  (`zoom_lento`; o Podcast Premium já usa).

## 3.20 — Aba Contas que rola e 3 faixas novas

- **Contas & IA:** a aba ganhou barra de rolagem (e rola com a rodinha do mouse). Antes, em telas
  menores, a parte de baixo (qualidade da IA, uso da IA) ficava escondida.
- **3 formatos novos de faixa** (Visual → Formato da faixa), todos com as cores do estilo escolhido:
  - **Plantão (jornal):** barra reta com a etiqueta "URGENTE" e a tarja branca com o canal.
  - **Explosão (HQ):** estrela de quadrinho com contorno preto e sombra chapada.
  - **Diagonal (esporte):** faixa inclinada com bloco deslocado e listras de velocidade.
- O **👁 Ver formatos** agora mostra as amostras em 3 colunas, pra caber os 10 formatos na tela.

## 3.19 — Downloads do YouTube que não travam

O problema: cortes de vídeos do YouTube demoravam demais ou não terminavam. Medido: o download do
trecho (45 s de um vídeo de 18 min) ficava parado por **mais de 10 minutos**.
- **Causa 1 — desafio do YouTube:** o YouTube passou a exigir um desafio em JavaScript ("n challenge").
  Sem resolver, ele estrangula a velocidade. Agora o yt-dlp usa o pacote **yt-dlp-ejs** com o **Node.js**
  (ou Deno) em todos os lugares (`baixador.opcoes_ytdlp`). O Examinar o PC confere o Node e instala se faltar.
- **Causa 2 — download do trecho:** o jeito antigo abria o vídeo inteiro (378 MB) numa conexão só.
  Agora o programa lê o índice do arquivo (sidx) e baixa **só os pedaços do trecho**, em pedidos de até
  10 MB: **4 s** em vez de travar. O corte inteiro do YouTube, do link ao vídeo pronto: ~1 min 45 s.
- **Nada fica travado:** se o jeito rápido não servir (outro site, formato sem índice), o jeito
  tradicional roda num processo separado **com limite de tempo** e tenta de novo.
- **yt-dlp sempre em dia:** a cada 3 dias o programa atualiza o yt-dlp e o yt-dlp-ejs sozinho, em segundo
  plano (o YouTube muda toda semana). A versão deixou de ficar presa.
- **Chip de vídeo:** os passos que duplicam e emendam o vídeo (gancho, pausas) decodificam no processador
  (a memória fixa do chip da Intel enchia); se o chip falhar num comando, só aquele volta pro processador.
- O áudio do vídeo inteiro (pra achar os momentos) também baixa em pedidos de 10 MB.

## 3.18 — Desempenho: cortes ~45% mais rápidos

Medido num i5-7200U (2 núcleos, Intel HD 620), mesmo corte de 45 s: **186 s → 100 s**.
- **Rostos 5x mais rápidos** (62 s → 17 s): o vídeo é lido em sequência (`efeitos.amostras_video`) em vez
  de pular pra cada amostra, o que obrigava a decodificar de novo desde o último quadro-chave.
- **Chip de vídeo no recorte e nos intermediários:** o recorte do trecho e os arquivos de passagem
  (gancho, pausas) usam o encoder de hardware, e o **chip também decodifica** (`-hwaccel`). Recorte
  36 s → 11 s. Se o chip não aceitar um vídeo, aquele comando refaz no processador sozinho.
- **Projeto de edição 5x menor:** o `com_gancho.mp4` guardado pra reeditar caiu de 240 MB para 47 MB.
- **Lives checadas em paralelo** (4 por vez): cada checagem leva ~6 s; com 10 canais, a rodada caiu de
  ~1 min para ~15 s.
- **Progresso com tempo restante** no recorte e na montagem ("Montando o vídeo: 50% (falta ~13 s)").
- **Tempos por etapa** de cada corte em `analises/tempos.jsonl`.
- **Novas ferramentas em Contas & IA:** ⚡ Testar velocidade, 🐢 Modo PC fraco e 🧹 Espaço em disco
  (limpeza automática dos projetos de edição com mais de 30 dias e aviso de disco quase cheio).

## 3.17 — Extensão do Chrome 3.0 com bot

- **Painel novo** em Twitch, Kick e YouTube (`ui.js`): visual isolado do site (shadow DOM), abas
  **Cortar / Momentos / Bot**, arrastável (lembra a posição por site) e minimizável numa bolinha que pisca.
- **Chat agora** (Twitch/Kick): gráfico dos últimos 5 min, msg/min, quantas vezes acima do normal,
  % de risada e as palavras do momento. Aba Momentos com o que o programa detectou e os cortes da live.
- **YouTube:** "últimos 30/60 s", duração na hora, assistir o trecho e a aba **Momentos** com os picos do
  gráfico "mais assistidos de novo" e os minutos citados nos comentários (agrupados por lance).
- **🤖 Bot** (`bot.py` + rota `/bot` do monitor): usa a IA de Contas & IA pra analisar o chat/comentários,
  dar nota, sugerir gancho e títulos e propor ações (cortar, marcar, gravar, ir para o minuto, marcar
  trecho) que viram **botões** — nada acontece sem clique. Chat e comentários vão como material, nunca
  como instrução; ações fora da lista e números fora dos limites são descartados. Sem IA, responde com os
  números do chat. Comenta sozinho quando o chat explode (com IA, no máximo 1 análise a cada 3 min).
- **Popup do ícone:** programa ligado/desligado, IA do bot, lives gravando com o calor, fila, cortes prontos
  e configurações (painel por site, bot automático, bot com IA).
- `/status` do monitor passa a informar a IA do bot e a versão do programa.

## 3.16 — Instalador .exe com atalho personalizado

- **`Instalar-Gerador-de-Cortes-<versão>.exe`:** um arquivo só (uns 3 MB), feito com o Inno Setup.
  Dois cliques → Avançar → Instalar. Copia o programa para `%LOCALAPPDATA%\Programs\Gerador de Cortes`
  (não precisa de admin pra copiar), cria o atalho **Gerador de Cortes** com o ícone na área de trabalho
  e no menu Iniciar, roda o instalador (`instalar.ps1 -Setup`: Python, bibliotecas, ffmpeg, PATH, IA) e
  oferece abrir o programa no fim.
- **Desinstalar** por Configurações → Aplicativos: remove o programa, o `.venv` e o `ffmpeg` baixado, e
  pergunta antes de apagar cortes e configurações (padrão: guardar). Atualizar por cima mantém tudo.
- **`GERAR-SETUP.bat`** gera o `.exe` na pasta `dist`. Só empacota os arquivos do git: contas, tokens,
  configurações, cortes, gravações e testes ficam de fora.
- `instalar.ps1` espera a janela de administrador terminar e, numa instalação feita pelo `.exe`, não
  duplica atalhos nem a entrada em Aplicativos.

## 3.15 — Instalação à prova de PC novo

- **Doutor de instalação** (`doutor.py`, só biblioteca padrão, roda em qualquer Python 3.8+): examina
  o PC (Windows 64 bits, disco, internet, Python, bibliotecas, Visual C++, ffmpeg com legenda, PATH,
  winget) e conserta o que falta. Usado pelo `INSTALAR.bat`, pelo botão ⚡ INSTALAR TUDO e pelo novo
  **🩺 Examinar o PC** (também em `EXAMINAR-PC.bat`).
- **Python certo sempre:** o programa roda num ambiente próprio (`.venv`) com o Python 3.12, separado
  dos outros Pythons do PC. Antes, um PC com 3.13/3.14 (ou o atalho falso da Microsoft Store) fazia as
  bibliotecas falharem. Um `.venv` copiado de outro PC é detectado e refeito.
- **Sem depender do winget:** Python (python.org, assinatura da Python Software Foundation conferida),
  Visual C++ (Microsoft, assinatura conferida) e ffmpeg (gyan.dev, hash SHA-256 conferido) são baixados
  direto quando o winget não existe ou falha. O ffmpeg vai pra pasta `ferramentas` e vale na hora.
- **PATH:** o doutor grava as pastas no PATH do usuário e o programa as acrescenta ao abrir, então nada
  depende de reiniciar o PC.
- **Lê o erro e tenta de novo:** regras para os erros comuns (DLL faltando, versão sem pacote, download
  corrompido, comando não reconhecido, `.venv` de outro PC) e passos manuais para o que não tem
  conserto automático (certificado SSL, disco cheio, arquivo em uso, internet). Se ainda falhar e houver
  uma IA, ela recebe o exame e o log e escolhe consertos **só da lista do doutor** — nunca roda comando
  inventado.
- **Atalhos espertos:** `interface.bat`, `monitor.bat` e `cortar.bat` acham o Python com as bibliotecas
  (`_python.bat`) e, se faltar algo, abrem o instalador em vez de dar erro.
- A IA local, quando escolhida no instalador, já baixa o modelo recomendado pra memória do PC.

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
