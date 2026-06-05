"""Modulo de analise tecnica — fecha o veredito 2 (so dados tecnicos).

Junta os indicadores do candle atual + open interest + a taxa-base condicional
do historico e fecha um veredito proprio. Nao conversa com o fundamental: isso e
de proposito, para enxergar quando os dois concordam e quando brigam.

CONFIANCA (recalibrada): antes ela saturava em 0.85 sempre que os indicadores
apontavam junto. Agora ela e dominada pela QUALIDADE da evidencia — quanto vies
o historico realmente mostra (edge) e em quantos casos (amostra). Momentum diz a
direcao; amostra e edge dizem o quanto confiar. Amostra pequena derruba a
confianca mesmo com os indicadores todos alinhados.
"""
from dados_binance import obter_candles, obter_futuros
from indicadores import adicionar_indicadores
from historico import taxa_base_condicional

PESO_BASE = {"muito baixa": 0.2, "baixa": 0.6, "media": 1.2, "alta": 2.0}
TETO_CONFIANCA = 0.75  # direcao de 1 periodo e dominada por ruido; teto baixo de proposito


def analise_tecnica(symbol="BTCUSDT", intervalo="1d", horizonte_periodos=1,
                    limite=600, usar_teste=False):
    df, sintetico = obter_candles(symbol, intervalo, limite, usar_teste)
    df = adicionar_indicadores(df)
    futuros = obter_futuros(symbol, usar_teste)
    atual = df.iloc[-1]
    base = taxa_base_condicional(df, horizonte_periodos)

    sinais = []

    def add(nome, voto, peso, detalhe):
        # voto em [-1, 1]: +1 = alta, -1 = baixa, 0 = neutro
        sinais.append({"nome": nome, "voto": voto, "peso": peso, "detalhe": detalhe})

    add("MACD", 1 if atual["macd_hist"] > 0 else -1, 1.0,
        f"histograma {'positivo' if atual['macd_hist'] > 0 else 'negativo'}")
    add("Preco vs SMA50", 1 if atual["close"] > atual["sma50"] else -1, 1.0,
        f"preco {'acima' if atual['close'] > atual['sma50'] else 'abaixo'} da media de 50")
    add("EMA9 vs EMA21", 1 if atual["ema9"] > atual["ema21"] else -1, 0.8,
        f"tendencia de curto prazo de {'alta' if atual['ema9'] > atual['ema21'] else 'baixa'}")

    if atual["rsi"] > 70:
        add("RSI", -0.5, 0.6, f"sobrecomprado ({atual['rsi']:.0f})")
    elif atual["rsi"] < 30:
        add("RSI", 0.5, 0.6, f"sobrevendido ({atual['rsi']:.0f})")
    else:
        add("RSI", 0, 0.3, f"neutro ({atual['rsi']:.0f})")

    lean = (base["pct_alta"] - 0.5) * 2  # -1..1
    add("Historico condicional", lean, PESO_BASE[base["confianca_amostra"]],
        f"{base['pct_alta'] * 100:.0f}% de alta em casos parecidos "
        f"(n={base['n_amostra']}, confianca {base['confianca_amostra']})")

    # Open interest: OI subindo reforca a tendencia de curto prazo; caindo, esvazia.
    oi_var = futuros.get("oi_variacao")
    if oi_var is not None:
        tend = 1 if atual["ema9"] > atual["ema21"] else -1
        if oi_var > 0:
            add("Open interest", tend, 0.5, f"OI subindo {oi_var:+.1f}% reforca a tendencia")
        else:
            add("Open interest", 0, 0.4, f"OI caindo {oi_var:+.1f}% (tendencia perde forca)")

    peso_total = sum(s["peso"] for s in sinais)
    score = sum(s["voto"] * s["peso"] for s in sinais)
    score_norm = score / peso_total if peso_total else 0.0

    if score_norm > 0.1:
        direcao = "cima"
    elif score_norm < -0.1:
        direcao = "baixo"
    else:
        direcao = "indefinido"

    # --- CONFIANCA dominada pela qualidade da evidencia ---
    concordancia_sinais = abs(score_norm)               # 0..1 — o quanto os sinais apontam junto
    edge_hist = abs(base["pct_alta"] - 0.5) * 2          # 0..1 — forca do vies historico
    fator_amostra = min(base["n_amostra"] / 100.0, 1.0)  # 0..1 — amostra pequena => pouca confianca
    base_conf = 0.35 * concordancia_sinais + 0.65 * edge_hist
    confianca = base_conf * (0.4 + 0.6 * fator_amostra)
    confianca = round(min(confianca, TETO_CONFIANCA), 2)

    raciocinio = " | ".join(f"{s['nome']}: {s['detalhe']}" for s in sinais)

    # Série recente de preço (para o mini-gráfico) e variação do último período.
    serie_preco = [round(float(x), 2) for x in df["close"].tail(40)]
    if len(df) >= 2 and float(df["close"].iloc[-2]):
        variacao_pct = round((float(atual["close"]) / float(df["close"].iloc[-2]) - 1) * 100, 2)
    else:
        variacao_pct = 0.0

    return {
        "modulo": "tecnica",
        "direcao": direcao,
        "confianca": confianca,
        "raciocinio": raciocinio,
        "n_amostra": base["n_amostra"],
        "preco_atual": round(float(atual["close"]), 2),
        "variacao_pct": variacao_pct,
        "serie_preco": serie_preco,
        "indicadores": {
            "rsi": round(float(atual["rsi"]), 1),
            "macd_hist": round(float(atual["macd_hist"]), 2),
            "sma50": round(float(atual["sma50"]), 2),
            "ema9": round(float(atual["ema9"]), 2),
            "ema21": round(float(atual["ema21"]), 2),
        },
        "futuros": futuros,
        "dados_sinteticos": sintetico,
    }
