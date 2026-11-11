"""Guarda segredos (ex.: chave do Gemini) criptografados pela proteção de dados do Windows (DPAPI).

O valor salvo no config.json vira "dpapi:<base64>" e só a SUA conta do Windows, neste PC, consegue abrir.
Copiar o config.json pra outro PC/usuário não leva a chave junto (basta colar a chave de novo lá).
Fora do Windows (ou se a proteção falhar), o valor fica como estava — nada quebra.
"""
import base64
import sys

PREFIXO = "dpapi:"


def _dpapi(dados: bytes, proteger: bool):
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(dados, len(dados))
    entrada = BLOB(len(dados), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    saida = BLOB()
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    func = crypt32.CryptProtectData if proteger else crypt32.CryptUnprotectData
    # 0x01 = CRYPTPROTECT_UI_FORBIDDEN (nunca abre janela)
    if not func(ctypes.byref(entrada), None, None, None, None, 0x01, ctypes.byref(saida)):
        raise OSError("DPAPI falhou")
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(saida.pbData, ctypes.c_void_p))


def disponivel():
    return sys.platform == "win32"


def protegido(valor):
    return isinstance(valor, str) and valor.startswith(PREFIXO)


def proteger(texto):
    """Texto puro → 'dpapi:...'. Vazio, já protegido ou sem DPAPI: devolve como veio."""
    if not isinstance(texto, str) or not texto.strip() or protegido(texto) or not disponivel():
        return texto
    try:
        return PREFIXO + base64.b64encode(_dpapi(texto.strip().encode("utf-8"), True)).decode("ascii")
    except Exception:
        return texto


def revelar(valor):
    """'dpapi:...' → texto puro ("" se não der pra abrir: outro PC/usuário). Texto puro passa direto."""
    if not protegido(valor):
        return valor if isinstance(valor, str) else ""
    if not disponivel():
        return ""
    try:
        return _dpapi(base64.b64decode(valor[len(PREFIXO):]), False).decode("utf-8")
    except Exception:
        return ""
