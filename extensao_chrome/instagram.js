// Cortes 9:16 — 📥 baixar os reels de um perfil do Instagram, no arquivo ORIGINAL (sem marca d'água).
//  • aparece na página de um perfil (instagram.com/fulano ou /fulano/reels)
//  • rola a aba Reels sozinha juntando os links (o Instagram não deixa programa listar o perfil;
//    no seu navegador, ele mostra) e manda pro programa baixar um por um
//  • o programa abre direto aqui com #c916baixar=N (botão "📥 Reels do Instagram" no programa)
(() => {
  if (window.__c916ig) return;
  window.__c916ig = true;
  const UI = window.C916UI;
  const RESERVADOS = new Set(["explore", "reels", "reel", "p", "tv", "stories", "direct", "accounts", "about",
                              "developer", "legal", "web", "challenge", "emails", "graphql", "api"]);
  let ativo = true, conectado = false, usuarioAtual = null, juntando = false, cancelar = false;
  let trabalho = null, timer = null, quantos = 30, avisoLogin = "";
  // deslogado: o Instagram mostra só uns 12 reels e cobre a página com "entre no Instagram"
  const deslogado = () => !!document.querySelector('a[href*="/accounts/login"]') && !document.querySelector('a[href*="/direct/"]');

  const painel = UI.criarPainel({ subtitulo: "Instagram", chave: "painel:instagram",
                                  abas: [{ id: "baixar", rotulo: "Baixar reels", icone: "baixar" }] });
  const aba = painel.aba("baixar");
  aba.innerHTML = `
    <div class="sec">
      <div class="rot">Reels de <span class="ig-user">@</span></div>
      <div class="cartao">
        <div class="dica" style="margin-bottom:6px">Quantos reels (os mais novos primeiro)</div>
        <div class="seg ig-n">${[12, 30, 60, 150, 500].map((n) => `<button data-v="${n}" class="${n === 30 ? "on" : ""}">${n === 500 ? "Todos" : n}</button>`).join("")}</div>
        <div style="margin-top:10px"><button class="grande b-baixar">📥 BAIXAR REELS</button></div>
        <div class="linha" style="margin-top:8px;justify-content:space-between">
          <span class="dica ig-st">Arquivo original, sem marca d'água. Os que você já baixou não baixam de novo.</span>
        </div>
        <div style="margin-top:8px;display:none" class="ig-barra"><div class="termo"><div class="ig-prog" style="background:var(--verde)"></div></div></div>
        <div style="margin-top:8px;text-align:right"><button class="link b-parar" style="display:none">■ parar</button></div>
      </div>
      <div class="dica" style="margin-top:8px">Salva na pasta <b>reels_instagram/@perfil</b> do programa, com um <b>reels.json</b> com a legenda e a data de cada um. Conta privada: só se você seguir.</div>
    </div>`;
  const $ = (s) => aba.querySelector(s);
  const st = (t, cor = "") => { $(".ig-st").textContent = t; $(".ig-st").style.color = cor; };
  const dormir = (ms) => new Promise((r) => setTimeout(r, ms));

  aba.querySelectorAll(".ig-n button").forEach((b) => (b.onclick = () => {
    aba.querySelectorAll(".ig-n button").forEach((x) => x.classList.toggle("on", x === b));
    quantos = +b.dataset.v;
  }));

  function usuarioDaPagina() {
    const partes = location.pathname.split("/").filter(Boolean);
    if (!partes.length || partes.length > 2 || RESERVADOS.has(partes[0].toLowerCase())) return null;
    if (partes[1] && !["reels", "tagged"].includes(partes[1])) return null;
    return /^[A-Za-z0-9._]{1,30}$/.test(partes[0]) ? partes[0] : null;
  }
  const naAbaReels = () => location.pathname.split("/").filter(Boolean)[1] === "reels";
  function linksDeReels(u) {
    const achados = [];
    document.querySelectorAll('a[href*="/reel/"]').forEach((a) => {
      const h = a.getAttribute("href") || "";
      // só os reels DESTE perfil (a página também mostra sugestões de outras contas)
      if (/\/reel\/[A-Za-z0-9_-]{5,}/.test(h) && (!/^\/[^/]+\/reel\//.test(h) || h.toLowerCase().startsWith(`/${u.toLowerCase()}/`)))
        achados.push(h);
    });
    return achados;
  }

  async function juntar(u, limite) {
    const links = new Set();
    let semNovos = 0;
    window.scrollTo(0, 0);
    await dormir(800);
    while (links.size < limite && semNovos < 6 && !cancelar) {
      if (document.hidden) {               // aba em segundo plano: o Instagram não carrega mais nada
        st("⏸ Volte pra esta aba do Instagram — com ela escondida a página não carrega mais reels.", "#ffd400");
        await dormir(1000);
        continue;
      }
      const antes = links.size;
      linksDeReels(u).forEach((l) => links.add(l));
      st(`🔎 Juntando os reels da página… ${Math.min(links.size, limite)}${limite < 500 ? ` de ${limite}` : ""}`, "#ffd400");
      // vai até o fim da página: é chegando lá que o Instagram carrega a próxima leva
      window.scrollTo(0, document.documentElement.scrollHeight);
      await dormir(1300 + Math.random() * 900);            // espera o Instagram carregar mais
      linksDeReels(u).forEach((l) => links.add(l));
      semNovos = links.size === antes ? semNovos + 1 : 0;
    }
    return [...links].slice(0, limite);
  }

  async function baixar() {
    const u = usuarioDaPagina();
    if (!u || juntando) return;
    if (!conectado) return st("Programa desligado. Abra o Gerador de Cortes e clique em LIGAR MONITOR.", "#ff4d55");
    if (!naAbaReels()) {                                      // a aba Reels só tem vídeo (a de posts tem foto)
      location.href = `https://www.instagram.com/${u}/reels/#c916baixar=${quantos}`;
      return;
    }
    juntando = true; cancelar = false;
    $(".b-baixar").disabled = true;
    $(".b-parar").style.display = "";
    const links = await juntar(u, quantos);
    juntando = false;
    avisoLogin = links.length < quantos && deslogado()
      ? " · Sem login o Instagram só mostra uns 12 reels: entre na sua conta e clique de novo pra pegar o resto (os baixados não repetem)."
      : "";
    if (cancelar) { pronto(); return st("Parado."); }
    if (!links.length) { pronto(); return st("Não achei reels nesse perfil (é privado ou não tem reels?).", "#ff4d55"); }
    st(`📨 Mandando ${links.length} reel(s) pro programa…`);
    const r = await UI.api("instagram", {}, { usuario: u, links });
    if (!r.ok) { pronto(); return st(r.msg || "Não deu certo.", "#ff4d55"); }
    trabalho = r.trabalho;
    desenhar();
    acompanhar();
  }

  function pronto() {
    $(".b-baixar").disabled = false;
    $(".b-baixar").textContent = "📥 BAIXAR REELS";
    $(".b-parar").style.display = "none";
  }

  function desenhar() {
    const t = trabalho;
    if (!t) return;
    const feitos = t.feitos + t.pulados + t.falhas;
    $(".ig-barra").style.display = "";
    $(".ig-prog").style.width = `${Math.round((100 * feitos) / Math.max(1, t.total))}%`;
    if (t.estado === "baixando") {
      $(".b-baixar").disabled = true;
      $(".b-baixar").textContent = "📥 BAIXANDO…";
      $(".b-parar").style.display = "";
      st(`📥 ${feitos} de ${t.total}` + (t.pulados ? ` (${t.pulados} já tinha)` : "") + (t.falhas ? ` · ${t.falhas} falha(s)` : ""), "#ffd400");
    } else {
      pronto();
      st((t.estado === "pronto" && t.feitos + t.pulados > 0 ? "✅ " : "⚠ ") + (t.msg || "") + avisoLogin,
         t.estado === "pronto" && t.feitos + t.pulados > 0 ? "#3ddc84" : "#ff4d55");
      painel.badge("baixar", t.feitos);
    }
  }

  function acompanhar() {
    clearTimeout(timer);
    if (!trabalho || trabalho.estado !== "baixando") return;
    timer = setTimeout(async () => {
      const s = await UI.api("status");
      const t = (s.instagram || []).find((x) => x.id === trabalho.id);
      if (t) { trabalho = t; desenhar(); }
      acompanhar();
    }, 2500);
  }

  $(".b-baixar").onclick = baixar;
  $(".b-parar").onclick = async () => {
    cancelar = true;
    if (trabalho && trabalho.estado === "baixando") await UI.api("instagram", {}, { parar: trabalho.id });
  };

  async function atualizarStatus() {
    if (!ativo || !usuarioDaPagina()) return;
    const s = await UI.api("status");
    conectado = !s.offline;
    painel.status(conectado ? "conectado" : "programa desligado", conectado ? "ok" : "off");
    const t = conectado && (s.instagram || []).find((x) => x.usuario.toLowerCase() === (usuarioAtual || "").toLowerCase());
    if (t && !juntando && (!trabalho || trabalho.id !== t.id || trabalho.estado !== t.estado)) {
      trabalho = t; desenhar(); acompanhar();
    }
  }

  function ciclo() {
    const u = ativo ? usuarioDaPagina() : null;
    if (!u) { painel.remover(); usuarioAtual = null; return; }
    painel.mostrar();
    if (u !== usuarioAtual) {
      usuarioAtual = u; trabalho = null; clearTimeout(timer);
      $(".ig-user").textContent = "@" + u;
      $(".ig-barra").style.display = "none";
      if (!juntando) { pronto(); st("Arquivo original, sem marca d'água. Os que você já baixou não baixam de novo."); }
      atualizarStatus();
      // aberto pelo programa (ou pelo botão em outra aba do perfil): começa sozinho
      const m = location.hash.match(/c916baixar=(\d+)/);
      if (m) {
        quantos = Math.max(1, Math.min(500, +m[1]));
        aba.querySelectorAll(".ig-n button").forEach((x) => x.classList.toggle("on", +x.dataset.v === quantos));
        history.replaceState(null, "", location.pathname);
        setTimeout(async () => { await atualizarStatus(); baixar(); }, 3500);
      }
    }
  }

  if (window.__c916_local) window.__c916_ig = { usuarioDaPagina, linksDeReels, juntar, painel, deslogado };  // testes
  UI.config().then((c) => { ativo = c.instagram !== false; ciclo(); });
  UI.aoMudarConfig((c) => { ativo = c.instagram !== false; ciclo(); });
  setInterval(ciclo, 1500);
  setInterval(atualizarStatus, 8000);
})();
