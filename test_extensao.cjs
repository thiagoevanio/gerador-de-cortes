// Valida o service worker sem rede e sem controlar uma sessão do Chrome.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
(async () => {
  const chamadas = [];
  let listener;
  const contexto = { URLSearchParams, AbortController, setTimeout, clearTimeout,
    chrome: { runtime: { onMessage: { addListener: fn => listener = fn } },
      storage: { local: { get: async () => ({}), set: async () => {} } },
      notifications: { create: async () => 'ok' } },
    fetch: async (url, op = {}) => {
      chamadas.push({url, op});
      return { ok:true, status:200, json:async () => url.endsWith('/sessao') ? { token:'teste' } : {ok:true} };
    }
  };
  vm.createContext(contexto);
  vm.runInContext(fs.readFileSync('extensao_chrome/background.js', 'utf8'), contexto);
  await vm.runInContext("api('cortar', {canal:'teste'})", contexto);
  assert.equal(chamadas[0].url.endsWith('/sessao'), true);
  assert.equal(chamadas[1].op.method, 'POST');
  assert.equal(chamadas[1].op.headers['X-Cortes-Token'], 'teste');
  await vm.runInContext("api('status')", contexto);
  assert.equal(chamadas.at(-1).op.method, 'GET');
  const n = chamadas.length;
  const erro = await vm.runInContext("api('../invalido')", contexto);
  assert.equal(erro.ok, false); assert.equal(chamadas.length, n);
  assert.equal(typeof listener, 'function');
  const live = fs.readFileSync('extensao_chrome/live.js', 'utf8');
  const a = live.indexOf('  function hashDoPlayer(');
  const b = live.indexOf('  // ---------- cortar ----------', a);
  const funcaoHash = live.slice(a, b);
  const rgba = new Uint8ClampedArray(72 * 4);
  for (let i=0;i<72;i++) { rgba[i*4]=rgba[i*4+1]=rgba[i*4+2]=255-i; rgba[i*4+3]=255; }
  const ctx = {drawImage(){},getImageData(){return {data:rgba};}};
  const ambiente = { document:{createElement(){return {getContext(){return ctx;}};}} };
  assert.equal(vm.runInNewContext(funcaoHash+'; hashDoPlayer({})', ambiente),'ffffffffffffffff');
  ctx.getImageData = () => {throw new Error('CORS');};
  assert.equal(vm.runInNewContext(funcaoHash+'; hashDoPlayer({})', ambiente),'');
  console.log('Extensão: sessão, POST, status e lista de ações aprovados.');
})().catch(e => { console.error(e); process.exitCode = 1; });
