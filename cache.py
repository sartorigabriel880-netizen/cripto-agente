"""Cache em disco simples (JSON) com expiracao por tempo (TTL).

Serve para NAO repetir — e nao pagar de novo — a busca do modulo fundamental
quando voce roda o mesmo ativo varias vezes seguidas dentro de um intervalo.
Os arquivos ficam numa pasta oculta .cache ao lado dos scripts.
"""
import hashlib
import json
import os
import time

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")


def _caminho(chave):
    nome = hashlib.sha1(chave.encode("utf-8")).hexdigest()[:16]
    return os.path.join(PASTA, f"{nome}.json")


def cache_get(chave, ttl_segundos):
    """Devolve o valor guardado se existir e nao tiver expirado; senao, None."""
    if not ttl_segundos or ttl_segundos <= 0:
        return None
    try:
        with open(_caminho(chave), "r", encoding="utf-8") as f:
            registro = json.load(f)
    except Exception:
        return None
    if time.time() - registro.get("ts", 0) > ttl_segundos:
        return None
    return registro.get("valor")


def cache_set(chave, valor):
    """Guarda o valor em disco com o horario atual (best-effort)."""
    try:
        os.makedirs(PASTA, exist_ok=True)
        with open(_caminho(chave), "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "valor": valor}, f, ensure_ascii=False)
    except Exception:
        pass
