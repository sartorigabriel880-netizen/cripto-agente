"""Backtest honesto do veredito técnico — o 'track record' do próprio agente.

Caminha pelo histórico e, em cada ponto i, decide usando SÓ os candles até i
(fatia df[:i+1]) — a mesma função `_avaliar` da produção, então não há divergência
de lógica. Depois compara a direção prevista com o que o preço REALMENTE fez na(s)
vela(s) seguinte(s). Isso evita look-ahead (não espia o futuro).

Limitações honestas:
  - Não inclui futuros (open interest/funding): não há histórico desses por candle.
  - Backtest não é promessa de futuro; mede só como a regra teria se saído no
    período coberto, que pode não se repetir.
"""
from dados_binance import obter_candles
from historico import _confianca_amostra, _estado
from indicadores import adicionar_indicadores
from tecnica import _avaliar

_FUTUROS_VAZIO = {"sintetico": False, "funding_rate": None, "long_short_ratio": None,
                  "open_interest": None, "oi_variacao": None, "oi_fonte": None}

_FAIXAS = [("baixa (<0.20)", 0.0, 0.20),
           ("média (0.20–0.35)", 0.20, 0.35),
           ("alta (≥0.35)", 0.35, 1.01)]


def backtestar(symbol="BTCUSDT", intervalo="1d", horizonte_periodos=1,
               limite=600, passos=200, usar_teste=False, detalhar=False):
    """Roda o backtest e devolve métricas de acerto (sem look-ahead).

    detalhar=True inclui 'calls': lista de (confianca, acerto) por chamada,
    para análises por limiar de confiança (ex.: varredura por edge)."""
    df, sintetico = obter_candles(symbol, intervalo, limite, usar_teste)
    df = adicionar_indicadores(df)
    df = df.reset_index(drop=True)
    n = len(df)
    h = max(1, int(horizonte_periodos))

    # janela de avaliação: ultimos `passos` pontos, com indicadores ja aquecidos
    fim = n - h
    inicio = max(80, fim - int(passos))
    if fim - inicio < 10:
        return {"erro": "histórico insuficiente para backtest",
                "n_avaliacoes": 0, "n_chamadas": 0}

    closes = df["close"].to_numpy()
    # Pré-computa, UMA vez, o estado discreto de cada candle e se subiu depois de h.
    # Isso torna a taxa-base condicional O(i) com comparações baratas (sem .iloc
    # por candle a cada ponto), derrubando o tempo do backtest de ~74s para ~poucos s.
    estados = [_estado(df.iloc[k]) for k in range(n)]
    subiu_arr = [bool(closes[k + h] > closes[k]) if k + h < n else None for k in range(n)]

    def _base_ate(i):
        ea = estados[i]
        altas = tot = 0
        for j in range(50, i - h + 1):
            if estados[j] == ea:
                tot += 1
                altas += int(subiu_arr[j])
        pct = (altas / tot) if tot else 0.5
        return {"estado_atual": ea, "n_amostra": tot, "pct_alta": round(pct, 3),
                "confianca_amostra": _confianca_amostra(tot, pct)}

    n_chamadas = n_acertos = n_indef = subiu_total = 0
    faixas = {nome: {"n": 0, "acertos": 0} for nome, _, _ in _FAIXAS}
    calls = []  # (confianca, acerto_bool) por chamada — para filtrar por limiar depois

    for i in range(inicio, fim):
        v = _avaliar(df.iloc[:i + 1], h, _FUTUROS_VAZIO, sintetico,
                     base=_base_ate(i), leve=True)
        subiu = closes[i + h] > closes[i]
        subiu_total += int(subiu)
        pred, conf = v["direcao"], v["confianca"]
        if pred not in ("cima", "baixo"):
            n_indef += 1
            continue
        acerto = (pred == "cima" and subiu) or (pred == "baixo" and not subiu)
        n_chamadas += 1
        n_acertos += int(acerto)
        calls.append((float(conf), bool(acerto)))
        for nome, lo, hi in _FAIXAS:
            if lo <= conf < hi:
                faixas[nome]["n"] += 1
                faixas[nome]["acertos"] += int(acerto)
                break

    n_aval = fim - inicio
    p_alta = subiu_total / n_aval if n_aval else 0.0
    baseline = max(p_alta, 1 - p_alta)  # acerto de quem sempre chuta o lado mais comum
    acuracia = (n_acertos / n_chamadas) if n_chamadas else None
    for f in faixas.values():
        f["acuracia"] = (f["acertos"] / f["n"]) if f["n"] else None

    resultado = {
        "symbol": symbol, "intervalo": intervalo, "horizonte": h,
        "n_avaliacoes": n_aval,
        "n_chamadas": n_chamadas,
        "n_indefinido": n_indef,
        "acuracia": acuracia,
        "baseline": baseline,          # referencia ingenua (sempre o lado mais comum)
        "edge": (acuracia - baseline) if acuracia is not None else None,
        "p_alta_periodo": round(p_alta, 3),
        "por_confianca": faixas,
        "dados_sinteticos": sintetico,
    }
    if detalhar:
        resultado["calls"] = calls
    return resultado
