// Popup do ícone da extensão: estado do programa, IA, lives gravando, cortes prontos e configurações.
const PADRAO = { twitch: true, kick: true, youtube: true, botAuto: true, botIa: true };
const $ = (s) => document.querySelector(s);
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function api(acao) {
  return new Promise((ok) => {
    chrome.runtime.sendMessage({ tipo: "api", acao, params: {} }, (r) => ok(chrome.runtime.lastError || !r ? { offline: true } : r));
  });
}
function haQuanto(seg) {
  seg = Math.max(0, Math.floor(seg));
  if (seg < 60) return "agora";
  if (seg < 3600) return `há ${Math.floor(seg / 60)} min`;
  return `há ${Math.floor(seg / 3600)}h${String(Math.floor((seg % 3600) / 60)).padStart(2, "0")}`;
}
const corCalor = (p) => (p >= 100 ? "#ff3030" : p >= 70 ? "#ff8a00" : p >= 40 ? "#ffd400" : "#3ddc84");

async function atualizar() {
  const s = await api("status");
  const con = $("#conexao");
  $("#versao").textContent = `extensão ${chrome.runtime.getManifest().version}` + (s.versao ? ` · programa ${s.versao}` : "");
  if (s.offline) {
    con.className = "pilula off"; con.lastElementChild.textContent = "desligado";
    $("#offline").hidden = false; $("#online").hidden = true;
    return;
  }
  con.className = "pilula ok"; con.lastElementChild.textContent = "conectado";
  $("#offline").hidden = true; $("#online").hidden = false;
  const lives = Object.values(s.lives || {}), prontos = (s.prontos || []).slice().reverse();
  $("#n-lives").textContent = lives.length;
  $("#n-fila").textContent = s.fila || 0;
  $("#n-prontos").textContent = (s.prontos || []).length;

  const ia = s.ia || {}, pia = $("#ia");
  pia.className = "pilula " + (ia.pronta ? "ok" : "off");
  pia.lastElementChild.textContent = ia.pronta ? `IA do bot: ${ia.rotulo}` : "Bot sem IA (modo básico)";
  $("#ia-dica").textContent = ia.pronta ? "" : "Ligue em Contas & IA no programa";

  const boxL = $("#lives");
  boxL.innerHTML = lives.length ? "" : '<div class="vazio">Nenhuma live gravando agora. Abra uma live na Twitch ou Kick.</div>';
  for (const l of lives) {
    const calor = Math.max(0, Math.min(100, l.calor || 0));
    const d = document.createElement("div");
    d.className = "item";
    d.innerHTML = `<span class="pilula rec"><i></i></span><div class="txt"><b>${esc(l.canal)}</b>
      <small>${esc(l.plataforma)} · ${haQuanto(Date.now() / 1000 - l.desde)} · ${l.cortes} corte(s)</small>
      ${typeof l.calor === "number" ? `<div class="termo"><div style="width:${calor}%;background:${corCalor(calor)}"></div></div>` : ""}</div>`;
    if (l.url) {
      const a = document.createElement("button");
      a.className = "link"; a.textContent = "abrir";
      a.onclick = () => chrome.tabs.create({ url: l.url });
      d.appendChild(a);
    }
    boxL.appendChild(d);
  }
  const boxP = $("#prontos");
  boxP.innerHTML = prontos.length ? "" : '<div class="vazio">Nenhum corte pronto nesta sessão do monitor.</div>';
  for (const p of prontos.slice(0, 5)) {
    const d = document.createElement("div");
    d.className = "item";
    d.innerHTML = `<span>✅</span><div class="txt"><b>${esc(p.titulo || p.arquivo)}</b>
      <small>${esc(p.canal || "")}${p.quando ? " · " + haQuanto(Date.now() / 1000 - p.quando) : ""}</small></div>`;
    boxP.appendChild(d);
  }
}

async function configuracoes() {
  const { cfg } = await chrome.storage.local.get(["cfg"]);
  const atual = { ...PADRAO, ...(cfg || {}) };
  document.querySelectorAll("[data-cfg]").forEach((c) => {
    c.checked = !!atual[c.dataset.cfg];
    c.onchange = async () => {
      const { cfg: agora } = await chrome.storage.local.get(["cfg"]);
      await chrome.storage.local.set({ cfg: { ...PADRAO, ...(agora || {}), [c.dataset.cfg]: c.checked } });
    };
  });
}

$("#painel").onclick = () => chrome.tabs.create({ url: "http://localhost:8765/painel" });
configuracoes();
atualizar();
setInterval(atualizar, 4000);
