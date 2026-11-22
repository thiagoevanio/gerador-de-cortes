"""
Galeria no celular — abre no navegador do celular (mesmo Wi-Fi) pra assistir, aprovar e postar.
Sem Telegram, sem nuvem, sem IA: é um servidorzinho no próprio PC, protegido por PIN.

    python celular.py            (ou o botão "📱 Celular" na aba Galeria)
"""
import base64
import json
import mimetypes
import secrets
import socket
import subprocess
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PASTA = Path(__file__).resolve().parent
BASE = PASTA / "cortes_prontos"
PORTA = 8766
IGNORAR = ("_trabalho", "_descartados", ".miniaturas", "_edicao")
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_servidor = None
_estado = {"pin": None, "url": None, "tarefas": {}, "sessoes": set()}
# chute de PIN: depois de ERROS_MAX erros seguidos, NINGUÉM entra por BLOQUEIO_S segundos (nem com o PIN
# certo — senão quem chuta em paralelo acertaria do mesmo jeito)
ERROS_MAX, BLOQUEIO_S = 5, 300
_tentativas = {"erros": 0, "ate": 0.0}
_TRAVA_PIN = threading.Lock()


def conferir_pin(pin: str):
    """True (entrou), False (PIN errado) ou o nº de segundos que falta do bloqueio."""
    with _TRAVA_PIN:
        agora = time.time()
        if _tentativas["ate"] > agora:
            return int(_tentativas["ate"] - agora) + 1
        if _estado["pin"] and secrets.compare_digest(str(pin), _estado["pin"]):
            _tentativas["erros"] = 0
            return True
        _tentativas["erros"] += 1
        if _tentativas["erros"] >= ERROS_MAX:
            _tentativas.update(erros=0, ate=agora + BLOQUEIO_S)
        return False


