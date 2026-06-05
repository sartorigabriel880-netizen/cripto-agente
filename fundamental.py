"""Modulo de analise fundamental (ntc/info) — usa Claude + web_search.

macro + micro + noticias + redes sociais + comparacao com periodos anteriores,
fechando o veredito 'ntc/info'. Chama o Claude com a ferramenta web_search.

CACHE: o resultado e guardado em disco por um tempo (padrao 60 min). Se voce
rodar o mesmo ativo de novo dentro desse intervalo, ele reusa o resultado e NAO
paga a busca de novo. Controle com --cache-min (0 desliga) e --sem-cache.

Requisitos:
  pip install anthropic
  export ANTHROPIC_API_KEY=...            (sua chave)
  export MODELO_CLAUDE=claude-sonnet-4-6  (opcional; este e o padrao)

Sem a chave, o modulo devolve 'indefinido' de forma graciosa.
"""
import os

from cache import cache_get, cache_set

NOMES = {
    "BTCUSDT": "Bitcoin (BTC)",
    "ETHUSDT": "Ethereum (ETH)",
    "SOLUSDT": "Solana (SOL)",
    "XRPUSDT": "XRP",
}


def analise_fundamental(symbol="BTCUSDT", horizonte_periodos=1, cache_min=60):
    chave_cache = f"fundamental:{symbol}:{horizonte_periodos}"
    cacheado = cache_get(chave_cache, ttl_segundos=cache_min * 60)
    if cacheado is not None:
        cacheado = dict(cacheado)
        cacheado["do_cache"] = True
        return cacheado

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _indefinido("Sem ANTHROPIC_API_KEY definida — modulo fundamental pulado.")

    try:
        from anthropic import Anthropic
    except ImportError:
        return _indefinido("Pacote 'anthropic' nao instalado (pip install anthropic).")

    modelo = os.environ.get("MODELO_CLAUDE", "claude-sonnet-4-6")
    client = Anthropic(api_key=api_key)

    try:
        resp = client.messages.create(
            model=modelo,
            max_tokens=2000,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
            messages=[{"role": "user", "content": _montar_prompt(symbol, horizonte_periodos)}],
        )
    except Exception as e:
        return _indefinido(f"Falha na chamada a API: {e}")

    dados = _parsear_json(_extrair_texto(resp))
    if dados is None:
        return _indefinido("Nao consegui parsear o JSON retornado pelo modelo.")

    resultado = {
        "modulo": "fundamental",
        "direcao": dados.get("direcao", "indefinido"),
        "confianca": _num(dados.get("confianca", 0.0)),
        "raciocinio": dados.get("raciocinio", ""),
        "fontes": dados.get("fontes", []),
        "n_amostra": int(dados.get("episodios_analogos", 0) or 0),
        "do_cache": False,
    }
    cache_set(chave_cache, resultado)  # so guarda resultado bom (nao guarda 'indefinido')
    return resultado


def _montar_prompt(symbol, horizonte):
    ativo = NOMES.get(symbol, symbol)
    return (
        f"Voce e um analista de mercado. Pesquise na web as informacoes MAIS RECENTES "
        f"que podem afetar o preco de {ativo} no horizonte de {horizonte} periodo(s) a frente.\n\n"
        f"Cubra:\n"
        f"1. Macro: decisoes de juros / Fed, inflacao (CPI), dolar (DXY), bolsa.\n"
        f"2. Noticias do ativo e do mercado cripto (regulacao, ETFs, hacks, on-chain).\n"
        f"3. Sentimento de redes sociais / clima geral do mercado.\n"
        f"4. Comparacao historica: ja houve cenarios parecidos? O que o preco fez depois? "
        f"Quantos episodios comparaveis voce encontrou?\n\n"
        f"Seja honesto: se a noticia ja esta precificada, diga. Se nao ha episodios analogos "
        f"claros (amostra pequena), a confianca deve ser BAIXA. Direcao de curto prazo e incerta.\n\n"
        f"Responda APENAS com um objeto JSON, sem markdown, neste formato exato:\n"
        f'{{\n'
        f'  "direcao": "cima" | "baixo" | "indefinido",\n'
        f'  "confianca": <numero de 0 a 1>,\n'
        f'  "raciocinio": "<2-4 frases: impacto liquido + comparacao historica>",\n'
        f'  "fontes": ["<url>", "..."],\n'
        f'  "episodios_analogos": <inteiro: quantos cenarios historicos comparaveis voce achou>\n'
        f'}}'
    )


def _extrair_texto(resp):
    partes = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    return "\n".join(partes).strip()


def _parsear_json(texto):
    if not texto:
        return None
    ini, fim = texto.find("{"), texto.rfind("}")
    if ini == -1 or fim == -1 or fim < ini:
        return None
    try:
        import json
        return json.loads(texto[ini:fim + 1])
    except Exception:
        return None


def _num(v):
    try:
        return round(float(v), 2)
    except Exception:
        return 0.0


def _indefinido(motivo):
    return {
        "modulo": "fundamental",
        "direcao": "indefinido",
        "confianca": 0.0,
        "raciocinio": motivo,
        "fontes": [],
        "n_amostra": 0,
        "do_cache": False,
    }
