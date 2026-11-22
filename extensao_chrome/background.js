// Ponte entre as páginas (Twitch/Kick/YouTube) e o programa no seu PC (porta 8765).
const BASE = "http://127.0.0.1:8765";
const OFF = { ok: false, offline: true, msg: "Programa desligado. Abra o Gerador de Cortes e clique em LIGAR MONITOR." };

let tokenSessao = null;
let notificando = Promise.resolve();
async function api(acao, params = {}, corpo = null, reconectar = true) {
  const permitidas = new Set(["status", "gravar", "cortar", "gerar", "nota", "momento", "chat", "tarefa", "bot", "ia_momentos", "instagram"]);
  if (!permitidas.has(acao)) return { ok: false, msg: "Ação inválida." };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 110000);
  try {
    if (!tokenSessao && acao !== "status") {
      const sessao = await fetch(`${BASE}/sessao`, { signal: controller.signal });
      if (sessao.status === 403) {          // o programa não reconheceu esta extensão (ID diferente)
        const e = await sessao.json().catch(() => ({}));
        return { ok: false, offline: true, msg: e.msg || OFF.msg };
      }
      if (!sessao.ok) throw new Error("Sessão indisponível");
      tokenSessao = (await sessao.json()).token;
    }
    const url = `${BASE}/${acao}?${new URLSearchParams(params).toString()}`;
    const r = await fetch(url, {
      method: acao === "status" ? "GET" : "POST",
      headers: { "Content-Type": "application/json", "X-Cortes-Token": tokenSessao || "" },
      ...(corpo ? { body: JSON.stringify(corpo) } : {}), signal: controller.signal
    });
    if (r.status === 403 && reconectar) {
      tokenSessao = null;
      return await api(acao, params, corpo, false);
    }
    if (!r.ok) {
      const erro = await r.json().catch(() => ({}));
      return { ok: false, ...(r.status === 403 ? { offline: true } : {}), msg: erro.msg || `Erro HTTP ${r.status}` };
    }
    return await r.json();
  } finally { clearTimeout(timer); }
}

// avisa quando um corte novo fica pronto (sem repetir aviso entre abas)
async function verificarProntos(status) {
  const prontos = (status && status.prontos) || [];
  const { avisados, iniciado } = await chrome.storage.local.get(["avisados", "iniciado"]);
  const ja = new Set(avisados || []);
  if (!iniciado) {                       // primeira vez: não avisa o que já existia
    await chrome.storage.local.set({ avisados: prontos.map((p) => p.id), iniciado: true });
    return;
  }
  for (const p of prontos) {
    if (ja.has(p.id)) continue;
    ja.add(p.id);
    await chrome.notifications.create(p.id, {
      type: "basic", iconUrl: "icone128.png", priority: 2,
      title: "✅ Corte pronto!" + (p.canal ? ` (${p.canal})` : ""),
      message: (p.titulo || p.arquivo || "") + "\nAbra a Galeria do programa pra revisar e postar.",
    });
  }
  await chrome.storage.local.set({ avisados: [...ja].slice(-60) });
}

chrome.runtime.onMessage.addListener((msg, _rem, responder) => {
  (async () => {
    try {
      if (msg.tipo === "api") {
        const r = await api(msg.acao, msg.params || {}, msg.corpo || null);
        if (msg.acao === "status") notificando = notificando.then(() => verificarProntos(r)).catch(() => {});
        responder(r);
      } else {                                   // formato antigo (youtube.js e painel)
        const { acao, ...resto } = msg;
        responder(await api(acao, resto));
      }
    } catch (e) {
      responder(OFF);
    }
  })();
  return true; // resposta assíncrona
});
