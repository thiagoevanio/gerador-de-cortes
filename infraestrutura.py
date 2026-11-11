"""Gravações atômicas e exclusão mútua entre interface e monitor."""
import json
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

_locks = {}
_guard = threading.Lock()


def salvar_json(caminho, dados):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, nome = tempfile.mkstemp(prefix=caminho.name + '.', suffix='.tmp', dir=caminho.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(nome, caminho)
    finally:
        if os.path.exists(nome):
            os.unlink(nome)


@contextmanager
def exclusividade(caminho, timeout=3600):
    with _guard:
        lock = _locks.setdefault(str(Path(caminho).resolve()), threading.RLock())
    with lock:
        with open(caminho, 'a+b') as arquivo:
            arquivo.seek(0, 2)
            if not arquivo.tell():
                arquivo.write(b'0')
                arquivo.flush()
            inicio = time.monotonic()
            while True:
                try:
                    arquivo.seek(0)
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(arquivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() - inicio > timeout:
                        raise TimeoutError('Outro corte ainda está usando o renderizador.')
                    time.sleep(0.25)
            try:
                yield
            finally:
                arquivo.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(arquivo, fcntl.LOCK_UN)
