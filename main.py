"""Ponto de entrada do agente.

Exemplos:
    python main.py BTCUSDT                  # um ativo, dados reais
    python main.py BTCUSDT ETHUSDT SOLUSDT  # varios de uma vez
    python main.py --todos                  # BTC, ETH, SOL e XRP
    python main.py BTCUSDT --intervalo 4h --horizonte 3
    python main.py BTCUSDT --teste          # dados sinteticos (offline)
    python main.py BTCUSDT --sem-cache      # forca nova busca no fundamental
"""
import argparse

from tecnica import analise_tecnica
from fundamental import analise_fundamental
from sintese import sintetizar

ATIVOS_PADRAO = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]


def _imprimir_veredito(v):
    extra = "   (do cache)" if v.get("do_cache") else ""
    print(f"  direcao    : {v['direcao']}{extra}")
    print(f"  confianca  : {v['confianca']}")
    print(f"  n_amostra  : {v.get('n_amostra', '-')}")
    print(f"  raciocinio : {v['raciocinio']}")
    if v.get("fontes"):
        print(f"  fontes     : {', '.join(v['fontes'][:5])}")


def analisar(symbol, args):
    print(f"\n=== Analise de {symbol} | intervalo {args.intervalo} "
          f"| horizonte {args.horizonte} periodo(s) ===")

    vt = analise_tecnica(symbol, args.intervalo, args.horizonte, args.limite, args.teste)
    cache_min = 0 if args.sem_cache else args.cache_min
    vf = analise_fundamental(symbol, args.horizonte, cache_min=cache_min)
    final = sintetizar(vf, vt)

    if vt.get("dados_sinteticos"):
        print("\n[MODO TESTE] Dados sinteticos — NAO refletem o mercado real.")

    print(f"\nPreco atual : {vt['preco_atual']}")
    print(f"Indicadores : {vt['indicadores']}")
    print(f"Futuros     : {vt['futuros']}")

    print("\n--- Veredito 1 (fundamental / ntc-info) ---")
    _imprimir_veredito(vf)
    print("\n--- Veredito 2 (tecnica) ---")
    _imprimir_veredito(vt)

    print("\n=== VEREDITO FINAL ===")
    print(f"  direcao      : {final['direcao']}")
    print(f"  confianca    : {final['confianca']}")
    print(f"  concordancia : {final['concordancia']}")
    print(f"  resumo       : {final['resumo']}")
    print(f"  aviso        : {final['aviso']}")


def main():
    p = argparse.ArgumentParser(description="Agente de analise de cripto")
    p.add_argument("symbols", nargs="*", default=["BTCUSDT"],
                   help="um ou mais pares, ex.: BTCUSDT ETHUSDT")
    p.add_argument("--todos", action="store_true", help="analisa BTC, ETH, SOL e XRP")
    p.add_argument("--intervalo", default="1d", help="1d, 4h, 1h, 15m...")
    p.add_argument("--horizonte", type=int, default=1, help="quantos periodos a frente")
    p.add_argument("--limite", type=int, default=600, help="quantidade de candles historicos")
    p.add_argument("--teste", action="store_true", help="usa dados sinteticos (offline)")
    p.add_argument("--cache-min", type=int, default=60, dest="cache_min",
                   help="minutos de validade do cache do fundamental (0 desliga)")
    p.add_argument("--sem-cache", action="store_true", dest="sem_cache",
                   help="ignora o cache e forca nova busca")
    args = p.parse_args()

    symbols = ATIVOS_PADRAO if args.todos else (args.symbols or ["BTCUSDT"])
    for sym in symbols:
        analisar(sym.upper(), args)
    print()


if __name__ == "__main__":
    main()
