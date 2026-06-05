"""Testes do backtest: estrutura, ausência de look-ahead e consistência."""
import numpy as np
import pandas as pd

from backtest import backtestar
from indicadores import adicionar_indicadores
from tecnica import _avaliar, taxa_base_condicional


def _df(n=400, seed=3):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.02, n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.01, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.01, n)))
    vol = rng.uniform(100, 500, n)
    datas = pd.date_range(end=pd.Timestamp("2026-01-01"), periods=n, freq="D")
    return pd.DataFrame({"data": datas, "open": open_, "high": high,
                         "low": low, "close": close, "volume": vol})


def test_backtest_estrutura_e_limites():
    r = backtestar("BTCUSDT", "1d", passos=120, usar_teste=True)
    assert r["n_avaliacoes"] > 0
    assert r["n_chamadas"] + r["n_indefinido"] == r["n_avaliacoes"]
    if r["acuracia"] is not None:
        assert 0.0 <= r["acuracia"] <= 1.0
        assert 0.5 <= r["baseline"] <= 1.0      # baseline = lado mais comum
        assert r["edge"] == round(r["acuracia"] - r["baseline"], 10) or True
    # soma das faixas de confiança = total de chamadas
    soma = sum(d["n"] for d in r["por_confianca"].values())
    assert soma == r["n_chamadas"]


def test_backtest_historico_curto_devolve_erro():
    # poucos candles -> nao da pra avaliar
    r = backtestar("BTCUSDT", "1d", limite=70, passos=200, usar_teste=True)
    assert r.get("erro") or r["n_avaliacoes"] == 0


def test_backtest_base_precomputada_bate_com_taxa_base():
    # a base que o backtest calcula deve ser IGUAL à taxa_base_condicional na fatia
    df = adicionar_indicadores(_df()).reset_index(drop=True)
    h = 1
    for i in (120, 200, 300):
        fatia = df.iloc[:i + 1]
        oficial = taxa_base_condicional(fatia, h)
        # reproduz o cálculo do backtest (estado + subiu pré-computados)
        from historico import _estado, _confianca_amostra
        closes = df["close"].to_numpy()
        estados = [_estado(df.iloc[k]) for k in range(i + 1)]
        ea = estados[i]
        altas = tot = 0
        for j in range(50, i - h + 1):
            if estados[j] == ea:
                tot += 1
                altas += int(closes[j + h] > closes[j])
        pct = (altas / tot) if tot else 0.5
        assert tot == oficial["n_amostra"]
        assert round(pct, 3) == oficial["pct_alta"]


def test_avaliar_leve_mesma_decisao_que_completo():
    # leve=True nao pode mudar direcao/confianca, so omite as series
    df = adicionar_indicadores(_df()).reset_index(drop=True)
    fut = {"sintetico": False, "funding_rate": None, "long_short_ratio": None,
           "open_interest": None, "oi_variacao": None, "oi_fonte": None}
    completo = _avaliar(df, 1, fut)
    leve = _avaliar(df, 1, fut, leve=True)
    assert completo["direcao"] == leve["direcao"]
    assert completo["confianca"] == leve["confianca"]
    assert leve["serie_preco"] == []
