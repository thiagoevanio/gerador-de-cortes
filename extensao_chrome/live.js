// Cortes 9:16 — painel flutuante nas lives da Twitch e da Kick.
//  • abriu a live → o programa já começa a gravar (o lance não se perde)
//  • lê o chat da página: gráfico do movimento, % de risada, palavras do momento e alerta quando "explode"
//  • ✂ CORTAR com 30s / 60s / 90s, ou ⏱ marcar início e cortar até agora (Alt+C / Alt+M)
//  • aba Momentos: o que o programa detectou sozinho (aprovar/descartar) e os cortes desta live
//  • aba Bot: assistente que analisa o chat; com IA ligada no programa, responde de verdade e sugere
//    cortes/títulos (só como botões: nada acontece sem o seu clique)
(() => {
  if (window.__c916) return;
  window.__c916 = true;
  const UI = window.C916UI;

  const LOC = window.__c916_local || location;          // (usado só nos testes)
  const PLAT = LOC.hostname.includes("kick.com") ? "kick" : "twitch";
  const NAO_CANAL = new Set(["", "directory", "videos", "settings", "subscriptions", "inventory", "wallet",
    "drops", "search", "downloads", "turbo", "p", "jobs", "store", "prime", "friends", "following",
    "categories", "browse", "video", "clips", "dashboard", "signup", "login", "moderator", "popout"]);
  const RISADA = /(k{3,}|kekw|lul|omegalul|icant|lmao|haha|rsrs|\?{2,}|!{3,}|caralho|meu deus|nooo|pog|wtf|a{4,}|😂|🤣|💀)/i;
  const PARADAS = new Set(("a o e é de da do das dos que pra pro para com um uma uns umas no na nos nas em se eu tu ele ela " +
    "isso esse essa este esta ta tá to tô vc voce você mas mais muito nao não sim ja já so só the and is to of it in mano " +
    "cara kk kkk né ne aí ai ou como foi vai ser tem q oq o que lá la me te").split(" "));

  let canal = null, duracao = 60, marca = null, ativo = true, cfg = {};
  let ajusteSync = 0, diferencaRelogio = 0;
  let ultimoAlerta = 0, notaTimer = null, cortando = false, ultimoAutoIa = 0;
  const porSegundo = new Map();          // segundo → pontos do chat (risada vale 2)
  const msgsPorSegundo = new Map();      // segundo → mensagens
  const risadaPorSegundo = new Map();    // segundo → mensagens com risada
  const recentes = [];                   // últimas mensagens (pro contexto da IA)
  let pendentesKick = [];
  let observando = null, inicioObservacao = 0;
  let servidorDetecta = false;          // o programa está medindo o calor desta live (tempo real)
  let momentosVistos = new Set(), ultimoStatus = null, meusCortes = [];

  const api = UI.api;

  function canalAtual() {
    const partes = LOC.pathname.split("/").filter(Boolean).map((p) => p.toLowerCase());
    let c = partes[0] || "";
    if (c === "popout" && partes[1]) c = partes[1];             // twitch.tv/popout/canal/chat
    else if (partes.length > 1 && partes[1] !== "chat") return null;  // ex: /canal/videos
    return /^[a-z0-9_]{2,30}$/.test(c) && !NAO_CANAL.has(c) ? c : null;
  }

  // ---------- interface ----------
  const painel = UI.criarPainel({
    subtitulo: PLAT === "kick" ? "Kick" : "Twitch", chave: `painel:${PLAT}`,
    abas: [{ id: "cortar", rotulo: "Cortar", icone: "tesoura" }, { id: "momentos", rotulo: "Momentos", icone: "raio" },
           { id: "bot", rotulo: "Bot", icone: "bot" }],
  });
  const abaCortar = painel.aba("cortar"), abaMomentos = painel.aba("momentos");
  abaCortar.innerHTML = `
    <div class="sec">
      <div class="cartao">
        <div class="linha"><span class="pilula estado"><i></i><span>verificando…</span></span><div class="esp"></div>
          <span class="dica fila"></span></div>
        <div class="termo-box" hidden style="margin-top:9px" title="Calor da live: quando enche, o programa corta sozinho">
          <div class="linha" style="justify-content:space-between;margin-bottom:5px"><span class="dica">🌡 Calor da live</span>
            <b class="termo-txt" style="font-size:12px">0%</b></div>
          <div class="termo"><div></div></div>
        </div>
      </div>
      <div class="rot">Chat agora</div>
      <div class="cartao">
        <div class="pulso" title="Mensagens a cada 10 segundos (últimos 5 minutos)"></div>
        <div class="nums">
          <div><b class="n-min">–</b><span>msg/min</span></div>
          <div><b class="n-x">–</b><span>vs. normal</span></div>
          <div><b class="n-ris">–</b><span>risada</span></div>
        </div>
        <div class="tags"></div>
      </div>
      <div class="rot">Duração do corte</div>
      <div class="seg dur">
        <button data-s="30">30s</button><button data-s="60">60s</button><button data-s="90">90s</button>
        <button class="marca" title="Marca o começo do lance (Alt+M). Depois clique em CORTAR.">⏱ marcar</button>
      </div>
      <div style="margin-top:10px"><button class="grande cortar" title="Corta o que acabou de acontecer">✂ CORTAR <kbd>Alt+C</kbd></button></div>
      <div class="nota" hidden style="margin-top:8px">
        <div class="linha"><input type="text" maxlength="200" placeholder="O que aconteceu? (opcional, Enter)">
          <span class="dica seg-nota" style="width:20px;text-align:right">20</span></div>
        <div class="dica" style="margin-top:4px">A IA usa isso pra escrever a pergunta da faixa.</div>
      </div>
      <div class="linha" style="margin-top:10px;justify-content:space-between">
        <button class="link sync" title="Ajuste adicional em segundos: positivo avança o corte; negativo recua">Sincronização: 0s</button>
        <span class="dica">Alt+M marca · Alt+C corta</span>
      </div>
    </div>`;
  abaMomentos.innerHTML = `
    <div class="sec">
      <div class="rot">Detectados pelo programa</div><div class="lista-mom"></div>
      <div class="rot">Seus cortes nesta live</div><div class="lista-meus"></div>
    </div>`;
  const $ = (s) => abaCortar.querySelector(s);
  const mensagem = (texto, tipo = "") => painel.rodape(texto, tipo);
  for (let i = 0; i < 30; i++) $(".pulso").appendChild(document.createElement("span"));

  function desenharDuracao() {
    abaCortar.querySelectorAll(".dur button[data-s]").forEach((b) => b.classList.toggle("on", +b.dataset.s === duracao && !marca));
    $(".marca").classList.toggle("on", !!marca);
    $(".marca").textContent = marca ? `⏱ ${Math.round((Date.now() - marca) / 1000)}s` : "⏱ marcar";
  }
  abaCortar.querySelectorAll(".dur button[data-s]").forEach((b) => (b.onclick = () => {
    duracao = +b.dataset.s; marca = null; desenharDuracao(); UI.guardar.gravar("duracao", duracao);
  }));
  const alternarMarca = () => { marca = marca ? null : Date.now(); desenharDuracao(); };
  $(".marca").onclick = alternarMarca;
  $(".cortar").onclick = () => cortar("botao");
  UI.guardar.ler("duracao", 60).then((d) => { duracao = d; desenharDuracao(); });

  document.addEventListener("keydown", (e) => {
    if (!e.altKey || !ativo || !canal) return;
    const k = e.key.toLowerCase();
    if (k === "c") { e.preventDefault(); cortar("atalho"); }
    if (k === "m") { e.preventDefault(); alternarMarca(); }
  });

  $(".sync").onclick = () => {
    const texto = window.prompt("Ajuste adicional em segundos (-60 a 60). Positivo avança; negativo recua.", String(ajusteSync));
    if (texto === null) return;
    const valor = Number(texto.replace(",", "."));
    if (!Number.isFinite(valor) || Math.abs(valor) > 60) return mensagem("Use um ajuste entre -60 e 60 segundos.", "erro");
    ajusteSync = valor; $(".sync").textContent = `Sincronização: ${valor}s`;
    UI.guardar.gravar(`sync:${PLAT}:${canal}`, valor);
  };
  function hashDoPlayer(player) {
    try {
      const c = document.createElement("canvas"); c.width = 9; c.height = 8;
      const ctx = c.getContext("2d", {willReadFrequently:true}); ctx.drawImage(player,0,0,9,8);
      const rgba = ctx.getImageData(0,0,9,8).data;
      const cinza = Array.from({length:72}, (_,i)=>rgba[i*4]*.299+rgba[i*4+1]*.587+rgba[i*4+2]*.114);
      let bits = 0n;
      for(let y=0;y<8;y++) for(let x=0;x<8;x++) bits=(bits<<1n)|BigInt(cinza[y*9+x]>cinza[y*9+x+1]);
      return bits.toString(16).padStart(16,"0");
    } catch (_) { return ""; }
  }

  // ---------- cortar ----------
  function chatRecente(segundos = 25) {
    const limite = Date.now() / 1000 - segundos;
    return recentes.filter((m) => m.t >= limite).slice(-30).map((m) => m.m).join(" | ").slice(0, 700);
  }

  async function cortar(origem, pedido = null) {
    if (cortando) return false;
    if (!canal) { mensagem("Abra a live de um canal primeiro.", "erro"); return false; }
    cortando = true;
    $(".cortar").disabled = true;
    try {
      let antes, depois;
      if (pedido) {                               // o bot sugeriu (e você clicou)
        antes = pedido.antes; depois = pedido.depois;
      } else if (marca) {
        antes = Math.min(180, (Date.now() - marca) / 1000 + 2); depois = 6;
      } else if (origem === "alerta") {          // o chat reage DEPOIS do lance: pega mais pra trás
        antes = duracao - 5; depois = 5;
      } else {
        antes = duracao - 10; depois = 10;
      }
      marca = null; desenharDuracao();
      mensagem("✂ pedindo o corte…");
      const player = document.querySelector("video");
      let atraso = 0;
      if (player && player.seekable.length) atraso = Math.max(0, player.seekable.end(player.seekable.length - 1) - player.currentTime);
      if (atraso > 180) { mensagem("O player está mais de 3 minutos atrasado. Volte para perto do ao vivo.", "erro"); return false; }
      const capturado_em = Date.now() / 1000 + diferencaRelogio;
      const r = await api("cortar", { frame_hash: player ? hashDoPlayer(player) : "", ajuste_sync: ajusteSync, capturado_em,
        atraso: atraso.toFixed(2), canal, plat: PLAT, antes: antes.toFixed(0), depois: depois.toFixed(0), chat: chatRecente() });
      mensagem(r.msg || "", r.ok ? "ok" : "erro");
      if (r.ok) {
        meusCortes.unshift({ hora: new Date().toTimeString().slice(0, 5), seg: Math.round(antes + depois), origem, msg: r.msg || "" });
        desenharMeus();
      }
      atualizarStatus();
      if (r.ok && r.id) abrirNota(r.id);
      return !!r.ok;
    } finally { cortando = false; $(".cortar").disabled = false; }
  }

  function abrirNota(id) {
    const box = $(".nota"), input = box.querySelector("input"), seg = box.querySelector(".seg-nota");
    painel.selecionar("cortar");
    box.hidden = false; input.value = ""; input.focus();
    let resta = 20;
    seg.textContent = resta;
    clearInterval(notaTimer);
    notaTimer = setInterval(() => {
      resta -= 1; seg.textContent = resta;
      if (resta <= 0) { clearInterval(notaTimer); box.hidden = true; }
    }, 1000);
    input.onkeydown = async (e) => {
      if (e.key === "Escape") { clearInterval(notaTimer); box.hidden = true; }
      if (e.key !== "Enter" || !input.value.trim()) return;
      clearInterval(notaTimer); box.hidden = true;
      const r = await api("nota", { id, texto: input.value.trim() });
      mensagem(r.msg || "", r.ok ? "ok" : "erro");
    };
  }

  // ---------- status (gravando? fila? momentos) ----------
  function tempo(seg) {
    seg = Math.max(0, Math.floor(seg));
    const h = Math.floor(seg / 3600), m = Math.floor((seg % 3600) / 60);
    return h ? `${h}h${String(m).padStart(2, "0")}` : `${m} min`;
  }

  async function atualizarStatus() {
    if (!canal || !ativo) return;
    const inicioRequisicao = Date.now();
    const s = await api("status");
    if (s.agora) diferencaRelogio = s.agora - (inicioRequisicao + Date.now()) / 2000;
    const est = $(".estado");
    if (s.offline) {
      painel.status("programa desligado", "off");
      est.className = "pilula estado off"; est.querySelector("span").textContent = "Abra o programa e ligue o monitor";
      $(".fila").textContent = ""; servidorDetecta = false; $(".termo-box").hidden = true;
      bot.atualizarIa(null); ultimoStatus = null;
      return;
    }
    ultimoStatus = s;
    bot.atualizarIa(s.ia);
    const chave = PLAT === "twitch" ? canal : `${PLAT}:${canal}`;
    const live = s.lives && s.lives[chave];
    $(".fila").textContent = s.fila ? `${s.fila} na fila` : "";
    if (live) {
      painel.status(`gravando · ${tempo(Date.now() / 1000 - live.desde)}`, "rec");
      est.className = "pilula estado rec";
      est.querySelector("span").textContent = `Gravando há ${tempo(Date.now() / 1000 - live.desde)} · ${live.cortes} corte(s)`;
      servidorDetecta = typeof live.calor === "number";
      desenharTermometro(live);
      desenharMomentos(live.momentos || []);
    } else {
      painel.status("conectado", "ok");
      est.className = "pilula estado"; est.querySelector("span").textContent = "Não está gravando";
      servidorDetecta = false; $(".termo-box").hidden = true;
      desenharMomentos([]);
    }
  }

  function desenharTermometro(live) {
    $(".termo-box").hidden = false;
    const pct = Math.max(0, Math.min(100, live.calor || 0));
    const fogo = $(".termo div");
    fogo.style.width = pct + "%";
    fogo.style.background = pct >= 100 ? "#ff3030" : pct >= 70 ? "#ff8a00" : pct >= 40 ? "#ffd400" : "#3ddc84";
    const sens = { baixa: " · sens. baixa", media: " · sens. média", alta: " · sens. alta" }[live.sensibilidade] || "";
    $(".termo-txt").textContent = `${pct}%${pct >= 100 ? " 🔥" : ""}${sens}`;
  }

  const ROTULO = { "na fila": "✂ na fila", aguardando: "⏳ aprovar?", pronto: "✅ pronto", descartado: "❌ descartado",
                   expirou: "⌛ expirou", "nota baixa": "🗑 nota baixa", erro: "❌ falhou", "tentando novamente": "⟳ tentando de novo", limite: "limite da live" };

  function desenharMomentos(lista) {
    const box = abaMomentos.querySelector(".lista-mom");
    box.innerHTML = "";
    if (!lista.length) box.appendChild(UI.el("div", { class: "vazio" }, "Nada detectado ainda. Quando o calor da live encher, aparece aqui."));
    const novos = [];
    for (const m of lista.slice(-6).reverse()) {
      if (!momentosVistos.has(m.id)) { momentosVistos.add(m.id); novos.push(m); }
      const pend = m.status === "aguardando", pode = pend || m.status === "na fila";
      const linha = UI.el("div", { class: "item" + (pend ? " pendente" : "") },
        `<div class="txt"><b>🤖 ${UI.esc(m.hora.slice(0, 5))}</b> · nota ${UI.esc(m.nota ?? "–")}
          <small>${UI.esc((m.motivos || []).slice(0, 3).join(" + "))}</small><small>${UI.esc(ROTULO[m.status] || m.status || "")}</small></div>`);
      if (pend) linha.appendChild(UI.el("button", { title: "Cortar esse momento", onclick: async () => { const r = await api("momento", { id: m.id, acao: "aprovar" }); mensagem(r.msg, "ok"); atualizarStatus(); } }, "✅"));
      if (pode) linha.appendChild(UI.el("button", { title: "Descartar esse momento", onclick: async () => { const r = await api("momento", { id: m.id, acao: "descartar" }); mensagem(r.msg); atualizarStatus(); } }, "❌"));
      box.appendChild(linha);
    }
    if (novos.length && momentosVistos.size > novos.length) {   // não avisa os que já existiam ao abrir
      painel.piscar(true); setTimeout(() => painel.piscar(false), 6000);
      painel.badge("momentos", novos.length);
      const m = novos[0];
      if (cfg.botAuto) bot.dizer({ texto: `🤖 O programa achou um momento às ${m.hora.slice(0, 5)} (nota ${m.nota ?? "–"}): ${(m.motivos || []).slice(0, 3).join(", ")}.` +
        (m.status === "aguardando" ? " Aprove na aba Momentos." : ""), ia: "programa" });
    }
  }

  function desenharMeus() {
    const box = abaMomentos.querySelector(".lista-meus");
    box.innerHTML = "";
    if (!meusCortes.length) return box.appendChild(UI.el("div", { class: "vazio" }, "Você ainda não cortou nada nesta live."));
    for (const c of meusCortes.slice(0, 10)) {
      box.appendChild(UI.el("div", { class: "item" }, `<div class="txt"><b>✂ ${UI.esc(c.hora)}</b> · ${c.seg}s
        ${c.origem === "bot" ? "· sugerido pelo bot" : ""}<small>${UI.esc(c.msg)}</small></div>`));
    }
  }
  desenharMeus();

  function contarEspectadores() {
    const sel = PLAT === "twitch"
      ? ['[data-a-target="animated-channel-viewers-count"]', '[data-a-target="channel-viewers-count"]',
         '.channel-info-content [aria-label*="spectador"]', '.channel-info-content [aria-label*="viewer"]']
      : ['[data-testid="viewer-count"]', '[class*="viewer-count"]', '[class*="viewers"]'];
    let el = null;
    for (const q of sel) { el = document.querySelector(q); if (el) break; }
    const txt = (el ? el.innerText || el.getAttribute("aria-label") || "" : "").toLowerCase().replace(/\s/g, "");
    const m = txt.match(/([\d.,]+)(mil|k|mi|m)?/);
    if (!m) return 0;
    let n = parseFloat(m[1].replace(/\.(?=\d{3}\b)/g, "").replace(",", "."));
    if (m[2] === "mil" || m[2] === "k") n *= 1000;
    if (m[2] === "mi" || m[2] === "m") n *= 1e6;
    return Math.round(n) || 0;
  }

  // abriu a live → pede pra gravar; e repete a cada 30 s (sinal de que a aba está aberta)
  async function sinalGravar(primeira) {
    if (!canal || !ativo) return false;
    const r = await api("gravar", { canal, plat: PLAT, auto: "1", espectadores: contarEspectadores() });
    if (primeira && r.msg && !r.offline) mensagem(r.msg, r.ok ? "ok" : "");
    if (primeira && r.offline) mensagem(r.msg, "erro");
    atualizarStatus();
    return !!r.ok;
  }

  // ---------- leitura do chat ----------
  const SELETORES_CHAT = PLAT === "twitch"
    ? ['[data-test-selector="chat-scrollable-area__message-container"]', ".chat-scrollable-area__message-container",
       ".seventv-chat-list", '[role="log"]']
    : ["#chatroom-messages", '[data-testid="chat-messages"]', "#chat-messages", '[class*="chatroom-messages"]'];

  function textoDaMensagem(el) {
    const corpo = el.querySelector('[data-a-target="chat-line-message-body"], .message, .chat-entry-content') || el;
    let t = (corpo.innerText || "").trim();
    el.querySelectorAll("img[alt]").forEach((img) => (t += " " + img.alt));
    return t.slice(0, 300);
  }

  const somar = (mapa, k, n = 1) => mapa.set(k, (mapa.get(k) || 0) + n);
  function novaMensagem(el) {
    const t = textoDaMensagem(el);
    if (!t) return;
    const agora = Date.now() / 1000, seg = Math.floor(agora), ri = RISADA.test(t);
    somar(porSegundo, seg, ri ? 2 : 1);
    somar(msgsPorSegundo, seg);
    if (ri) somar(risadaPorSegundo, seg);
    recentes.push({ t: agora, m: t });
    if (recentes.length > 400) recentes.splice(0, 100);
    if (PLAT === "kick") {
      const autor = el.querySelector('[data-username], [data-testid="chat-message-username"], .chat-entry-username');
      const u = autor ? (autor.getAttribute("data-username") || autor.textContent || "").trim() : "";
      pendentesKick.push({ t: agora, u, m: t });
      if (pendentesKick.length > 2000) pendentesKick.splice(0, pendentesKick.length - 2000);
    }
  }

  function observarChat() {
    let alvo = null;
    for (const s of SELETORES_CHAT) { alvo = document.querySelector(s); if (alvo) break; }
    if (!alvo || alvo === observando) return;
    if (observando && observando._obs) observando._obs.disconnect();
    const obs = new MutationObserver((lista) => {
      for (const m of lista) m.addedNodes.forEach((n) => { if (n.nodeType === 1) novaMensagem(n); });
    });
    obs.observe(alvo, { childList: true });
    alvo._obs = obs;
    observando = alvo;
    inicioObservacao = Date.now();
  }

  const soma = (mapa, a, b) => { let t = 0; for (let s = a; s < b; s++) t += mapa.get(s) || 0; return t; };

  // números do chat que o painel mostra e o bot usa
  function estatisticas() {
    const agora = Math.floor(Date.now() / 1000);
    const msgMin = soma(msgsPorSegundo, agora - 60, agora);
    const janelas = [];
    for (let s = agora - 600; s < agora - 60; s += 15) janelas.push(soma(msgsPorSegundo, s, s + 60));
    const comDados = janelas.filter((n) => n > 0).sort((a, b) => a - b);
    const normal = comDados.length >= 4 ? comDados[Math.floor(comDados.length / 2)] : 0;
    const contagem = new Map();
    for (const m of recentes) {
      if (m.t < agora - 60) continue;
      const vistas = new Set();
      for (let w of m.m.toLowerCase().split(/[^\p{L}\p{N}_]+/u)) {
        if (/^k{3,}$/.test(w)) w = "kkkk";
        if (w.length < 3 || PARADAS.has(w) || /^\d+$/.test(w) || vistas.has(w)) continue;
        vistas.add(w); contagem.set(w, (contagem.get(w) || 0) + 1);
      }
    }
    const top = [...contagem.entries()].filter(([, n]) => n >= 2).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([w]) => w);
    const barras = [];
    for (let i = 29; i >= 0; i--) barras.push(soma(msgsPorSegundo, agora - (i + 1) * 10, agora - i * 10));
    return { msgMin, normal, x: normal ? msgMin / normal : 0, risada: msgMin ? soma(risadaPorSegundo, agora - 60, agora) / msgMin : 0,
             top, barras, lendo: !!observando, minutosLendo: observando ? (Date.now() - inicioObservacao) / 60000 : 0 };
  }

  function desenharChat() {
    const e = estatisticas();
    const max = Math.max(4, ...e.barras), media = e.normal / 6;
    $(".pulso").querySelectorAll("span").forEach((s, i) => {
      const v = e.barras[i];
      s.style.height = Math.max(2, (v / max) * 38) + "px";
      s.className = media && v >= media * 2.5 ? "quente" : media && v >= media * 1.6 ? "morno" : "";
    });
    $(".n-min").textContent = e.lendo ? String(e.msgMin) : "–";
    $(".n-x").textContent = e.normal ? `${e.x.toFixed(1).replace(".", ",")}x` : "–";
    $(".n-x").style.color = e.x >= 2.5 ? "#ff4d55" : e.x >= 1.6 ? "#ff9f1a" : "";
    $(".n-ris").textContent = e.msgMin ? `${Math.round(e.risada * 100)}%` : "–";
    $(".tags").innerHTML = e.top.map((w) => `<span>${UI.esc(w)}</span>`).join("") ||
      `<span class="dica" style="background:none;padding:0">${e.lendo ? "Esperando o chat falar…" : "Abra o chat da live pra eu ler"}</span>`;
  }

  // pico = os últimos 15s têm pelo menos 2,5x o movimento normal do chat
  function verificarPico() {
    const agora = Math.floor(Date.now() / 1000);
    for (const mapa of [porSegundo, msgsPorSegundo, risadaPorSegundo]) for (const k of mapa.keys()) if (k < agora - 660) mapa.delete(k);
    if (servidorDetecta || !ativo) return;    // o programa já está medindo (e cortando) em tempo real
    if (!observando || Date.now() - inicioObservacao < 90000) return;
    const janela = soma(porSegundo, agora - 15, agora);
    const normais = [];
    for (let s = agora - 300; s < agora - 15; s += 5) normais.push(soma(porSegundo, s, s + 15));
    normais.sort((a, b) => a - b);
    const mediana = normais.length ? normais[Math.floor(normais.length / 2)] : 0;
    if (janela >= Math.max(mediana * 2.5, 12) && Date.now() - ultimoAlerta > 90000) {
      ultimoAlerta = Date.now();
      mostrarAlerta();
    }
  }

  function mostrarAlerta() {
    painel.alerta("🔥 O CHAT EXPLODIU!", [{ rotulo: "✂ CORTAR", classe: "sim", acao: () => cortar("alerta") }, { rotulo: "✕", classe: "nao" }]);
    if (!cfg.botAuto) return;
    const e = estatisticas();
    bot.dizer({ texto: `🔥 O chat explodiu: ${e.x ? e.x.toFixed(1).replace(".", ",") + "x o normal" : "pico forte"}` +
      (e.msgMin ? `, ${Math.round(e.risada * 100)}% de risada` : "") + (e.top.length ? `. Falam de: ${e.top.slice(0, 4).join(", ")}.` : "."),
      acoes: [{ tipo: "cortar", antes: duracao - 5, depois: 5, rotulo: `✂ Cortar ${duracao}s` }], ia: "modo básico" });
    if (cfg.botIa && bot.iaPronta() && Date.now() - ultimoAutoIa > 180000) {
      ultimoAutoIa = Date.now();
      setTimeout(() => bot.perguntar("analisar", "", "", { silencioso: true }), 4000);   // espera o chat reagir
    }
  }

  async function enviarChatKick() {
    if (PLAT !== "kick" || !canal || !pendentesKick.length || !ativo) return;
    const msgs = pendentesKick.splice(0, 500);
    const origem = canal;
    const r = await api("chat", {}, { canal: origem, plat: PLAT, msgs });
    if (!r.ok && canal === origem) pendentesKick = msgs.concat(pendentesKick).slice(-2000);
  }

  // ---------- bot ----------
  function respostaLocal(tipo) {
    const e = estatisticas();
    const x = e.x ? `${e.x.toFixed(1).replace(".", ",")}x o normal` : "sem base ainda (preciso de uns minutos lendo o chat)";
    const ris = `${Math.round(e.risada * 100)}% de risada`;
    const temas = e.top.length ? ` Mais falado: ${e.top.slice(0, 5).join(", ")}.` : "";
    if (!e.lendo) return { texto: "Ainda não consigo ler o chat desta página. Deixe o chat da live aberto ao lado do vídeo." };
    if (tipo === "analisar") {
      const nota = Math.round(Math.min(10, (e.x || 1) * 2.5 + e.risada * 4) * 10) / 10;
      const vale = e.x >= 2.5 || (e.x >= 1.6 && e.risada >= 0.3);
      return { texto: `${vale ? "Parece que sim!" : "Por enquanto não."} Chat com ${e.msgMin} msg/min (${x}), ${ris}.${temas}`, nota,
               acoes: vale ? [{ tipo: "cortar", antes: duracao - 10, depois: 10, rotulo: `✂ Cortar ${duracao}s` }] : [{ tipo: "marcar", rotulo: "⏱ Marcar início" }] };
    }
    if (tipo === "titulo") return { texto: `Pra sugerir títulos eu preciso de uma IA ligada no programa.${temas}` };
    return { texto: `Último minuto: ${e.msgMin} mensagens (${x}), ${ris}.${temas}` };
  }

  const bot = UI.criarBot({
    painel, abaId: "bot",
    chave: () => `${PLAT}:${canal || "-"}`,
    sugestoes: [{ tipo: "analisar", rotulo: "🔥 Vale cortar agora?" }, { tipo: "resumo", rotulo: "📝 O que rolou?" },
                { tipo: "titulo", rotulo: "✍ Sugere um título" }],
    contexto: () => {
      const e = estatisticas(), limite = Date.now() / 1000 - 150;
      const chave = PLAT === "twitch" ? canal : `${PLAT}:${canal}`;
      const live = ultimoStatus && ultimoStatus.lives && ultimoStatus.lives[chave];
      return {
        plat: PLAT, canal, titulo: (live && live.titulo) || document.title.replace(/ - Twitch$| \| Kick$/i, ""),
        chat: recentes.filter((m) => m.t >= limite).slice(-120).map((m) => m.m),
        stats: { "mensagens no último minuto": e.msgMin, "normal por minuto": e.normal || "sem base",
                 "risada": `${Math.round(e.risada * 100)}%`, "palavras do momento": e.top.join(", ") || "-",
                 ...(live ? { "calor da live": `${live.calor ?? "-"}%` } : {}) },
        momentos: ((live && live.momentos) || []).map((m) => `${m.hora} nota ${m.nota}: ${(m.motivos || []).join(", ")}`),
      };
    },
    local: respostaLocal,
    executar: async (a) => {
      if (a.tipo === "cortar") return await cortar("bot", { antes: a.antes, depois: a.depois });
      if (a.tipo === "marcar") { marca = Date.now(); desenharDuracao(); painel.selecionar("cortar"); mensagem("⏱ Início marcado. Clique em CORTAR quando o lance acabar.", "ok"); return true; }
      if (a.tipo === "gravar") return await sinalGravar(true);
      return false;
    },
  });

  // ---------- ciclo ----------
  function verificarPagina() {
    const c = ativo ? canalAtual() : null;
    if (!c) { if (observando && observando._obs) observando._obs.disconnect(); observando = null; painel.remover(); canal = null; return; }
    painel.mostrar();
    if (c !== canal) {
      canal = c;
      painel.subtitulo(`${PLAT === "kick" ? "Kick" : "Twitch"} · ${c}`);
      ajusteSync = 0;
      const chaveSync = `sync:${PLAT}:${canal}`;
      UI.guardar.ler(chaveSync, 0).then((v) => { if (canal === c) { ajusteSync = Number(v) || 0; $(".sync").textContent = `Sincronização: ${ajusteSync}s`; } });
      if (observando && observando._obs) observando._obs.disconnect();
      for (const mapa of [porSegundo, msgsPorSegundo, risadaPorSegundo]) mapa.clear();
      recentes.length = 0; pendentesKick = []; observando = null; marca = null;
      momentosVistos = new Set(); servidorDetecta = false; meusCortes = []; desenharMeus();
      painel.semAlerta(); desenharDuracao(); bot.recarregar();
      sinalGravar(true);
    }
    observarChat();
  }

  if (window.__c916_local) window.__c916_t = { verificarPico, novaMensagem, porSegundo, estatisticas, respostaLocal, painel, bot };  // testes

  UI.config().then((c) => { cfg = c; ativo = c[PLAT] !== false; verificarPagina(); });
  UI.aoMudarConfig((c) => { cfg = c; ativo = c[PLAT] !== false; verificarPagina(); });
  setInterval(verificarPagina, 2000);
  setInterval(verificarPico, 2000);
  setInterval(() => { if (canal) { desenharDuracao(); desenharChat(); } }, 1000);
  setInterval(atualizarStatus, 5000);
  setInterval(() => sinalGravar(false), 30000);
  setInterval(enviarChatKick, 5000);
})();
