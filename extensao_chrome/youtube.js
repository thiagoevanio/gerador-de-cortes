// Cortes 9:16 — painel nos vídeos do YouTube.
//  • Cortar: marca início e fim no ponto atual (Alt+I / Alt+F) ou "últimos 30/60 s" e manda gerar (Alt+G)
//  • Momentos: 🤖 a IA acha e corta os melhores momentos sozinha (usa o gráfico de replays e os minutos
//    citados nos comentários como pistas) + a lista dos picos e dos minutos citados
//  • Bot: acha os melhores trechos, sugere título e responde perguntas (com IA ligada no programa);
//    as sugestões viram botões (ir até o ponto / marcar o trecho) — gerar continua sendo com você
(() => {
  if (window.__c916yt) return;
  window.__c916yt = true;
  const UI = window.C916UI;
  let inicio = null, fim = null, ativo = true, cfg = {}, ultimoLink = null, conectado = false;

  const painel = UI.criarPainel({
    subtitulo: "YouTube", chave: "painel:youtube",
    abas: [{ id: "cortar", rotulo: "Cortar", icone: "tesoura" }, { id: "momentos", rotulo: "Momentos", icone: "raio" },
           { id: "bot", rotulo: "Bot", icone: "bot" }],
  });
  const abaCortar = painel.aba("cortar"), abaMom = painel.aba("momentos");
  abaCortar.innerHTML = `
    <div class="sec">
      <div class="rot">Trecho do corte</div>
      <div class="cartao">
        <div class="linha" style="justify-content:space-between">
          <div><div class="dica">Início</div><div class="tempo t-ini" style="font-size:18px">--:--</div></div>
          <div style="text-align:center"><div class="dica">Duração</div><b class="t-dur" style="font-size:14px">–</b></div>
          <div style="text-align:right"><div class="dica">Fim</div><div class="tempo t-fim" style="font-size:18px">--:--</div></div>
        </div>
        <div class="linha" style="margin-top:10px">
          <button class="btn b-ini" style="flex:1" title="Marca o início no ponto atual (Alt+I)">⏱ Início</button>
          <button class="btn b-fim" style="flex:1" title="Marca o fim no ponto atual (Alt+F)">⏱ Fim</button>
        </div>
        <div class="linha" style="margin-top:6px">
          <button class="btn b-ult" data-s="30" style="flex:1" title="Do ponto atual menos 30 s até agora">↶ últimos 30s</button>
          <button class="btn b-ult" data-s="60" style="flex:1" title="Do ponto atual menos 60 s até agora">↶ últimos 60s</button>
        </div>
      </div>
      <div style="margin-top:10px"><button class="grande gerar" title="Manda o trecho pro gerador">✂ GERAR CORTE <kbd>Alt+G</kbd></button></div>
      <div class="linha" style="margin-top:9px;justify-content:space-between">
        <button class="link b-ver">▶ assistir o trecho</button><button class="link b-limpar">limpar marcas</button>
      </div>
      <div style="margin-top:12px;text-align:center"><button class="link b-ir-ia">🤖 ou deixe a IA achar e cortar os melhores momentos →</button></div>
    </div>`;
  abaMom.innerHTML = `
    <div class="sec">
      <div class="rot">🤖 IA corta os melhores momentos</div>
      <div class="cartao">
        <div class="dica" style="margin-bottom:6px">Quantos cortes</div>
        <div class="seg ia-n">${[1, 2, 3, 4, 5].map((n) => `<button data-v="${n}" class="${n === 3 ? "on" : ""}">${n}</button>`).join("")}</div>
        <div class="dica" style="margin:8px 0 6px">Duração de cada um</div>
        <div class="seg ia-dur">${[30, 45, 60, 90].map((d) => `<button data-v="${d}" class="${d === 60 ? "on" : ""}">${d}s</button>`).join("")}</div>
        <div style="margin-top:10px"><button class="grande b-ia" title="A IA ouve o vídeo, escolhe os melhores trechos e manda gerar">🤖 ACHAR E CORTAR SOZINHA</button></div>
        <div class="dica ia-st" style="margin-top:8px">A IA ouve o vídeo, usa o gráfico de replays e os minutos citados nos comentários como pista, escolhe os trechos com começo e fim certos e manda gerar. Você recebe um aviso quando cada corte ficar pronto.</div>
        <div class="ia-lista"></div>
      </div>
      <div class="rot">Mais assistidos de novo</div><div class="l-calor"></div>
      <div class="rot">Citados nos comentários</div><div class="l-com"></div>
      <div class="dica" style="margin-top:6px">Role a página até os comentários pra eu ler mais.</div>
    </div>`;
  const $ = (s) => abaCortar.querySelector(s);
  const mensagem = (t, tipo = "") => painel.rodape(t, tipo);

  function linkLimpo() {
    const u = new URL(location.href);
    const id = u.searchParams.get("v") || (u.pathname.startsWith("/shorts/") ? u.pathname.split("/")[2] : null);
    return id ? `https://www.youtube.com/watch?v=${id}` : null;
  }
  const video = () => document.querySelector("video.html5-main-video") || document.querySelector("video");
  const anuncio = () => !!document.querySelector(".html5-video-player.ad-showing, .html5-video-player.ad-interrupting");
  const tituloVideo = () => (document.querySelector("h1.ytd-watch-metadata, h1.title") || {}).textContent?.trim() || document.title.replace(/ - YouTube$/, "");

  function desenhar() {
    $(".t-ini").textContent = inicio == null ? "--:--" : UI.relogio(inicio);
    $(".t-fim").textContent = fim == null ? "--:--" : UI.relogio(fim);
    const d = inicio != null && fim != null ? fim - inicio : null;
    const tdur = $(".t-dur");
    tdur.textContent = d == null ? "–" : `${Math.round(d)}s`;
    tdur.style.color = d == null ? "" : d >= 5 && d <= 180 ? "#3ddc84" : "#ff4d55";
    $(".gerar").disabled = !(d >= 5 && d <= 180);
  }
  function podeMarcar() {
    if (anuncio()) { mensagem("Espere o anúncio terminar para marcar o vídeo.", "erro"); return null; }
    return video();
  }
  function marcarInicio() { const v = podeMarcar(); if (v) { inicio = v.currentTime; if (fim != null && fim <= inicio) fim = null; desenhar(); } }
  function marcarFim() { const v = podeMarcar(); if (v) { fim = v.currentTime; if (inicio != null && fim <= inicio) inicio = null; desenhar(); } }
  function trecho(ini, f) {
    const v = video(), dur = v && isFinite(v.duration) ? v.duration : Infinity;
    inicio = Math.max(0, ini); fim = Math.min(dur, f); desenhar();
    painel.selecionar("cortar");
  }
  $(".b-ini").onclick = marcarInicio;
  $(".b-fim").onclick = marcarFim;
  abaCortar.querySelectorAll(".b-ult").forEach((b) => (b.onclick = () => { const v = podeMarcar(); if (v) trecho(v.currentTime - +b.dataset.s, v.currentTime); }));
  $(".b-limpar").onclick = () => { inicio = fim = null; desenhar(); };
  $(".b-ver").onclick = () => { const v = video(); if (v && inicio != null) { v.currentTime = inicio; v.play(); } };
  $(".gerar").onclick = gerar;

  async function gerar() {
    const url = linkLimpo();
    if (inicio == null || fim == null || fim <= inicio) return mensagem("Marque o início e depois o fim.", "erro");
    if (fim - inicio < 5 || fim - inicio > 180) return mensagem("O corte precisa ter entre 5 s e 3 min.", "erro");
    mensagem("✂ Mandando pro gerador…");
    $(".gerar").disabled = true;
    const r = await UI.api("gerar", { url, ini: inicio.toFixed(3), fim: fim.toFixed(3) });
    mensagem(r.msg || (r.offline ? "Programa desligado." : ""), r.ok ? "ok" : "erro");
    if (r.ok) { inicio = fim = null; }
    desenhar();
  }

  document.addEventListener("keydown", (e) => {
    if (!e.altKey || !ativo || !linkLimpo()) return;
    const k = e.key.toLowerCase();
    if (k === "i") { e.preventDefault(); marcarInicio(); } else if (k === "f") { e.preventDefault(); marcarFim(); }
    else if (k === "g") { e.preventDefault(); gerar(); }
  });

  // ---------- momentos: gráfico de replays e comentários ----------
  function picosReplay(n = 5) {
    const v = video(), dur = v && isFinite(v.duration) ? v.duration : 0;
    if (!dur) return [];
    const caixa = document.querySelector(".ytp-heat-map-container");
    const caminhos = [...document.querySelectorAll(".ytp-heat-map-path")];
    if (!caminhos.length) return [];
    const pontos = [];
    const cr = caixa && caixa.getBoundingClientRect();
    for (const p of caminhos) {
      const nums = (p.getAttribute("d") || "").match(/-?\d+(\.\d+)?/g);
      if (!nums) continue;
      let ini = 0, larg = 1;
      const cap = p.closest(".ytp-heat-map-chapter");
      if (cap && cr && cr.width && caminhos.length > 1) {
        const r = cap.getBoundingClientRect(); ini = (r.left - cr.left) / cr.width; larg = r.width / cr.width;
      }
      for (let i = 0; i + 1 < nums.length; i += 2) {
        const x = +nums[i], y = +nums[i + 1];
        if (x >= 0 && x <= 1000 && y >= 0 && y <= 100) pontos.push({ t: (ini + (x / 1000) * larg) * dur, forca: 100 - y });
      }
    }
    pontos.sort((a, b) => a.t - b.t);
    // só os topos de verdade: mais alto que os vizinhos e pelo menos 55% do pico mais forte do vídeo
    const maior = Math.max(0, ...pontos.map((p) => p.forca));
    const topos = pontos.filter((p, i) => (!pontos[i - 1] || p.forca >= pontos[i - 1].forca) && (!pontos[i + 1] || p.forca >= pontos[i + 1].forca));
    topos.sort((a, b) => b.forca - a.forca);
    const escolhidos = [];
    for (const p of topos) {
      if (p.forca < 35 || p.forca < maior * 0.55 || p.t < 5) continue;
      if (escolhidos.every((e) => Math.abs(e.t - p.t) > Math.max(30, dur / 40))) escolhidos.push(p);
      if (escolhidos.length >= n) break;
    }
    return escolhidos;
  }

  const RE_TEMPO = /^(?:(\d{1,2}):)?(\d{1,2}):(\d{2})$/;
  function comentariosComTempo() {
    const lista = [];
    document.querySelectorAll("ytd-comment-thread-renderer #content-text, ytd-comment-view-model #content-text").forEach((c) => {
      const texto = (c.innerText || "").replace(/\s+/g, " ").trim();
      c.querySelectorAll("a").forEach((a) => {
        const m = (a.textContent || "").trim().match(RE_TEMPO);
        if (m) lista.push({ t: (+m[1] || 0) * 3600 + +m[2] * 60 + +m[3], texto: texto.slice(0, 200) });
      });
    });
    return lista;
  }
  // junta citações próximas (4:05, 4:08 e 4:10 são o mesmo lance)
  function agruparComentarios(lista, n = 6) {
    const grupos = [];
    for (const c of [...lista].sort((a, b) => a.t - b.t)) {
      const g = grupos[grupos.length - 1];
      if (g && c.t - g.t <= 15) { g.n += 1; if (g.textos.length < 3 && !g.textos.includes(c.texto)) g.textos.push(c.texto); }
      else grupos.push({ t: c.t, n: 1, textos: [c.texto] });
    }
    return grupos.sort((a, b) => b.n - a.n || a.t - b.t).slice(0, n);
  }

  function itemMomento(t, titulo, sub) {
    const linha = UI.el("div", { class: "item" }, `<div class="tempo">${UI.relogio(t)}</div><div class="txt"><b>${UI.esc(titulo)}</b><small>${UI.esc(sub)}</small></div>`);
    linha.appendChild(UI.el("button", { title: "Ir até esse ponto", onclick: () => { const v = video(); if (v) { v.currentTime = Math.max(0, t - 3); v.play(); } } }, "▶"));
    linha.appendChild(UI.el("button", { title: "Marcar um trecho de 1 minuto em volta", onclick: () => trecho(t - 20, t + 40) }, "✂"));
    return linha;
  }
  let assinaturaMomentos = "";
  function desenharMomentos() {
    const picos = picosReplay(), grupos = agruparComentarios(comentariosComTempo());
    const assinatura = picos.map((p) => Math.round(p.t)).join() + "|" + grupos.map((g) => g.t + ":" + g.n).join();
    if (assinatura === assinaturaMomentos) return;
    assinaturaMomentos = assinatura;
    const lc = abaMom.querySelector(".l-calor"), lm = abaMom.querySelector(".l-com");
    lc.innerHTML = ""; lm.innerHTML = "";
    if (!picos.length) lc.appendChild(UI.el("div", { class: "vazio" }, "Este vídeo não tem o gráfico de replays (vídeos novos ou com pouca visualização)."));
    picos.forEach((p) => lc.appendChild(itemMomento(p.t, `🔥 pico de replay (${Math.round(p.forca)}%)`, "O pessoal volta pra ver esse trecho de novo")));
    if (!grupos.length) lm.appendChild(UI.el("div", { class: "vazio" }, "Nenhum comentário com minuto lido ainda."));
    grupos.forEach((g) => lm.appendChild(itemMomento(g.t, `💬 ${g.n} comentário${g.n > 1 ? "s" : ""}`, g.textos[0] || "")));
    painel.badge("momentos", picos.length + grupos.length);
  }

  // ---------- 🤖 IA corta os melhores momentos ----------
  let iaTrabalho = null, iaTimer = null;
  const IA_TEXTO = abaMom.querySelector(".ia-st").textContent;
  const iaSt = (txt, cor = "") => { const el = abaMom.querySelector(".ia-st"); el.textContent = txt; el.style.color = cor; };
  const escolhido = (sel) => +abaMom.querySelector(`${sel} button.on`).dataset.v;
  abaMom.querySelectorAll(".ia-n button, .ia-dur button").forEach((b) => (b.onclick = () => {
    b.parentElement.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
  }));
  abaCortar.querySelector(".b-ir-ia").onclick = () => painel.selecionar("momentos");
  abaMom.querySelector(".b-ia").onclick = iaCortar;

  async function iaCortar() {
    const url = linkLimpo();
    if (!url) return;
    if (!conectado) return iaSt("Programa desligado. Abra o Gerador de Cortes e clique em LIGAR MONITOR.", "#ff4d55");
    const b = abaMom.querySelector(".b-ia");
    b.disabled = true;
    iaSt("🤖 Mandando pro programa…");
    const pedido = { url, n: escolhido(".ia-n"), dur: escolhido(".ia-dur"), titulo: tituloVideo(),
                     comentarios: agruparComentarios(comentariosComTempo(), 8),
                     picos: picosReplay(5).map((p) => ({ t: Math.round(p.t), forca: Math.round(p.forca) })) };
    const r = await UI.api("ia_momentos", {}, pedido);
    if (!r.ok) { b.disabled = false; return iaSt(r.msg || "Não deu certo.", "#ff4d55"); }
    iaTrabalho = r.trabalho;
    desenharIa();
    acompanharIa();
  }
  function desenharIa() {
    const t = iaTrabalho, b = abaMom.querySelector(".b-ia"), lista = abaMom.querySelector(".ia-lista");
    if (!t) return;
    lista.innerHTML = "";
    const passou = Math.round(((t.fim || Date.now() / 1000) - t.inicio));
    if (t.estado === "trabalhando") {
      b.disabled = true;
      b.textContent = "🤖 TRABALHANDO…";
      iaSt(`⏳ ${t.etapa || "trabalhando..."}  (${UI.relogio(passou)})`, "#ffd400");
      return;
    }
    b.disabled = false;
    b.textContent = "🤖 ACHAR E CORTAR SOZINHA";
    iaSt(t.estado === "pronto" ? `✅ ${t.msg}` : `⚠ ${t.msg}`, t.estado === "pronto" ? "#3ddc84" : "#ff4d55");
    (t.momentos || []).forEach((m, i) => lista.appendChild(itemMomento(m.inicio,
      `✂ Corte ${i + 1}: ${UI.relogio(m.inicio)}–${UI.relogio(m.fim)}` + (m.nota != null ? ` · nota ${m.nota}` : ""),
      m.motivo || "")));
    painel.badge("momentos", (t.momentos || []).length);
  }
  function acompanharIa() {
    clearTimeout(iaTimer);
    if (!iaTrabalho || iaTrabalho.estado !== "trabalhando") return;
    iaTimer = setTimeout(async () => {
      const s = await UI.api("status");
      const t = (s.ia_momentos || []).find((x) => x.id === iaTrabalho.id);
      if (t) { iaTrabalho = t; desenharIa(); }
      else if (s.offline) iaSt("Programa desligado — o trabalho parou.", "#ff4d55");
      acompanharIa();
    }, 3000);
  }
  // voltou pro vídeo (ou recarregou a página) com um trabalho da IA: mostra o andamento de novo
  function retomarIa(s) {
    const t = (s.ia_momentos || []).find((x) => x.url === linkLimpo());
    if (t && (!iaTrabalho || iaTrabalho.id !== t.id || iaTrabalho.estado !== t.estado)) {
      iaTrabalho = t; desenharIa(); acompanharIa();
    }
  }

  // ---------- bot ----------
  function respostaLocal(tipo) {
    const picos = picosReplay(3), grupos = agruparComentarios(comentariosComTempo(), 3);
    if (tipo === "momentos") {
      if (!picos.length && !grupos.length) return { texto: "Não achei pistas ainda: este vídeo não tem o gráfico de replays e não li comentários com minuto. Role até os comentários e pergunte de novo." };
      const acoes = [];
      for (const p of picos.slice(0, 2)) acoes.push({ tipo: "trecho", ini: Math.max(0, p.t - 20), fim: p.t + 40, rotulo: `✂ Trecho em ${UI.relogio(p.t)}` });
      if (grupos[0]) acoes.push({ tipo: "pular", t: grupos[0].t, rotulo: `▶ Ir para ${UI.relogio(grupos[0].t)}` });
      const partes = [];
      if (picos.length) partes.push(`Picos de replay em ${picos.map((p) => UI.relogio(p.t)).join(", ")}`);
      if (grupos.length) partes.push(`os comentários citam ${grupos.map((g) => `${UI.relogio(g.t)} (${g.n}x)`).join(", ")}`);
      return { texto: partes.join("; ") + ".", acoes };
    }
    if (tipo === "titulo") return { texto: "Pra sugerir títulos eu preciso de uma IA ligada no programa (Contas & IA)." };
    return { texto: "Sem IA eu só consigo achar os momentos (gráfico de replays e comentários). Ligue uma IA no programa pra conversar sobre o vídeo." };
  }

  const bot = UI.criarBot({
    painel, abaId: "bot",
    chave: () => `youtube:${(linkLimpo() || "").split("v=")[1] || "-"}`,
    sugestoes: [{ tipo: "momentos", rotulo: "🎯 Melhores momentos" }, { tipo: "titulo", rotulo: "✍ Título pro trecho" },
                { tipo: "resumo", rotulo: "📝 Do que fala o vídeo?" }],
    contexto: () => {
      const v = video();
      const coms = comentariosComTempo().slice(0, 60);
      const outros = [...document.querySelectorAll("ytd-comment-thread-renderer #content-text")].slice(0, 40)
        .map((c) => (c.innerText || "").replace(/\s+/g, " ").trim()).filter(Boolean);
      return {
        plat: "youtube", titulo: tituloVideo(),
        tempo_video: v ? v.currentTime : null, duracao_video: v && isFinite(v.duration) ? v.duration : null,
        comentarios: coms, chat: outros,
        stats: { "picos de replay": picosReplay().map((p) => `${UI.relogio(p.t)} (${Math.round(p.forca)}%)`).join(", ") || "sem gráfico",
                 "trecho marcado": inicio != null && fim != null ? `${UI.relogio(inicio)}–${UI.relogio(fim)}` : "nenhum" },
      };
    },
    local: respostaLocal,
    executar: async (a) => {
      const v = video();
      if (a.tipo === "pular" && v) { v.currentTime = a.t; v.play(); return true; }
      if (a.tipo === "trecho") { trecho(a.ini, a.fim); mensagem("Trecho marcado. Confira e clique em GERAR CORTE.", "ok"); return true; }
      return false;
    },
  });

  async function atualizarStatus() {
    if (!ativo || !linkLimpo()) return;
    const s = await UI.api("status");
    conectado = !s.offline;
    painel.status(conectado ? "conectado" : "programa desligado", conectado ? "ok" : "off");
    bot.atualizarIa(conectado ? s.ia : null);
    if (conectado) retomarIa(s);
  }

  function ciclo() {
    const l = ativo ? linkLimpo() : null;
    if (!l) { painel.remover(); ultimoLink = null; return; }
    painel.mostrar();
    if (l !== ultimoLink) {
      ultimoLink = l; inicio = fim = null; assinaturaMomentos = ""; desenhar(); bot.recarregar();
      iaTrabalho = null; clearTimeout(iaTimer); abaMom.querySelector(".ia-lista").innerHTML = "";
      const b = abaMom.querySelector(".b-ia"); b.disabled = false; b.textContent = "🤖 ACHAR E CORTAR SOZINHA";
      iaSt(IA_TEXTO);
      atualizarStatus();
    }
    desenharMomentos();
  }

  if (window.__c916_local) window.__c916_yt = { picosReplay, agruparComentarios, comentariosComTempo, respostaLocal, painel, bot, iaCortar };  // testes
  desenhar();
  UI.config().then((c) => { cfg = c; ativo = c.youtube !== false; ciclo(); });
  UI.aoMudarConfig((c) => { cfg = c; ativo = c.youtube !== false; ciclo(); });
  setInterval(ciclo, 1500);
  setInterval(atualizarStatus, 8000);
})();
