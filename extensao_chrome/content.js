// Botões flutuantes na página da Twitch.
const NAO_CANAL = ["directory", "videos", "settings", "subscriptions", "inventory", "wallet",
  "drops", "search", "downloads", "turbo", "p", "jobs", "store", "prime", "friends"];

function canalAtual() {
  const parte = location.pathname.split("/")[1] || "";
  if (!parte || NAO_CANAL.includes(parte.toLowerCase())) return null;
  return parte.toLowerCase();
}

function aviso(texto, ok) {
  let t = document.getElementById("cortes916-aviso");
  if (!t) {
    t = document.createElement("div");
    t.id = "cortes916-aviso";
    document.body.appendChild(t);
  }
  t.textContent = texto;
  t.className = ok ? "ok" : "erro";
  t.style.opacity = "1";
  clearTimeout(t._tempo);
  t._tempo = setTimeout(() => (t.style.opacity = "0"), 6000);
}

function enviar(acao) {
  const canal = canalAtual();
  if (!canal) return aviso("Abra a live de um canal primeiro.", false);
  aviso(acao === "cortar" ? "✂ Pedindo o corte..." : "⏺ Pedindo pra gravar...", true);
  chrome.runtime.sendMessage({ acao, canal }, (r) => {
    if (chrome.runtime.lastError || !r) return aviso("Não consegui falar com o monitor.", false);
    aviso(r.msg, r.ok);
  });
}

function criarBotoes() {
  if (document.getElementById("cortes916")) return;
  const caixa = document.createElement("div");
  caixa.id = "cortes916";
  caixa.innerHTML = `<button class="cortar" title="Corta os últimos segundos (atalho: Alt+C)">✂ CORTAR</button>
                     <button class="gravar" title="Começa a gravar esta live">⏺</button>`;
  caixa.querySelector(".cortar").onclick = () => enviar("cortar");
  caixa.querySelector(".gravar").onclick = () => enviar("gravar");
  document.body.appendChild(caixa);
}

document.addEventListener("keydown", (e) => {
  if (e.altKey && (e.key === "c" || e.key === "C")) enviar("cortar");
});
criarBotoes();
setInterval(criarBotoes, 3000);