def pin_novo() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def ip_local():
    """IP do PC na rede de casa (o que o celular usa pra achar ele)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))          # não manda nada, só descobre a placa de rede usada
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _id(v: Path):
    return base64.urlsafe_b64encode(str(v.relative_to(BASE)).encode()).decode().rstrip("=")


def _video(ident):
    try:
        rel = base64.urlsafe_b64decode(ident + "=" * (-len(ident) % 4)).decode()
        v = (BASE / rel).resolve()
    except Exception:
        return None
    if BASE.resolve() not in v.parents or v.suffix.lower() != ".mp4" or not v.exists() \
            or any(p in v.parts for p in IGNORAR):
        return None
    return v


def _ler(v):
    import postagem
    return postagem.ler_ficha(v)


def _salvar(v, ficha):
    import postagem
    postagem.salvar_ficha(v, ficha)


def listar():
    if not BASE.exists():
        return []
    vids = [v for v in BASE.rglob("*.mp4") if not any(p in v.parts for p in IGNORAR)]
    vids.sort(key=lambda v: v.stat().st_mtime, reverse=True)
    import postagem
    saida = []
    for v in vids[:80]:
        f = _ler(v)
        saida.append({
            "id": _id(v), "titulo": f.get("titulo") or v.stem, "pergunta": f.get("pergunta", ""),
            "nota": f.get("nota"), "perfil": f.get("perfil") or "Padrão", "status": f.get("status", "novo"),
            "youtube": bool(f.get("youtube_id") or f.get("youtube_quando")), "tiktok": bool(f.get("tiktok")),
            "parte": f.get("parte"), "layout": f.get("layout"), "variante": f.get("variante"),
            "legenda": postagem.legenda_post(f, "tiktok"),
            "quando": f.get("youtube_quando", "")[:16].replace("T", " "),
            "tarefa": _estado["tarefas"].get(_id(v), ""),
            "resumo": str(f.get("resumo") or "")[:200],
            "musica": bool((f.get("musica_de_fundo") or {}).get("provavel")),
        })
    return saida


def miniatura(v: Path):
    pasta = BASE / ".miniaturas"
    pasta.mkdir(parents=True, exist_ok=True)
    capa = v.with_suffix(".capa.jpg")
    marca = int(max(v.stat().st_mtime, capa.stat().st_mtime if capa.exists() else 0))
    m = pasta / f"cel_{v.stem[:60]}_{marca}.jpg"
    if not m.exists() and capa.exists():           # a capa escolhida vira a miniatura
        try:
            from PIL import Image
            Image.open(capa).convert("RGB").resize((270, 480)).save(m, quality=80)
        except Exception:
            pass
    if not m.exists():
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1.5", "-i", str(v), "-frames:v", "1",
                        "-vf", "scale=270:480", "-q:v", "5", str(m)], creationflags=SEM_JANELA)
    return m


def _postar_youtube(v: Path):
    import postagem
    ident = _id(v)
    _estado["tarefas"][ident] = "enviando pro YouTube..."
    try:
        msgs = []
        postagem.postar_youtube(v, log=msgs.append)
        _estado["tarefas"][ident] = (msgs[-1] if msgs else "✅ agendado")[:120]
    except Exception as e:
        _estado["tarefas"][ident] = f"❌ {str(e)[:120]}"


def _descartar(v: Path):
    destino = BASE / "_descartados"
    destino.mkdir(parents=True, exist_ok=True)
    for ext in (".mp4", ".json", ".txt", ".srt", ".capa.jpg", ".qualidade.json", ".transcricao.json"):
        arq = v.with_suffix(ext)
        if arq.exists():
            alvo = destino / arq.name
            if alvo.exists():
                alvo.unlink()
            arq.replace(alvo)


PAGINA = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Cortes</title>
<style>
:root{--f:#111216;--c:#1d1f26;--t:#f3f3f5;--g:#9a9cab;--v:#e3262e;--ok:#25c26e}
*{box-sizing:border-box}body{margin:0;background:var(--f);color:var(--t);font:15px system-ui,sans-serif}
header{position:sticky;top:0;background:var(--f);padding:12px 16px;display:flex;gap:8px;align-items:center;z-index:2}
h1{font-size:18px;margin:0;flex:1}select,button{font:inherit}
select{background:var(--c);color:var(--t);border:0;border-radius:10px;padding:8px}
main{padding:0 12px 40px;display:grid;gap:12px}
.card{background:var(--c);border-radius:16px;overflow:hidden}
.topo{display:flex;gap:12px;padding:12px}
.topo img{width:96px;height:170px;object-fit:cover;border-radius:10px;background:#000;flex:none}
.info{min-width:0}.tit{font-weight:700;margin:0 0 6px;line-height:1.25}
.sel{display:flex;flex-wrap:wrap;gap:4px;margin:6px 0}.sel span{background:#2b2e38;color:var(--g);border-radius:20px;padding:2px 8px;font-size:12px}
.sel .ok{background:#163d2a;color:#7ff0b0}.sel .alerta{background:#4a3a10;color:#ffd866}
video{width:100%;max-height:75vh;background:#000;display:block}
.bts{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:0 12px 12px}
.bts button,.bts a{border:0;border-radius:12px;padding:12px 8px;background:#2b2e38;color:var(--t);text-align:center;text-decoration:none}
.bts .yt{background:var(--v)}.bts .ok{background:var(--ok);color:#06210f}
.msg{padding:0 12px 12px;color:var(--g);font-size:13px}
.pin{max-width:320px;margin:20vh auto;text-align:center;padding:16px}
.pin input{width:100%;font-size:32px;text-align:center;letter-spacing:12px;padding:12px;border-radius:12px;border:0;background:var(--c);color:var(--t)}
.pin button{margin-top:12px;width:100%;padding:14px;border:0;border-radius:12px;background:var(--v);color:#fff;font-size:17px}
</style></head><body>__CORPO__</body></html>"""

CORPO_PIN = """<form class="pin" method="post" action="/entrar"><h2>🔒 Galeria de cortes</h2>
<p style="color:#9a9cab">Digite o PIN que aparece no PC.</p>
<input name="pin" inputmode="numeric" maxlength="6" autofocus><button>Entrar</button>__ERRO__</form>"""

