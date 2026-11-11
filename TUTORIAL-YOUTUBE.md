# Tutorial: conectar o YouTube (uma vez só, ~10 minutos)

O programa já sabe postar sozinho no YouTube. O Google só exige que **você** crie uma "chave de app"
(o arquivo `client_secret.json`) na sua conta. É de graça e não precisa de cartão.

---

## Passo 1 — Criar o projeto
1. Entre em **https://console.cloud.google.com** com a conta Google do seu canal.
2. Lá em cima, clique no seletor de projeto → **Novo projeto**.
3. Nome: `Gerador de Cortes` → **Criar**. Espere uns segundos e confira se ele ficou selecionado lá em cima.

## Passo 2 — Ligar as 2 APIs
1. Menu ☰ → **APIs e serviços** → **Biblioteca**.
2. Procure **YouTube Data API v3** → **Ativar**.
3. Volte na Biblioteca, procure **YouTube Analytics API** → **Ativar** (é ela que traz views e retenção pra aba Resultados).

## Passo 3 — Tela de consentimento (o "nome do app" no login)
1. Menu ☰ → **APIs e serviços** → **Tela de consentimento OAuth**
   (em contas novas aparece como **Google Auth Platform**; clique em **Começar**).
2. **Nome do app:** `Gerador de Cortes` · **E-mail de suporte:** o seu.
3. **Público-alvo:** **Externo**.
4. **Dados de contato:** o seu e-mail → aceite os termos → **Criar**.
5. Em **Público-alvo** (ou **Usuários de teste**), adicione o seu e-mail.
6. Ainda em **Público-alvo**, clique em **Publicar app** → **Confirmar**.
   > Isso é importante: em modo "Teste" o login **expira a cada 7 dias** e você teria que conectar de novo.
   > Não precisa mandar o app pra verificação do Google — é só pra você.

## Passo 4 — Baixar a chave (client_secret.json)
1. Menu ☰ → **APIs e serviços** → **Credenciais** (ou **Clientes** no Google Auth Platform).
2. **Criar credenciais** → **ID do cliente OAuth**.
3. **Tipo de aplicativo:** **App para computador** (Desktop). Nome: `Cortes PC` → **Criar**.
4. Clique em **Baixar JSON**. Guarde o arquivo (ele termina em `.json`).
   > Não mande esse arquivo pra ninguém nem coloque no GitHub — ele é a chave do seu app.

## Passo 5 — Conectar no programa
1. Abra o programa → aba **🖼 Galeria**.
2. Em **Conta do YouTube do perfil**, escolha o perfil (ex: `Padrão`).
3. Clique em **▶ Conectar YouTube** → **Sim** → escolha o JSON que você baixou.
4. Vai abrir o navegador:
   - Escolha a conta do canal.
   - Vai aparecer **"O Google não verificou este app"** → clique em **Avançado** →
     **Acessar Gerador de Cortes (não seguro)**. (É normal: o app é seu, só não passou pela verificação.)
   - Marque **todas** as caixinhas de permissão → **Continuar**.
5. O botão vira **✔ conectado**. Pronto!

## Passo 6 — Usar
- Em cada corte da Galeria, clique em **YouTube**: ele sobe agora como privado e **o YouTube publica
  sozinho** no próximo horário livre do perfil (mesmo com o PC desligado).
- Pelo celular (botão **📱 Celular**) também dá pra agendar.
- **Mais de um canal?** Crie um perfil por canal na aba **🎨 Visual**, escolha ele na Galeria e clique
  em Conectar de novo — o mesmo `client_secret.json` serve pra todos.
- **Horário inteligente** (aba Visual): depois de uns 10 cortes postados com números, o programa troca
  os horários do perfil pelos que mais deram views (e sempre deixa 1 horário "teste" pra continuar aprendendo).

---

## Limites e problemas comuns
| Situação | O que fazer |
|---|---|
| Cota | Cada projeto pode subir **até 100 vídeos por dia** (cota própria de envio, separada da leitura de números). Sobra muito pra cortes. |
| "Acesso bloqueado" / erro 403 `access_denied` | Seu e-mail não está em Usuários de teste, ou o app não foi publicado (Passo 3, itens 5 e 6). |
| Pede login de novo toda semana | O app ficou em modo **Teste**. Clique em **Publicar app** (Passo 3, item 6) e conecte de novo. |
| `invalid_grant` | O login venceu ou foi revogado. Clique em **Conectar YouTube** de novo. |
| Vídeo fica preso como privado | Confira em studio.youtube.com se o canal está verificado por telefone (youtube.com/verify). |
| Erro de cota (`quotaExceeded`) | A cota zera à meia-noite do horário do Pacífico (umas 4h–5h da manhã em Brasília). Espere ou use outro projeto. |

O TikTok continua do jeito "1 clique": o programa copia a legenda e abre a página de upload
(a API do TikTok só posta como privado sem uma auditoria deles).
