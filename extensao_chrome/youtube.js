// Botões em vídeos do YouTube: marca início e fim no ponto atual do vídeo e manda gerar o corte.
let inicio = null, fim = null;

function fmt(s) {
  if (s == null) return "--:--";
  s = Math.floor(s);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), ss = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

function aviso(texto, ok) {
  let t = document.getElementById("cortes916-aviso");
  if (!t) { t = document.createElement("div"); t.id = "cortes916-aviso"; document.body.appendChild(t); }
  t.textContent = texto; t.className = ok ? "ok" : "erro"; t.style.opacity = "1";
  clearTimeout(t._tempo); t._tempo = setTimeout(() => (t.style.opacity = "0"), 6000);
}

function linkLimpo() {
  const u = new URL(location.href);
  const id = u.searchParams.get("v") || (u.pathname.startsWith("/shorts/") ? u.pathname.split("/")[2] : null);
  return id ? `https://www.youtube.com/watch?v=${id}` : null;
}

function atualizar() {
  const caixa = document.getElementById("cortes916");
  if (!caixa) return;
  caixa.querySelector(".tempos").textContent = `${fmt(inicio)} → ${fmt(fim)}`;
}

function criar() {
  const naPagina = !!linkLimpo();
  let caixa = document.getElementById("cortes916");
  if (!naPagina) { if (caixa) caixa.remove(); return; }
  if (caixa) return;
  caixa = document.createElement("div");
  caixa.id = "cortes916";
  caixa.innerHTML = `<button class="gravar ini" title="Marca o início no ponto atual (Alt+I)">⏱ Início</button>
    <button class="gravar fimb" title="Marca o fim no ponto atual (Alt+F)">⏱ Fim</button>
    <span class="tempos">--:-- → --:--</span>
    <button class="cortar" title="Manda gerar o corte (Alt+G)">✂ GERAR</button>`;
  caixa.querySelector(".ini").onclick = marcarInicio;
  caixa.querySelector(".fimb").onclick = marcarFim;
  caixa.querySelector(".cortar").onclick = gerar;
  document.body.appendChild(caixa);
}

const video = () => document.querySelector("video.html5-main-video") || document.querySelector("video");
const anuncio = () => !!document.querySelector(".html5-video-player.ad-showing, .html5-video-player.ad-interrupting");
function marcarInicio() { if (anuncio()) return aviso("Espere o anúncio terminar para marcar o vídeo.", false); const v = video(); if (v) { inicio = v.currentTime; if (fim != null && fim <= inicio) fim = null; atualizar(); } }
function marcarFim() { if (anuncio()) return aviso("Espere o anúncio terminar para marcar o vídeo.", false); const v = video(); if (v) { fim = v.currentTime; atualizar(); } }

function gerar() {
  const url = linkLimpo();
  if (inicio == null || fim == null || fim <= inicio) return aviso("Marque o início e depois o fim.", false);
  aviso("✂ Mandando pro gerador...", true);
  chrome.runtime.sendMessage({ acao: "gerar", url, ini: inicio.toFixed(3), fim: fim.toFixed(3) }, (r) => {
    if (chrome.runtime.lastError || !r) return aviso("Não consegui falar com o monitor.", false);
    aviso(r.msg, r.ok);
    if (r.ok) { inicio = fim = null; atualizar(); }
  });
}

document.addEventListener("keydown", (e) => {
  if (!e.altKey) return;
  const k = e.key.toLowerCase();
  if (k === "i") marcarInicio(); else if (k === "f") marcarFim(); else if (k === "g") gerar();
});
let ultimoLink = null;
setInterval(() => {
  const l = linkLimpo();
  if (l !== ultimoLink) { ultimoLink = l; inicio = fim = null; }
  criar(); atualizar();
}, 1500);
