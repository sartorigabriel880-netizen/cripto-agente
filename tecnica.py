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


def _arred_preco(x):
    """Arredonda preco com casas decimais adaptadas a magnitude. Sem isso,
    moedas muito baratas (ex.: BONK ~$0.00001) virariam 0.00 com round(x, 2)."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if x != x:  # NaN
        return None
    a = abs(x)
    if a >= 1:
        return round(x, 2)
    if a >= 0.01:
        return round(x, 4)
    if a >= 0.0001:
        return round(x, 6)
    return round(x, 8)


def analise_tecnica(symbol="BTCUSDT", intervalo="1d", horizonte_periodos=1,
                    limite=600, usar_teste=False, incluir_futuros=True):
    df, sintetico = obter_candles(symbol, intervalo, limite, usar_teste)
    df = adicionar_indicadores(df)
    # incluir_futuros=False acelera a 'visao geral' (varios ativos de uma vez),
    # pulando as chamadas de funding/long-short/open interest.
    futuros = obter_futuros(symbol, usar_teste) if incluir_futuros else {
        "sintetico": sintetico, "funding_rate": None, "long_short_ratio": None,
        "open_interest": None, "oi_variacao": None, "oi_fonte": None}
    return _avaliar(df, horizonte_periodos, futuros, sintetico)


def _avaliar(df, horizonte_periodos, futuros, sintetico=False, base=None, leve=False):
    """Decide o veredito técnico a partir de um DataFrame JÁ com indicadores.

    Separado de analise_tecnica de propósito: o backtest reusa EXATAMENTE esta
    lógica em fatias históricas (o df até o ponto i), sem espiar o futuro.

    `base`: taxa-base condicional já calculada (o backtest passa pré-computada,
    por desempenho). `leve=True`: pula a construção das séries do gráfico (o
    backtest não precisa) — a DECISÃO em si é idêntica.
    """
    atual = df.iloc[-1]
    if base is None:
        base = taxa_base_condicional(df, horizonte_periodos)

    sinais = []

    def add(nome, voto, peso, detalhe):
        # voto em [-1, 1]: +1 = alta, -1 = baixa, 0 = neutro
        sinais.append({"nome": nome, "voto": voto, "peso": peso, "detalhe": detalhe})

    # --- Filtro de tendencia por ADX (evidencia: sinais de tendencia so sao
    # confiaveis quando ha tendencia de verdade). Em mercado lateral (ADX baixo)
    # reduzimos o peso dos sinais de tendencia; em tendencia forte, reforcamos. ---
    adx_val = float(atual["adx"]) if atual["adx"] == atual["adx"] else None
    if adx_val is None:
        ft, regime = 1.0, "indefinida"
    elif adx_val >= 25:
        ft, regime = 1.15, "forte"
    elif adx_val >= 20:
        ft, regime = 1.0, "moderada"
    else:
        ft, regime = 0.6, "lateral"

    add("MACD", 1 if atual["macd_hist"] > 0 else -1, 1.0 * ft,
        f"histograma {'positivo' if atual['macd_hist'] > 0 else 'negativo'}")
    add("Preco vs SMA50", 1 if atual["close"] > atual["sma50"] else -1, 1.0 * ft,
        f"preco {'acima' if atual['close'] > atual['sma50'] else 'abaixo'} da media de 50")
    add("EMA9 vs EMA21", 1 if atual["ema9"] > atual["ema21"] else -1, 0.8 * ft,
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

    # Momentum de serie temporal (TSMOM) — evidencia academica forte em cripto:
    # o retorno recente do look-back tende a persistir. Pesado pelo regime (ADX).
    lb = min(30, len(df) - 1)
    if lb >= 5:
        ret_lb = float(df["close"].iloc[-1]) / float(df["close"].iloc[-1 - lb]) - 1
        if abs(ret_lb) > 0.005:
            add("Momentum (TSMOM)", 1 if ret_lb > 0 else -1, 1.0 * ft,
                f"retorno de {lb} periodos {ret_lb * 100:+.1f}% (tende a persistir)")

    # Confirmacao por volume — movimento com volume acima da media e mais
    # confiavel (evita 'fake breakout'); volume fraco esvazia a conviccao.
    vol_med = float(df["volume"].tail(20).mean())
    vol_atual = float(atual["volume"])
    if vol_med > 0:
        razao = vol_atual / vol_med
        tend = 1 if atual["ema9"] > atual["ema21"] else -1
        if razao > 1.2:
            add("Volume", tend, 0.5, f"volume {razao:.1f}x a media (confirma o movimento)")
        else:
            add("Volume", 0, 0.2, f"volume {razao:.1f}x a media (sem confirmacao)")

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

    nota_adx = (f"ADX {adx_val:.0f} (tendencia {regime})" if adx_val is not None
                else "ADX indisponivel")
    raciocinio = nota_adx + " | " + " | ".join(
        f"{s['nome']}: {s['detalhe']}" for s in sinais)

    # Séries recentes (até 120 pontos) para o gráfico: preço + médias móveis.
    def _serie(col, n=120):
        vals = df[col].tail(n)
        return [_arred_preco(v) for v in vals]  # None quando NaN; precisao adaptativa

    if leve:
        serie_preco = serie_sma50 = serie_ema21 = []
    else:
        serie_preco = _serie("close")
        serie_sma50 = _serie("sma50")
        serie_ema21 = _serie("ema21")
    if len(df) >= 2 and float(df["close"].iloc[-2]):
        variacao_pct = round((float(atual["close"]) / float(df["close"].iloc[-2]) - 1) * 100, 2)
    else:
        variacao_pct = 0.0

    try:
        ultimo_candle = str(atual["data"])[:16]  # 'YYYY-MM-DD HH:MM'
    except Exception:
        ultimo_candle = None

    return {
        "modulo": "tecnica",
        "direcao": direcao,
        "confianca": confianca,
        "raciocinio": raciocinio,
        "n_amostra": base["n_amostra"],
        "hist_pct_alta": base["pct_alta"],
        "hist_confianca": base["confianca_amostra"],
        "preco_atual": _arred_preco(atual["close"]),
        "variacao_pct": variacao_pct,
        "serie_preco": serie_preco,
        "serie_sma50": serie_sma50,
        "serie_ema21": serie_ema21,
        "ultimo_candle": ultimo_candle,
        "indicadores": {
            "rsi": round(float(atual["rsi"]), 1),
            "macd_hist": _arred_preco(atual["macd_hist"]),
            "sma50": _arred_preco(atual["sma50"]),
            "ema9": _arred_preco(atual["ema9"]),
            "ema21": _arred_preco(atual["ema21"]),
            "adx": round(adx_val, 1) if adx_val is not None else None,
        },
        "futuros": futuros,
        "dados_sinteticos": sintetico,
    }
