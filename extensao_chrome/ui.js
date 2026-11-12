// Cortes 9:16 — peças de interface compartilhadas (painel flutuante, abas, avisos e o bot).
// Tudo fica dentro de um "shadow DOM": o visual da Twitch/Kick/YouTube não mexe no painel e vice-versa.
(() => {
  if (window.C916UI) return;

  const ICONES = {
    tesoura: '<svg viewBox="0 0 24 24"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4 8.1 15.9M14.5 14.5 20 20M8.1 8.1 12 12"/></svg>',
    bot: '<svg viewBox="0 0 24 24"><rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 4v4M9 13h.01M15 13h.01M9.5 17h5"/></svg>',
    raio: '<svg viewBox="0 0 24 24"><path d="M13 2 4 14h7l-1 8 9-12h-7z"/></svg>',
    menos: '<svg viewBox="0 0 24 24"><path d="M5 12h14"/></svg>',
    enviar: '<svg viewBox="0 0 24 24"><path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/></svg>',
    copiar: '<svg viewBox="0 0 24 24"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>',
    limpar: '<svg viewBox="0 0 24 24"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/></svg>',
  };

  const CSS = `
  :host{all:initial}
  *{box-sizing:border-box}
  .p{--bg:#111114;--bg2:#1a1a1f;--bg3:#24242b;--linha:#2e2e37;--txt:#f4f4f6;--txt2:#a6a6b2;--txt3:#6f6f7c;
     --verm:#e3262e;--verm2:#ff4d55;--amar:#ffd400;--verde:#3ddc84;--azul:#5aa9ff;
     position:fixed;z-index:2147483000;width:330px;color:var(--txt);background:var(--bg);
     border:1px solid var(--linha);border-radius:16px;box-shadow:0 18px 50px rgba(0,0,0,.55),0 0 0 1px rgba(255,255,255,.03) inset;
     font:500 13px/1.4 "Segoe UI Variable","Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif;overflow:hidden;
     user-select:none;transition:box-shadow .3s}
  .p.pisca{box-shadow:0 0 0 3px var(--amar),0 18px 50px rgba(0,0,0,.55)}
  svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex:none}
  button{font:inherit;color:inherit;border:0;cursor:pointer;background:none}
  button:focus-visible,input:focus-visible,textarea:focus-visible{outline:2px solid var(--azul);outline-offset:1px}
  button:disabled{opacity:.5;cursor:default}
  [hidden]{display:none!important}

  .topo{display:flex;align-items:center;gap:8px;padding:10px 10px 8px 12px;cursor:grab;
        background:linear-gradient(180deg,#19191e,#131317)}
  .topo:active{cursor:grabbing}
  .logo{width:26px;height:26px;border-radius:8px;background:var(--verm);display:grid;place-items:center;color:#fff;
        box-shadow:0 2px 10px rgba(227,38,46,.45)}
  .logo svg{width:15px;height:15px}
  .nome{font-weight:700;font-size:13.5px;letter-spacing:.2px}
  .nome small{display:block;font-weight:500;font-size:11px;color:var(--txt2);margin-top:-1px;white-space:nowrap;
              overflow:hidden;text-overflow:ellipsis;max-width:190px}
  .esp{flex:1}
  .ico{width:28px;height:28px;border-radius:8px;display:grid;place-items:center;color:var(--txt2)}
  .ico:hover{background:var(--bg3);color:var(--txt)}

  .pilula{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:600;color:var(--txt2)}
  .pilula i{width:8px;height:8px;border-radius:50%;background:var(--txt3);flex:none}
  .pilula.rec i{background:var(--verm2);animation:pulsa 1.4s infinite}
  .pilula.ok i{background:var(--verde)}
  .pilula.off i{background:var(--amar)}
  @keyframes pulsa{0%{box-shadow:0 0 0 0 rgba(255,77,85,.6)}100%{box-shadow:0 0 0 7px rgba(255,77,85,0)}}

  .abas{display:flex;gap:4px;padding:0 10px;border-bottom:1px solid var(--linha);background:#131317}
  .aba{position:relative;display:flex;align-items:center;gap:6px;padding:9px 10px 10px;color:var(--txt2);font-weight:600;
       border-bottom:2px solid transparent;margin-bottom:-1px}
  .aba:hover{color:var(--txt)}
  .aba.on{color:var(--txt);border-color:var(--verm)}
  .aba b{min-width:17px;height:17px;padding:0 5px;border-radius:9px;background:var(--verm);color:#fff;font-size:10.5px;
         display:grid;place-items:center}
  .corpo{max-height:min(62vh,560px);overflow:auto;scrollbar-width:thin;scrollbar-color:#3a3a44 transparent}
  .sec{padding:12px}
  .rodape{padding:7px 12px;border-top:1px solid var(--linha);font-size:11.5px;color:var(--txt2);min-height:30px;
          background:#131317;transition:color .2s}
  .rodape.ok{color:var(--verde)} .rodape.erro{color:var(--verm2)}

  .alerta{display:flex;align-items:center;gap:8px;padding:9px 12px;background:linear-gradient(90deg,#b5121a,var(--verm));
          color:#fff;font-weight:700}
  .alerta span{flex:1;font-size:12.5px}
  .alerta button{padding:6px 10px;border-radius:8px;font-weight:800}
  .alerta .sim{background:var(--amar);color:#111}
  .alerta .nao{background:rgba(0,0,0,.25)}

  /* bolinha (minimizado) */
  .bola{position:fixed;z-index:2147483000;width:52px;height:52px;border-radius:50%;background:var(--verm,#e3262e);color:#fff;
        display:grid;place-items:center;box-shadow:0 8px 24px rgba(0,0,0,.5);cursor:pointer;border:2px solid rgba(255,255,255,.15)}
  .bola svg{width:22px;height:22px}
  .bola i{position:absolute;right:2px;top:2px;width:12px;height:12px;border-radius:50%;border:2px solid #111;background:#6f6f7c}
  .bola i.rec{background:#ff4d55} .bola i.ok{background:#3ddc84} .bola i.off{background:#ffd400}
  .bola.pisca{animation:bolapisca .8s infinite alternate}
  @keyframes bolapisca{to{box-shadow:0 0 0 7px rgba(255,212,0,.8)}}

  /* peças comuns */
  .cartao{background:var(--bg2);border:1px solid var(--linha);border-radius:12px;padding:10px}
  .linha{display:flex;gap:6px;align-items:center}
  .rot{font-size:11px;font-weight:700;color:var(--txt3);text-transform:uppercase;letter-spacing:.6px;margin:12px 0 6px}
  .rot:first-child{margin-top:0}
  .seg{display:flex;background:var(--bg2);border:1px solid var(--linha);border-radius:10px;padding:3px;gap:3px}
  .seg button{flex:1;padding:7px 0;border-radius:7px;color:var(--txt2);font-weight:700;font-size:12.5px}
  .seg button:hover{color:var(--txt)}
  .seg button.on{background:var(--bg3);color:var(--txt);box-shadow:0 0 0 1px #3a3a46 inset}
  .seg button.marca.on{background:var(--amar);color:#111}
  .btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;padding:8px 12px;border-radius:10px;
       background:var(--bg3);font-weight:700;font-size:12.5px}
  .btn:hover{background:#2d2d36}
  .grande{width:100%;padding:13px 0;font-size:15px;font-weight:800;letter-spacing:.4px;border-radius:12px;color:#fff;
          background:linear-gradient(180deg,var(--verm2),var(--verm));box-shadow:0 6px 18px rgba(227,38,46,.35),0 -3px 0 rgba(0,0,0,.18) inset}
  .grande:hover{filter:brightness(1.08)}
  .grande:active{transform:translateY(1px)}
  .grande kbd{font:600 10.5px Consolas,monospace;background:rgba(0,0,0,.25);border-radius:5px;padding:2px 5px;margin-left:4px}
  .dica{font-size:11.5px;color:var(--txt2)}
  .link{color:var(--azul);font-weight:600;font-size:11.5px;padding:0}
  .link:hover{text-decoration:underline}
  input,textarea{font:inherit;color:var(--txt);background:var(--bg2);border:1px solid var(--linha);border-radius:10px;
                 padding:8px 10px;width:100%;outline:none;user-select:text}
  input:focus,textarea:focus{border-color:#4a4a57}
  .vazio{color:var(--txt3);font-size:12px;text-align:center;padding:14px 6px}

  /* termômetro e pulso do chat */
  .termo{height:8px;border-radius:5px;background:var(--bg3);overflow:hidden}
  .termo div{height:100%;width:0;border-radius:5px;transition:width .6s,background .6s}
  .pulso{display:flex;align-items:flex-end;gap:2px;height:38px;margin-top:8px}
  .pulso span{flex:1;background:#33333d;border-radius:2px 2px 0 0;min-height:2px;transition:height .4s}
  .pulso span.quente{background:var(--verm2)} .pulso span.morno{background:#ff9f1a}
  .nums{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:8px}
  .nums div{background:var(--bg3);border-radius:8px;padding:6px 7px}
  .nums b{display:block;font-size:14px}
  .nums span{font-size:10.5px;color:var(--txt2)}
  .tags{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}
  .tags span{background:var(--bg3);border-radius:6px;padding:2px 7px;font-size:11.5px;color:#d9d9e0}

  /* listas de momentos */
  .item{display:flex;align-items:center;gap:8px;background:var(--bg2);border:1px solid var(--linha);border-radius:10px;
        padding:8px 9px;margin-bottom:6px}
  .item.pendente{border-color:var(--amar)}
  .item .txt{flex:1;min-width:0;font-size:12px}
  .item .txt b{font-weight:700}
  .item .txt small{display:block;color:var(--txt2);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .item button{padding:5px 8px;border-radius:7px;background:var(--bg3);font-size:12px;font-weight:700}
  .item button:hover{background:#33333d}
  .tempo{font:700 12px Consolas,monospace;color:var(--amar)}

  /* bot */
  .bot{display:flex;flex-direction:column;height:min(56vh,470px)}
  .bot-topo{display:flex;align-items:center;gap:8px;padding:9px 12px;border-bottom:1px solid var(--linha);font-size:11.5px;color:var(--txt2)}
  .bot-msgs{flex:1;overflow:auto;padding:10px 12px;display:flex;flex-direction:column;gap:8px;scrollbar-width:thin;
            scrollbar-color:#3a3a44 transparent;user-select:text}
  .msg{max-width:92%;padding:8px 10px;border-radius:12px;font-size:12.5px;line-height:1.45;white-space:pre-wrap;word-wrap:break-word}
  .msg.voce{align-self:flex-end;background:#2a2f45;border-bottom-right-radius:4px}
  .msg.bot{align-self:flex-start;background:var(--bg2);border:1px solid var(--linha);border-bottom-left-radius:4px}
  .msg.sistema{align-self:center;background:none;color:var(--txt3);font-size:11px;padding:2px}
  .msg .de{display:flex;align-items:center;gap:6px;font-size:10.5px;font-weight:700;color:var(--txt3);margin-bottom:3px;
           text-transform:uppercase;letter-spacing:.5px}
  .nota{display:inline-block;padding:1px 7px;border-radius:6px;font-weight:800;font-size:11px;color:#111}
  .gancho{margin-top:7px;background:#fff;color:#111;font-weight:900;font-size:12.5px;padding:7px 9px;border-radius:6px;
          border-left:4px solid var(--verm);display:flex;gap:6px;align-items:flex-start;text-transform:uppercase}
  .gancho span{flex:1}
  .titulos{margin:6px 0 0;padding:0;list-style:none}
  .titulos li{display:flex;gap:6px;align-items:center;background:var(--bg3);border-radius:7px;padding:5px 7px;margin-top:4px}
  .titulos li span{flex:1}
  .copiar{color:var(--txt2);padding:2px}
  .copiar:hover{color:var(--txt)}
  .acoes{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}
  .acoes button{background:var(--verm);color:#fff;border-radius:8px;padding:6px 10px;font-size:12px;font-weight:800}
  .acoes button:hover{filter:brightness(1.1)}
  .acoes button.feito{background:var(--bg3);color:var(--txt2)}
  .chips{display:flex;gap:5px;overflow-x:auto;padding:8px 12px 0;scrollbar-width:none}
  .chips button{white-space:nowrap;background:var(--bg2);border:1px solid var(--linha);border-radius:999px;padding:5px 10px;
                font-size:11.5px;font-weight:600;color:#dcdce3}
  .chips button:hover{border-color:#4a4a57;color:#fff}
  .entrada{display:flex;gap:6px;padding:8px 12px 12px}
  .entrada textarea{resize:none;height:38px;max-height:90px;padding:9px 10px}
  .entrada button{width:38px;height:38px;border-radius:10px;background:var(--verm);color:#fff;display:grid;place-items:center;flex:none}
  .pensando{display:inline-flex;gap:4px;padding:4px 2px}
  .pensando i{width:6px;height:6px;border-radius:50%;background:var(--txt2);animation:pula 1s infinite}
  .pensando i:nth-child(2){animation-delay:.15s}.pensando i:nth-child(3){animation-delay:.3s}
  @keyframes pula{0%,60%,100%{opacity:.3;transform:none}30%{opacity:1;transform:translateY(-3px)}}
  `;

  // ---------- comunicação com o programa (pelo service worker) ----------
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

  const guardar = {
    async ler(chave, padrao) {
      try { const r = await chrome.storage.local.get([chave]); return r[chave] === undefined ? padrao : r[chave]; }
      catch (e) { return padrao; }
    },
    gravar(chave, valor) { try { chrome.storage.local.set({ [chave]: valor }); } catch (e) {} },
  };

  const PADRAO_CFG = { twitch: true, kick: true, youtube: true, botAuto: true, botIa: true };
  async function config() { return { ...PADRAO_CFG, ...(await guardar.ler("cfg", {})) }; }
  function aoMudarConfig(fn) {
    try { chrome.storage.onChanged.addListener((m) => { if (m.cfg) fn({ ...PADRAO_CFG, ...(m.cfg.newValue || {}) }); }); } catch (e) {}
  }

  function el(tag, attrs = {}, html = "") {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") e.className = v; else if (k.startsWith("on")) e[k] = v; else e.setAttribute(k, v);
    }
    if (html) e.innerHTML = html;
    return e;
  }
  const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const relogio = (s) => {
    s = Math.max(0, Math.floor(s || 0));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), ss = String(s % 60).padStart(2, "0");
    return h ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
  };

  // ---------- painel flutuante ----------
  function criarPainel({ subtitulo = "", abas = [], chave = "painel" }) {
    const host = el("div", { id: "c916-host" });
    const raiz = host.attachShadow({ mode: "open" });
    raiz.appendChild(el("style", {}, CSS));
    const p = el("div", { class: "p", role: "dialog", "aria-label": "Cortes 9:16" });
    p.innerHTML = `
      <div class="alerta" hidden></div>
      <div class="topo">
        <div class="logo">${ICONES.tesoura}</div>
        <div class="nome">Cortes 9:16<small></small></div>
        <div class="esp"></div>
        <span class="pilula"><i></i><span>conectando…</span></span>
        <button class="ico min" title="Minimizar (vira uma bolinha)">${ICONES.menos}</button>
      </div>
      <div class="abas" role="tablist"></div>
      <div class="corpo"></div>
      <div class="rodape" aria-live="polite"></div>`;
    const bola = el("button", { class: "bola", title: "Abrir o Cortes 9:16", hidden: "" }, `${ICONES.tesoura}<i></i>`);
    raiz.append(p, bola);
    const $ = (s) => p.querySelector(s);
    $(".nome small").textContent = subtitulo;

    const conteudos = {}, botoesAba = {};
    let atual = null;
    for (const a of abas) {
      const b = el("button", { class: "aba", role: "tab" }, `${ICONES[a.icone] || ""}<span>${esc(a.rotulo)}</span><b hidden></b>`);
      b.onclick = () => selecionar(a.id);
      $(".abas").appendChild(b);
      botoesAba[a.id] = b;
      const c = el("div", { role: "tabpanel", hidden: "" });
      $(".corpo").appendChild(c);
      conteudos[a.id] = c;
    }
    const aoTrocar = [];
    function selecionar(id) {
      atual = id;
      for (const k in conteudos) { conteudos[k].hidden = k !== id; botoesAba[k].classList.toggle("on", k === id); }
      badge(id, 0);
      guardar.gravar(`${chave}:aba`, id);
      aoTrocar.forEach((fn) => fn(id));
      requestAnimationFrame(aplicarPos);
    }
    function badge(id, n) {
      const b = botoesAba[id] && botoesAba[id].querySelector("b");
      if (!b) return;
      b.hidden = !n || id === atual;
      b.textContent = n > 9 ? "9+" : String(n);
    }

    // posição (arrastar pelo topo ou pela bolinha) — lembrada por site
    let pos = { direita: 18, baixo: 90 }, minimizado = false;
    // só ajusta o que aparece (janela pequena/minimizada não estraga a posição guardada)
    const limitar = (v, max) => Math.max(6, Math.min(Math.max(6, max), v));
    function aplicarPos() {
      const w = innerWidth, h = innerHeight;
      if (!w || !h) return;
      const larg = p.hidden ? 52 : (p.offsetWidth || 330), alt = p.hidden ? 52 : (p.offsetHeight || 200);
      const d = limitar(pos.direita, w - Math.min(larg, w - 12) - 6), b = limitar(pos.baixo, h - Math.min(alt, h - 12) - 6);
      for (const e of [p, bola]) { e.style.right = d + "px"; e.style.bottom = b + "px"; }
    }
    function arrastavel(alca, aoClicar) {
      alca.addEventListener("pointerdown", (e) => {
        if (e.button !== 0 || e.target.closest(".ico")) return;
        const x0 = e.clientX, y0 = e.clientY;
        const d0 = parseFloat(p.style.right) || pos.direita, b0 = parseFloat(p.style.bottom) || pos.baixo;
        let moveu = false;
        alca.setPointerCapture(e.pointerId);
        const mover = (ev) => {
          if (Math.abs(ev.clientX - x0) + Math.abs(ev.clientY - y0) > 4) moveu = true;
          pos.direita = d0 - (ev.clientX - x0); pos.baixo = b0 - (ev.clientY - y0); aplicarPos();
        };
        const soltar = () => {
          alca.removeEventListener("pointermove", mover); alca.removeEventListener("pointerup", soltar);
          if (moveu) {
            pos = { direita: parseFloat(p.style.right), baixo: parseFloat(p.style.bottom) };   // onde ficou de fato
            guardar.gravar(`${chave}:pos`, pos);
          } else if (aoClicar) aoClicar();
        };
        alca.addEventListener("pointermove", mover); alca.addEventListener("pointerup", soltar);
      });
    }
    function minimizar(sim) {
      minimizado = sim; p.hidden = sim; bola.hidden = !sim;
      if (!sim) bola.classList.remove("pisca");
      aplicarPos();
      guardar.gravar(`${chave}:mini`, sim);
    }
    arrastavel($(".topo"));
    arrastavel(bola, () => minimizar(false));
    $(".min").onclick = () => minimizar(true);
    addEventListener("resize", aplicarPos);
    aplicarPos();

    // não deixa o site "roubar" as teclas digitadas no painel (atalhos da Twitch/YouTube)
    for (const tipo of ["keydown", "keyup", "keypress"]) {
      raiz.addEventListener(tipo, (e) => { if (e.target.matches && e.target.matches("input,textarea")) e.stopPropagation(); });
    }

    let tRodape = null;
    const api_ = {
      host, raiz, conteudos,
      aba: (id) => conteudos[id],
      selecionar, badge, onTrocar: (fn) => aoTrocar.push(fn),
      abaAtual: () => atual, minimizado: () => minimizado,
      subtitulo(t) { $(".nome small").textContent = t; },
      status(texto, tipo = "") {
        const pl = $(".pilula"); pl.className = "pilula " + tipo; pl.querySelector("span").textContent = texto;
        bola.querySelector("i").className = tipo;
      },
      rodape(texto, tipo = "", ms = 9000) {
        const r = $(".rodape"); r.textContent = texto; r.className = "rodape " + tipo;
        clearTimeout(tRodape); if (texto && ms) tRodape = setTimeout(() => { r.textContent = ""; r.className = "rodape"; }, ms);
      },
      alerta(texto, botoes = [], ms = 20000) {
        const a = $(".alerta");
        a.innerHTML = `<span>${esc(texto)}</span>`;
        for (const b of botoes) a.appendChild(el("button", { class: b.classe || "", onclick: () => { api_.semAlerta(); b.acao && b.acao(); } }, esc(b.rotulo)));
        a.hidden = false; api_.piscar(true);
        clearTimeout(a._t); a._t = setTimeout(() => api_.semAlerta(), ms);
      },
      semAlerta() { $(".alerta").hidden = true; api_.piscar(false); },
      piscar(sim) { p.classList.toggle("pisca", sim); bola.classList.toggle("pisca", sim && minimizado); },
      mostrar() { if (!host.isConnected) { (document.body || document.documentElement).appendChild(host); aplicarPos(); } },
      remover() { host.remove(); },
    };
    (async () => {
      const salvo = await guardar.ler(`${chave}:pos`, null);
      if (salvo && typeof salvo.direita === "number") { pos = salvo; aplicarPos(); }
      if (await guardar.ler(`${chave}:mini`, false)) minimizar(true);
      const aba = await guardar.ler(`${chave}:aba`, null);
      selecionar(aba && conteudos[aba] ? aba : abas[0].id);
    })();
    return api_;
  }

  // ---------- bot ----------
  // opcoes: { painel, abaId, chave(), contexto(), local(tipo, pergunta), executar(acao, botao), sugestoes: [{tipo, rotulo, pergunta}] }
  function criarBot(opcoes) {
    const caixa = opcoes.painel.aba(opcoes.abaId);
    caixa.innerHTML = `
      <div class="bot">
        <div class="bot-topo"><span class="pilula ia"><i></i><span>IA: verificando…</span></span><div class="esp"></div>
          <button class="ico limpar" title="Limpar a conversa">${ICONES.limpar}</button></div>
        <div class="bot-msgs" aria-live="polite"></div>
        <div class="chips"></div>
        <div class="entrada"><textarea rows="1" maxlength="500" placeholder="Pergunte ao bot… (Enter envia)"></textarea>
          <button class="env" title="Enviar">${ICONES.enviar}</button></div>
      </div>`;
    const $ = (s) => caixa.querySelector(s);
    const msgs = $(".bot-msgs"), campo = $("textarea");
    let historico = [], ia = { pronta: false, rotulo: "sem IA" }, pensando = false, nao_lidas = 0;

    for (const s of opcoes.sugestoes || []) {
      $(".chips").appendChild(el("button", { onclick: () => perguntar(s.tipo, s.pergunta || "", s.rotulo) }, esc(s.rotulo)));
    }
    campo.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviarCampo(); }
    });
    campo.addEventListener("input", () => { campo.style.height = "38px"; campo.style.height = Math.min(90, campo.scrollHeight) + "px"; });
    $(".env").onclick = enviarCampo;
    $(".limpar").onclick = () => { historico = []; desenhar(); salvar(); };
    opcoes.painel.onTrocar((id) => { if (id === opcoes.abaId) { nao_lidas = 0; rolar(); } });

    function enviarCampo() {
      const t = campo.value.trim();
      if (!t || pensando) return;
      campo.value = ""; campo.style.height = "38px";
      perguntar("pergunta", t, t);
    }

    function copiar(texto, botao) {
      navigator.clipboard.writeText(texto).then(() => { botao.style.color = "#3ddc84"; setTimeout(() => (botao.style.color = ""), 1200); }, () => {});
    }
    const corNota = (n) => (n >= 7.5 ? "#3ddc84" : n >= 5 ? "#ffd400" : "#ff7a59");

    function bolha(m) {
      if (m.de === "sistema") return el("div", { class: "msg sistema" }, esc(m.texto));
      const d = el("div", { class: "msg " + m.de });
      if (m.de === "bot") {
        const nota = typeof m.nota === "number" ? `<span class="nota" style="background:${corNota(m.nota)}">${m.nota}/10</span>` : "";
        d.innerHTML = `<div class="de">${ICONES.bot} bot${m.ia ? " · " + esc(m.ia) : ""} ${nota}</div>`;
      }
      d.appendChild(document.createTextNode(m.texto));
      if (m.gancho) {
        const g = el("div", { class: "gancho" }, `<span>${esc(m.gancho)}</span>`);
        const b = el("button", { class: "copiar", title: "Copiar o gancho" }, ICONES.copiar);
        b.onclick = () => copiar(m.gancho, b); g.appendChild(b); d.appendChild(g);
      }
      if (m.titulos && m.titulos.length) {
        const ul = el("ul", { class: "titulos" });
        for (const t of m.titulos) {
          const li = el("li", {}, `<span>${esc(t)}</span>`);
          const b = el("button", { class: "copiar", title: "Copiar" }, ICONES.copiar);
          b.onclick = () => copiar(t, b); li.appendChild(b); ul.appendChild(li);
        }
        d.appendChild(ul);
      }
      if (m.acoes && m.acoes.length) {
        const box = el("div", { class: "acoes" });
        m.acoes.forEach((a, i) => {
          const b = el("button", { title: "Você decide: nada acontece sem o seu clique" }, esc(a.rotulo));
          if (a.feito) b.classList.add("feito");
          b.onclick = async () => {
            b.disabled = true;
            const ok = await opcoes.executar(a, b);
            if (ok) { a.feito = true; b.classList.add("feito"); salvar(); }
            b.disabled = false;
          };
          box.appendChild(b);
        });
        d.appendChild(box);
      }
      return d;
    }
    function rolar() { msgs.scrollTop = msgs.scrollHeight; }
    function desenhar() {
      msgs.innerHTML = "";
      if (!historico.length) {
        msgs.appendChild(el("div", { class: "vazio" },
          "Oi! Eu fico de olho no chat e te ajudo a decidir o que cortar.<br>Use os botões abaixo ou pergunte qualquer coisa."));
      }
      historico.forEach((m) => msgs.appendChild(bolha(m)));
      if (pensando) msgs.appendChild(el("div", { class: "msg bot" }, '<span class="pensando"><i></i><i></i><i></i></span>'));
      rolar();
    }
    async function carregar() {
      historico = (await guardar.ler(`bot:${opcoes.chave()}`, [])).slice(-30);
      desenhar();
    }
    function salvar() { guardar.gravar(`bot:${opcoes.chave()}`, historico.slice(-30)); }
    function adicionar(m) {
      historico.push({ ...m, quando: Date.now() });
      if (historico.length > 40) historico.splice(0, historico.length - 40);
      desenhar(); salvar();
      if (m.de === "bot" && opcoes.painel.abaAtual() !== opcoes.abaId) opcoes.painel.badge(opcoes.abaId, ++nao_lidas);
    }

    async function perguntar(tipo, pergunta, rotulo, { silencioso = false } = {}) {
      if (pensando) return;
      if (!silencioso) adicionar({ de: "voce", texto: rotulo || pergunta });
      const cfg = await config();
      const local = () => opcoes.local(tipo, pergunta);
      if (!ia.pronta || !cfg.botIa) {
        const r = local();
        if (r) adicionar({ de: "bot", ia: "modo básico", ...r });
        if (!ia.pronta && !silencioso && !historico.some((m) => m.dica_ia)) {
          adicionar({ de: "sistema", dica_ia: true, texto: "Sem IA ligada: respondo com os números do chat. Ligue uma IA em Contas & IA no programa pra respostas completas." });
        }
        return;
      }
      pensando = true; desenhar();
      const pedido = { tipo, pergunta, ...opcoes.contexto(),
        historico: historico.filter((m) => m.de !== "sistema").slice(-6).map((m) => ({ de: m.de, texto: m.texto })) };
      const r = await api("bot", {}, pedido);
      pensando = false;
      if (r.ok) adicionar({ de: "bot", texto: r.resposta, nota: r.nota, gancho: r.gancho, titulos: r.titulos, acoes: r.acoes, ia: r.ia });
      else {
        const l = local();
        if (l) adicionar({ de: "bot", ia: "modo básico", ...l });
        adicionar({ de: "sistema", texto: r.msg || "A IA não respondeu." });
      }
    }

    function atualizarIa(info) {
      if (!info) { ia = { pronta: false, rotulo: "programa desligado" }; }
      else ia = info;
      const pl = $(".ia");
      pl.className = "pilula ia " + (ia.pronta ? "ok" : "off");
      pl.querySelector("span").textContent = ia.pronta ? `IA: ${ia.rotulo}` : (info ? "Sem IA — modo básico" : "Programa desligado");
    }

    carregar();
    return {
      perguntar, adicionar, atualizarIa, recarregar: carregar,
      dizer: (m) => adicionar({ de: "bot", ...m }),
      iaPronta: () => ia.pronta,
      pensando: () => pensando,
    };
  }

  window.C916UI = { api, guardar, config, aoMudarConfig, criarPainel, criarBot, el, esc, relogio, ICONES };
})();
