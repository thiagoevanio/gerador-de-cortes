// Cortes 9:16 — painel flutuante nas lives da Twitch e da Kick.
//  • abriu a live → o programa já começa a gravar (o lance não se perde)
//  • lê o chat da página e avisa quando ele "explode" (🔥 cortar?)
//  • ✂ CORTAR com 30s / 60s / 90s, ou ⏱ marcar início e cortar até agora
//  • caixinha opcional pra contar o que aconteceu (a IA usa pra criar a pergunta)
//  • mostra se está gravando e quantos cortes estão na fila
(() => {
  if (window.__c916) return;
  window.__c916 = true;

  const LOC = window.__c916_local || location;          // (usado só nos testes)
  const PLAT = LOC.hostname.includes("kick.com") ? "kick" : "twitch";
  const NAO_CANAL = new Set(["", "directory", "videos", "settings", "subscriptions", "inventory", "wallet",
    "drops", "search", "downloads", "turbo", "p", "jobs", "store", "prime", "friends", "following",
    "categories", "browse", "video", "clips", "dashboard", "signup", "login", "moderator", "popout"]);
  const RISADA = /(k{3,}|kekw|lul|omegalul|icant|lmao|haha|rsrs|\?{2,}|!{3,}|caralho|meu deus|nooo|pog|wtf|a{4,}|😂|🤣|💀)/i;

  let canal = null, duracao = 60, marca = null, minimizado = false;
  let ajusteSync = 0, diferencaRelogio = 0;
  let ultimoAlerta = 0, alertaTimer = null, notaTimer = null, cortando = false;
  const porSegundo = new Map();          // segundo → pontos do chat
  const recentes = [];                   // últimas mensagens (pro contexto da IA)
  let pendentesKick = [];
  let observando = null, inicioObservacao = 0;
  let servidorDetecta = false;          // o programa está medindo o calor desta live (tempo real)
  let momentosVistos = new Set();

  // ---------- comunicação com o programa ----------
  function api(acao, params = {}, corpo = null) {
    return new Promise((ok) => {
      try {
        chrome.runtime.sendMessage({ tipo: "api", acao, params, corpo }, (r) => {
          if (chrome.runtime.lastError || !r) return ok({ ok: false, offline: true, msg: "Sem conexão com o programa." });
          ok(r);
        });
      } catch (e) { ok({ ok: false, offline: true, msg: "Recarregue a página (a extensão foi atualizada)." }); }
    });
  }

  function canalAtual() {
    const partes = LOC.pathname.split("/").filter(Boolean).map((p) => p.toLowerCase());
    let c = partes[0] || "";
    if (c === "popout" && partes[1]) c = partes[1];             // twitch.tv/popout/canal/chat
    else if (partes.length > 1 && partes[1] !== "chat") return null;  // ex: /canal/videos
    return /^[a-z0-9_]{2,30}$/.test(c) && !NAO_CANAL.has(c) ? c : null;
  }

  // ---------- interface ----------
  const caixa = document.createElement("div");
  caixa.id = "c916";
  caixa.innerHTML = `
    <div class="c916-alerta" hidden>
      <span>🔥 O CHAT EXPLODIU!</span>
      <button class="c916-sim">✂ CORTAR</button>
      <button class="c916-nao" title="Ignorar">✕</button>
    </div>
    <div class="c916-topo">
      <span class="c916-status">● conectando...</span>
      <button class="c916-min" title="Minimizar">–</button>
    </div>
    <div class="c916-termo" hidden title="Calor da live: quando enche, o programa corta sozinho">
      <div class="c916-termo-barra"><div class="c916-termo-fogo"></div></div>
      <span class="c916-termo-txt">🌡 0%</span>
    </div>
    <div class="c916-momentos" hidden></div>
    <div class="c916-corpo"><button class="c916-sync" title="Ajuste adicional em segundos: positivo avança o corte; negativo recua">Sincronização: 0s</button>
      <div class="c916-linha">
        <button class="c916-dur" data-s="30">30s</button>
        <button class="c916-dur" data-s="60">60s</button>
        <button class="c916-dur" data-s="90">90s</button>
        <button class="c916-marcar" title="Marca o começo do lance (Alt+M). Depois clique em CORTAR.">⏱ marcar</button>
      </div>
      <button class="c916-cortar" title="Corta o que acabou de acontecer (Alt+C)">✂ CORTAR</button>
      <div class="c916-nota" hidden>
        <input type="text" maxlength="200" placeholder="O que aconteceu? (opcional, Enter)">
        <span class="c916-seg">20</span>
      </div>
      <div class="c916-msg"></div>
    </div>`;
  const $ = (s) => caixa.querySelector(s);

  function mensagem(texto, tipo = "") {
    const m = $(".c916-msg");
    m.textContent = texto;
    m.className = "c916-msg " + tipo;
    clearTimeout(m._t);
    if (texto) m._t = setTimeout(() => (m.textContent = ""), 9000);
  }

  function desenharDuracao() {
    caixa.querySelectorAll(".c916-dur").forEach((b) => b.classList.toggle("ativo", +b.dataset.s === duracao && !marca));
    $(".c916-marcar").classList.toggle("ativo", !!marca);
    $(".c916-marcar").textContent = marca ? `⏱ ${Math.round((Date.now() - marca) / 1000)}s` : "⏱ marcar";
  }

  caixa.querySelectorAll(".c916-dur").forEach((b) => (b.onclick = () => {
    duracao = +b.dataset.s; marca = null; desenharDuracao();
    try { chrome.storage.local.set({ duracao }); } catch (e) {}
  }));
  $(".c916-marcar").onclick = () => { marca = marca ? null : Date.now(); desenharDuracao(); };
  $(".c916-cortar").onclick = () => cortar("botao");
  $(".c916-sim").onclick = () => { esconderAlerta(); cortar("alerta"); };
  $(".c916-nao").onclick = esconderAlerta;
  $(".c916-min").onclick = () => {
    minimizado = !minimizado;
    caixa.classList.toggle("mini", minimizado);
    $(".c916-min").textContent = minimizado ? "+" : "–";
  };
  try { chrome.storage.local.get(["duracao"], (r) => { if (r && r.duracao) { duracao = r.duracao; desenharDuracao(); } }); } catch (e) {}

  document.addEventListener("keydown", (e) => {
    if (!e.altKey) return;
    const k = e.key.toLowerCase();
    if (k === "c") { e.preventDefault(); cortar("atalho"); }
    if (k === "m") { e.preventDefault(); marca = marca ? null : Date.now(); desenharDuracao(); }
  });

  $(".c916-sync").onclick = () => {
    const texto = window.prompt("Ajuste adicional em segundos (-60 a 60). Positivo avança; negativo recua.", String(ajusteSync));
    if (texto === null) return;
    const valor = Number(texto.replace(",", "."));
    if (!Number.isFinite(valor) || Math.abs(valor) > 60) return mensagem("Use um ajuste entre -60 e 60 segundos.", "erro");
    ajusteSync = valor; $(".c916-sync").textContent = `Sincronização: ${valor}s`;
    chrome.storage.local.set({ [`sync:${PLAT}:${canal}`]: valor });
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

  async function cortar(origem) {
    if (cortando) return;
    if (!canal) return mensagem("Abra a live de um canal primeiro.", "erro");
    cortando = true;
    $(".c916-cortar").disabled = true;
    try {
    let antes, depois;
    if (marca) {
      antes = Math.min(180, (Date.now() - marca) / 1000 + 2);
      depois = 6;
    } else if (origem === "alerta") {          // o chat reage DEPOIS do lance: pega mais pra trás
      antes = duracao - 5; depois = 5;
    } else {
      antes = duracao - 10; depois = 10;
    }
    marca = null; desenharDuracao();
    mensagem("✂ pedindo o corte...");
    const player = document.querySelector("video");
    let atraso = 0;
    if (player && player.seekable.length) atraso = Math.max(0, player.seekable.end(player.seekable.length - 1) - player.currentTime);
    if (atraso > 180) return mensagem("O player está mais de 3 minutos atrasado. Volte para perto do ao vivo.", "erro");
    const capturado_em = Date.now()/1000 + diferencaRelogio;
    const r = await api("cortar", { frame_hash: player ? hashDoPlayer(player) : "", ajuste_sync: ajusteSync, capturado_em, atraso: atraso.toFixed(2), canal, plat: PLAT, antes: antes.toFixed(0), depois: depois.toFixed(0), chat: chatRecente() });
    mensagem(r.msg || "", r.ok ? "ok" : "erro");
    atualizarStatus();
    if (r.ok && r.id) abrirNota(r.id);
    } finally { cortando = false; $(".c916-cortar").disabled = false; }
  }

  function abrirNota(id) {
    const box = $(".c916-nota"), input = box.querySelector("input"), seg = box.querySelector(".c916-seg");
    box.hidden = false; input.value = ""; input.focus();
    let resta = 20;
    seg.textContent = resta;
    clearInterval(notaTimer);
    notaTimer = setInterval(() => {
      resta -= 1; seg.textContent = resta;
      if (resta <= 0) { clearInterval(notaTimer); box.hidden = true; }
    }, 1000);
    input.onkeydown = async (e) => {
      e.stopPropagation();                       // não deixa a Twitch/Kick pegar as teclas
      if (e.key === "Escape") { clearInterval(notaTimer); box.hidden = true; }
      if (e.key !== "Enter" || !input.value.trim()) return;
      clearInterval(notaTimer); box.hidden = true;
      const r = await api("nota", { id, texto: input.value.trim() });
      mensagem(r.msg || "", r.ok ? "ok" : "erro");
    };
  }

  // ---------- status (gravando? fila?) ----------
  function tempo(seg) {
    seg = Math.max(0, Math.floor(seg));
    const h = Math.floor(seg / 3600), m = Math.floor((seg % 3600) / 60);
    return h ? `${h}h${String(m).padStart(2, "0")}` : `${m} min`;
  }

  async function atualizarStatus() {
    const inicioRequisicao = Date.now();
    const s = await api("status");
    if (s.agora) diferencaRelogio = s.agora - (inicioRequisicao + Date.now())/2000;
    const st = $(".c916-status");
    if (s.offline) {
      st.textContent = "⚠ programa desligado"; st.className = "c916-status off";
      servidorDetecta = false; $(".c916-termo").hidden = true; $(".c916-momentos").hidden = true;
      return;
    }
    const chave = PLAT === "twitch" ? canal : `${PLAT}:${canal}`;
    const live = s.lives && s.lives[chave];
    const fila = s.fila ? ` · ${s.fila} na fila` : "";
    if (live) {
      st.textContent = `🔴 gravando há ${tempo(Date.now() / 1000 - live.desde)} · ${live.cortes} corte(s)${fila}`;
      st.className = "c916-status rec";
      servidorDetecta = typeof live.calor === "number";
      desenharTermometro(live);
      desenharMomentos(live.momentos || []);
    } else {
      st.textContent = `⚪ não está gravando${fila}`;
      st.className = "c916-status";
      servidorDetecta = false;
      $(".c916-termo").hidden = true; $(".c916-momentos").hidden = true;
    }
  }

  function desenharTermometro(live) {
    const t = $(".c916-termo");
    t.hidden = false;
    const pct = Math.max(0, Math.min(100, live.calor || 0));
    const fogo = $(".c916-termo-fogo");
    fogo.style.width = pct + "%";
    fogo.style.background = pct >= 100 ? "#ff3030" : pct >= 70 ? "#ff8a00" : pct >= 40 ? "#ffd600" : "#4ade80";
    const sens = { baixa: "sens. baixa", media: "sens. média", alta: "sens. alta" }[live.sensibilidade] || "";
    $(".c916-termo-txt").textContent = `🌡 ${pct}%${pct >= 100 ? " 🔥" : ""}  ${sens}`;
  }

  const ROTULO = { "na fila": "✂ na fila", aguardando: "⏳ aprovar?", pronto: "✅ pronto", descartado: "❌ descartado",
                   expirou: "⌛ expirou", "nota baixa": "🗑 nota baixa", erro: "❌ falhou", "tentando novamente": "⟳ tentando novamente", limite: "limite da live" };

  function desenharMomentos(lista) {
    const box = $(".c916-momentos");
    if (!lista.length) { box.hidden = true; return; }
    box.hidden = false;
    let novo = false;
    box.innerHTML = "";
    for (const m of lista.slice(-3).reverse()) {
      if (!momentosVistos.has(m.id)) { momentosVistos.add(m.id); novo = true; }
      const linha = document.createElement("div");
      linha.className = "c916-mom " + (m.status === "aguardando" ? "pendente" : "");
      const pode = m.status === "aguardando" || m.status === "na fila";
      linha.innerHTML = `<div class="c916-mom-txt"><b>🤖 ${m.hora.slice(0, 5)}</b> ${m.motivos.slice(0, 2).join(" + ")}
        <span class="c916-mom-st">${ROTULO[m.status] || m.status}</span></div>
        ${m.status === "aguardando" ? '<button class="ok" title="Cortar esse momento">✅</button>' : ""}
        ${pode ? '<button class="no" title="Descartar esse momento">❌</button>' : ""}`;
      const ok = linha.querySelector(".ok"), no = linha.querySelector(".no");
      if (ok) ok.onclick = async () => { const r = await api("momento", { id: m.id, acao: "aprovar" }); mensagem(r.msg, "ok"); atualizarStatus(); };
      if (no) no.onclick = async () => { const r = await api("momento", { id: m.id, acao: "descartar" }); mensagem(r.msg, ""); atualizarStatus(); };
      box.appendChild(linha);
    }
    if (novo && momentosVistos.size > 0 && lista.length) {
      caixa.classList.add("pisca");
      setTimeout(() => caixa.classList.remove("pisca"), 6000);
    }
  }

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

  // abriu a live → pede pra gravar; e repete a cada minuto (sinal de que a aba está aberta)
  async function sinalGravar(primeira) {
    if (!canal) return;
    const r = await api("gravar", { canal, plat: PLAT, auto: "1", espectadores: contarEspectadores() });
    if (primeira && r.msg && !r.offline) mensagem(r.msg, r.ok ? "ok" : "");
    if (primeira && r.offline) mensagem(r.msg, "erro");
    atualizarStatus();
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

  function novaMensagem(el) {
    const t = textoDaMensagem(el);
    if (!t) return;
    const agora = Date.now() / 1000, seg = Math.floor(agora);
    porSegundo.set(seg, (porSegundo.get(seg) || 0) + (RISADA.test(t) ? 2 : 1));
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

  // pico = os últimos 15s têm pelo menos 2,5x o movimento normal do chat
  function verificarPico() {
    const agora = Math.floor(Date.now() / 1000);
    for (const k of porSegundo.keys()) if (k < agora - 600) porSegundo.delete(k);
    if (servidorDetecta) return;        // o programa já está medindo (e cortando) em tempo real
    if (!observando || Date.now() - inicioObservacao < 90000) return;
    const soma = (a, b) => { let t = 0; for (let s = a; s < b; s++) t += porSegundo.get(s) || 0; return t; };
    const janela = soma(agora - 15, agora);
    const normais = [];
    for (let s = agora - 300; s < agora - 15; s += 5) normais.push(soma(s, s + 15));
    normais.sort((a, b) => a - b);
    const mediana = normais.length ? normais[Math.floor(normais.length / 2)] : 0;
    if (janela >= Math.max(mediana * 2.5, 12) && Date.now() - ultimoAlerta > 90000) {
      ultimoAlerta = Date.now();
      mostrarAlerta();
    }
  }

  function mostrarAlerta() {
    const a = $(".c916-alerta");
    a.hidden = false;
    caixa.classList.add("pisca");
    clearTimeout(alertaTimer);
    alertaTimer = setTimeout(esconderAlerta, 20000);
  }

  function esconderAlerta() {
    $(".c916-alerta").hidden = true;
    caixa.classList.remove("pisca");
    clearTimeout(alertaTimer);
  }

  async function enviarChatKick() {
    if (PLAT !== "kick" || !canal || !pendentesKick.length) return;
    const msgs = pendentesKick.splice(0, 500);
    const origem = canal;
    const r = await api("chat", {}, { canal: origem, plat: PLAT, msgs });
    if (!r.ok && canal === origem) pendentesKick = msgs.concat(pendentesKick).slice(-2000);
  }

  // ---------- ciclo ----------
  function verificarPagina() {
    const c = canalAtual();
    if (!c) { if (observando && observando._obs) observando._obs.disconnect(); observando = null; caixa.remove(); canal = null; return; }
    if (!caixa.isConnected) document.body.appendChild(caixa);
    if (c !== canal) {
      canal = c;
      ajusteSync = 0;
      const chaveSync = `sync:${PLAT}:${canal}`;
      chrome.storage.local.get([chaveSync], (r)=>{ if(canal === c) { ajusteSync = Number(r[chaveSync]) || 0; $(".c916-sync").textContent = `Sincronização: ${ajusteSync}s`; } });
      if (observando && observando._obs) observando._obs.disconnect();
      porSegundo.clear(); recentes.length = 0; pendentesKick = []; observando = null; marca = null;
      momentosVistos = new Set(); servidorDetecta = false;
      esconderAlerta(); desenharDuracao();
      sinalGravar(true);
    }
    observarChat();
  }

  if (window.__c916_local) window.__c916_t = { verificarPico, novaMensagem, porSegundo };  // testes

  verificarPagina();
  setInterval(verificarPagina, 2000);
  setInterval(verificarPico, 2000);
  setInterval(() => { desenharDuracao(); }, 1000);
  setInterval(atualizarStatus, 5000);
  setInterval(() => sinalGravar(false), 30000);
  setInterval(enviarChatKick, 5000);
})();