CORPO_APP = """<header><h1>✂ Cortes</h1><select id="filtro" onchange="desenhar()">
<option value="rev">Para revisar</option><option value="post">Postados</option><option value="todos">Todos</option>
</select></header><main id="lista"></main>
<script>
let itens=[];
async function carregar(){const r=await fetch('/api/lista');if(r.status==401){location.reload();return}
itens=await r.json();desenhar()}
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function desenhar(){const f=document.getElementById('filtro').value;const L=document.getElementById('lista');
const vis=itens.filter(i=>{const p=i.youtube||i.tiktok||i.status=='postado';return f=='todos'||(f=='post'?p:!p)});
if(!vis.length){L.innerHTML='<p style="color:#9a9cab;text-align:center;margin-top:30px">Nada por aqui.</p>';return}
L.innerHTML=vis.map(i=>`<div class="card" id="c_${i.id}"><div class="topo"><img loading="lazy" src="/thumb/${i.id}" onclick="tocar('${i.id}')">
<div class="info"><p class="tit">${esc(i.titulo)}</p><div class="sel">
${i.nota!=null?`<span>⭐ ${i.nota}</span>`:''}<span>${esc(i.perfil)}</span>
${i.parte?`<span>Parte ${i.parte}</span>`:''}${i.layout&&i.layout!='normal'?`<span>${i.layout}</span>`:''}
${i.variante?`<span>versão ${i.variante}</span>`:''}${i.status=='aprovado'?'<span class="ok">✓ aprovado</span>':''}
${i.youtube?`<span class="ok">YouTube ${esc(i.quando)}</span>`:''}${i.tiktok?'<span class="ok">TikTok</span>':''}
${i.musica?'<span class="alerta">🎵 música de fundo?</span>':''}</div>
<div style="color:#9a9cab;font-size:13px">${esc(i.pergunta)}</div>
${i.resumo?`<div style="color:#c9cad3;font-size:12px;margin-top:6px">💬 ${esc(i.resumo)}</div>`:''}</div></div>
<div id="v_${i.id}"></div><div class="bts">
<button onclick="tocar('${i.id}')">▶ Assistir</button><a href="/baixar/${i.id}" download>⬇ Baixar</a>
<button onclick="copiar('${i.id}')">📋 Copiar legenda</button>
<button class="ok" onclick="acao('${i.id}','aprovar')">✓ Aprovar</button>
<button class="yt" onclick="if(confirm((i_musica('${i.id}')?'⚠ Parece ter música de fundo: música com direitos pode mutar ou bloquear no YouTube.\n\n':'')+'Agendar no próximo horário livre do YouTube?'))acao('${i.id}','youtube')">▶ YouTube</button>
<button onclick="acao('${i.id}','tiktok')">✔ Postei no TikTok</button>
<button style="grid-column:span 2;background:#3a1d20" onclick="if(confirm('Descartar este corte?'))acao('${i.id}','descartar')">🗑 Descartar</button>
</div><div class="msg">${esc(i.tarefa)}</div></div>`).join('')}
function i_musica(id){const i=itens.find(x=>x.id==id);return i&&i.musica}
function tocar(id){const d=document.getElementById('v_'+id);
d.innerHTML=d.innerHTML?'':`<video src="/video/${id}" controls autoplay playsinline></video>`}
function copiar(id){const i=itens.find(x=>x.id==id);const t=document.createElement('textarea');t.value=i.legenda;
document.body.appendChild(t);t.select();try{document.execCommand('copy');alert('Legenda copiada! Agora é só colar no TikTok.')}
catch(e){prompt('Copie a legenda:',i.legenda)}t.remove()}
async function acao(id,a){await fetch('/api/'+a+'?id='+id,{method:'POST'});setTimeout(carregar,a=='youtube'?1500:200)}
carregar();setInterval(carregar,15000);
</script>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _logado(self):
        c = SimpleCookie(self.headers.get("Cookie", ""))
        return "sessao" in c and c["sessao"].value in _estado["sessoes"]

    def _enviar(self, codigo, corpo, tipo="text/html; charset=utf-8", extra=None):
        dados = corpo.encode() if isinstance(corpo, str) else corpo
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(dados)

    def _pagina(self, corpo):
        self._enviar(200, PAGINA.replace("__CORPO__", corpo))

    def do_GET(self):
        url = urlparse(self.path)
        if not self._logado():
            if url.path.startswith(("/api/", "/thumb/", "/video/", "/baixar/")):
                return self._enviar(401, "PIN")
            return self._pagina(CORPO_PIN.replace("__ERRO__", ""))
        if url.path == "/":
            return self._pagina(CORPO_APP)
        if url.path == "/api/lista":
            return self._enviar(200, json.dumps(listar(), ensure_ascii=False), "application/json; charset=utf-8")
        partes = url.path.strip("/").split("/", 1)
        if len(partes) == 2:
            v = _video(partes[1])
            if not v:
                return self._enviar(404, "não achei")
            if partes[0] == "thumb":
                m = miniatura(v)
                return self._enviar(200, m.read_bytes() if m.exists() else b"", "image/jpeg")
            if partes[0] in ("video", "baixar"):
                return self._arquivo(v, baixar=partes[0] == "baixar")
        self._enviar(404, "não achei")

    def _arquivo(self, v: Path, baixar=False):
        """Manda o vídeo em pedaços (Range) — é o que deixa o celular tocar e avançar o vídeo."""
        tam = v.stat().st_size
        ini, fim = 0, tam - 1
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].split(",")[0].partition("-")
            try:
                if a:
                    ini = int(a)
                    fim = int(b) if b else tam - 1
                else:
                    ini = max(0, tam - int(b))
            except ValueError:
                ini, fim = 0, tam - 1
            fim = min(fim, tam - 1)
            if ini > fim:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{tam}")
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {ini}-{fim}/{tam}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(v.name)[0] or "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(fim - ini + 1))
        if baixar:
            from urllib.parse import quote
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(v.name)}")
        self.end_headers()
        try:
            with open(v, "rb") as f:
                f.seek(ini)
                falta = fim - ini + 1
                while falta > 0:
                    bloco = f.read(min(256 * 1024, falta))
                    if not bloco:
                        break
                    self.wfile.write(bloco)
                    falta -= len(bloco)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        url = urlparse(self.path)
        tam = int(self.headers.get("Content-Length") or 0)
        corpo = self.rfile.read(min(tam, 10000)).decode("utf-8", "ignore") if tam else ""
        if url.path == "/entrar":
            pin = parse_qs(corpo).get("pin", [""])[0].strip()
            ok = conferir_pin(pin)
            if ok is not True and ok is not False:
                return self._pagina(CORPO_PIN.replace("__ERRO__", f'<p style="color:#ff6b6b">Muitas tentativas erradas. '
                                                                  f'Espere {ok // 60 + 1} min.</p>'))
            if ok:
                sessao = secrets.token_urlsafe(24)
                _estado["sessoes"].add(sessao)
                return self._enviar(303, "", extra={
                    "Location": "/", "Set-Cookie": f"sessao={sessao}; Path=/; Max-Age=2592000; HttpOnly; SameSite=Strict"})
            time.sleep(1.0)                               # dificulta chute de PIN
            return self._pagina(CORPO_PIN.replace("__ERRO__", '<p style="color:#ff6b6b">PIN errado.</p>'))
        if not self._logado():
            return self._enviar(401, "PIN")
        v = _video(parse_qs(url.query).get("id", [""])[0])
        if not v:
            return self._enviar(404, "não achei")
        acao = url.path.rsplit("/", 1)[-1]
        f = _ler(v)
        if acao == "aprovar":
            f["status"] = "aprovado"
            _salvar(v, f)
        elif acao == "tiktok":
            f["tiktok"] = True
            f["status"] = "postado"
            _salvar(v, f)
        elif acao == "youtube":
            if f.get("youtube_id") or f.get("youtube_quando"):
                _estado["tarefas"][_id(v)] = "já foi pro YouTube."
            else:
                threading.Thread(target=_postar_youtube, args=(v,), daemon=True).start()
        elif acao == "descartar":
            _descartar(v)
        else:
            return self._enviar(404, "?")
        self._enviar(200, "ok", "text/plain")


def iniciar(pin=None):
    """Liga o servidor (se já não estiver ligado). Devolve (url, pin)."""
    global _servidor
    if _servidor:
        return _estado["url"], _estado["pin"]
    _estado["pin"] = pin or pin_novo()
    _servidor = ThreadingHTTPServer(("0.0.0.0", PORTA), Handler)
    threading.Thread(target=_servidor.serve_forever, daemon=True).start()
    _estado["url"] = f"http://{ip_local()}:{PORTA}"
    return _estado["url"], _estado["pin"]


def parar():
    global _servidor
    if _servidor:
        _servidor.shutdown()
        _servidor.server_close()
        _servidor = None


def qr_png(texto, destino: Path, tamanho=240):
    """QR code pra apontar a câmera do celular (precisa da biblioteca qrcode; se não tiver, None)."""
    try:
        import qrcode
    except ImportError:
        return None
    img = qrcode.make(texto).convert("RGB").resize((tamanho, tamanho))
    img.save(destino)
    return destino


if __name__ == "__main__":
    url, pin = iniciar()
    print(f"Abra no celular (mesmo Wi-Fi): {url}\nPIN: {pin}\n(Ctrl+C pra parar)")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        parar()
