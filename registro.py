"""Histórico de análises em disco (JSON Lines, append-only).

Cada análise vira uma linha no arquivo .hist/analises.jsonl. Sobrevive a
recarregar a página (enquanto o processo/servidor estiver vivo). Em nuvem o
disco é efêmero — some num redeploy/reboot —, mas dura a sessão do servidor.

Tudo best-effort: se o disco falhar, o painel segue funcionando sem o histórico.
"""
import json
import os

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".hist")
ARQ = os.path.join(PASTA, "analises.jsonl")
MAX_LINHAS = 500  # limite para o arquivo não crescer sem fim


def registrar(item):
    """Acrescenta uma análise ao histórico (dict simples e serializável)."""
    try:
        os.makedirs(PASTA, exist_ok=True)
        with open(ARQ, "a", encoding="utf-8") as f:
            f.write(json.dumps(dict(item), ensure_ascii=False) + "\n")
        _aparar()
    except Exception:
        pass


def listar(limite=100):
    """Devolve as análises mais recentes primeiro (lista de dicts)."""
    try:
        with open(ARQ, "r", encoding="utf-8") as f:
            linhas = [json.loads(ln) for ln in f if ln.strip()]
        return list(reversed(linhas))[:limite]
    except Exception:
        return []


def limpar():
    """Apaga todo o histórico."""
    try:
        if os.path.exists(ARQ):
            os.remove(ARQ)
    except Exception:
        pass


def _aparar():
    """Mantém só as últimas MAX_LINHAS linhas do arquivo."""
    try:
        with open(ARQ, "r", encoding="utf-8") as f:
            linhas = f.readlines()
        if len(linhas) > MAX_LINHAS:
            with open(ARQ, "w", encoding="utf-8") as f:
                f.writelines(linhas[-MAX_LINHAS:])
    except Exception:
        pass
