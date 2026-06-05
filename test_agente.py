"""Testes da logica offline e deterministica do agente.

Cobrem indicadores, taxa-base condicional, sintese e o veredito tecnico em modo
teste (dados sinteticos). NAO tocam a rede nem a API do Claude de proposito:
a logica que merece teste e justamente a que decide direcao e confianca.

Rodar:
    python -m pytest -q
"""
import numpy as np
import pandas as pd
import pytest

import indicadores as ind
from historico import (_bucket_rsi, _confianca_amostra, _estado,
                       taxa_base_condicional)
from sintese import TETO_FINAL, sintetizar
from tecnica import TETO_CONFIANCA, _arred_preco, analise_tecnica


# ----------------------------- fixtures --------------------------------
def _df_sintetico(n=300, seed=1):
    """Random walk OHLCV — suficiente para os indicadores aquecerem."""
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.01, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.01, n)))
    vol = rng.uniform(100, 500, n)
    datas = pd.date_range(end=pd.Timestamp("2026-01-01"), periods=n, freq="D")
    return pd.DataFrame({"data": datas, "open": open_, "high": high,
                         "low": low, "close": close, "volume": vol})


@pytest.fixture
def df():
    return _df_sintetico()


@pytest.fixture
def df_ind(df):
    return ind.adicionar_indicadores(df)


# ----------------------------- indicadores -----------------------------
def test_sma_ema_alinham_o_tamanho(df):
    assert len(ind.sma(df["close"], 20)) == len(df)
    assert len(ind.ema(df["close"], 9)) == len(df)


def test_rsi_fica_no_intervalo_0_100(df):
    r = ind.rsi(df["close"]).dropna()
    assert (r >= 0).all() and (r <= 100).all()


def test_macd_devolve_tres_series(df):
    linha, sinal, hist = ind.macd(df["close"])
    assert len(linha) == len(sinal) == len(hist) == len(df)
    # histograma = linha - sinal por definicao
    assert np.allclose((linha - sinal).dropna(), hist.dropna())


def test_bollinger_ordena_as_bandas(df):
    sup, mid, inf = ind.bollinger(df["close"])
    m = sup.notna() & inf.notna()
    assert (sup[m] >= mid[m]).all() and (mid[m] >= inf[m]).all()


def test_atr_nao_negativo(df):
    a = ind.atr(df).dropna()
    assert (a >= 0).all()


def test_adicionar_indicadores_cria_colunas(df_ind):
    esperadas = {"rsi", "macd", "macd_sinal", "macd_hist", "sma20", "sma50",
                 "ema9", "ema21", "bb_sup", "bb_mid", "bb_inf", "atr", "adx"}
    assert esperadas.issubset(df_ind.columns)


def test_adx_fica_no_intervalo_0_100(df):
    a = ind.adx(df).dropna()
    assert (a >= 0).all() and (a <= 100).all()


# ------------------------------ historico ------------------------------
@pytest.mark.parametrize("valor,esperado", [
    (10, "sobrevendido"), (29.9, "sobrevendido"),
    (30, "fraco"), (44.9, "fraco"),
    (45, "neutro"), (54.9, "neutro"),
    (55, "forte"), (69.9, "forte"),
    (70, "sobrecomprado"), (95, "sobrecomprado"),
])
def test_bucket_rsi_fronteiras(valor, esperado):
    assert _bucket_rsi(valor) == esperado


@pytest.mark.parametrize("n,pct,esperado", [
    (5, 0.9, "muito baixa"),
    (30, 0.9, "baixa"),
    (100, 0.6, "media"),
    (100, 0.51, "baixa"),     # margem pequena derruba para baixa
    (200, 0.6, "alta"),
    (200, 0.52, "media"),     # margem < 0.07 nao chega a alta
])
def test_confianca_amostra(n, pct, esperado):
    assert _confianca_amostra(n, pct) == esperado


def test_taxa_base_estrutura_e_limites(df_ind):
    base = taxa_base_condicional(df_ind, horizonte_periodos=1)
    assert set(base) == {"estado_atual", "n_amostra", "pct_alta", "confianca_amostra"}
    assert base["n_amostra"] >= 0
    assert 0.0 <= base["pct_alta"] <= 1.0
    assert base["confianca_amostra"] in {"muito baixa", "baixa", "media", "alta"}
    assert base["estado_atual"] == _estado(df_ind.iloc[-1])


def test_taxa_base_sem_casos_devolve_meio(df_ind):
    # horizonte gigante zera a amostra util -> pct_alta cai no neutro 0.5
    base = taxa_base_condicional(df_ind, horizonte_periodos=len(df_ind))
    assert base["n_amostra"] == 0
    assert base["pct_alta"] == 0.5
    assert base["confianca_amostra"] == "muito baixa"


# ------------------------------- sintese -------------------------------
def _v(modulo, direcao, confianca):
    return {"modulo": modulo, "direcao": direcao, "confianca": confianca}


def test_sintese_ambos_indefinidos():
    out = sintetizar(_v("fundamental", "indefinido", 0.0),
                     _v("tecnica", "indefinido", 0.0))
    assert out["direcao"] == "indefinido"
    assert out["concordancia"] == "indefinido"
    assert out["confianca"] == 0.0


def test_sintese_so_um_opina_aplica_desconto():
    out = sintetizar(_v("fundamental", "indefinido", 0.0),
                     _v("tecnica", "cima", 0.5))
    assert out["direcao"] == "cima"
    assert out["concordancia"] == "parcial"
    assert out["confianca"] == round(0.5 * 0.7, 2)  # 0.35


def test_sintese_concordam_da_bonus_mas_respeita_teto():
    out = sintetizar(_v("fundamental", "cima", 0.7),
                     _v("tecnica", "cima", 0.6))
    assert out["direcao"] == "cima"
    assert out["concordancia"] == "concordam"
    # media 0.65 + bonus 0.15*0.6=0.09 = 0.74, abaixo do teto
    assert out["confianca"] == pytest.approx(0.74, abs=0.01)
    assert out["confianca"] <= TETO_FINAL


def test_sintese_concordam_dois_fracos_nao_viram_forte():
    out = sintetizar(_v("fundamental", "baixo", 0.2),
                     _v("tecnica", "baixo", 0.2))
    # media 0.2 + bonus 0.15*0.2=0.03 = 0.23: continua fraco
    assert out["confianca"] == pytest.approx(0.23, abs=0.01)


def test_sintese_discordam_e_ambiguo():
    out = sintetizar(_v("fundamental", "cima", 0.9),
                     _v("tecnica", "baixo", 0.9))
    assert out["direcao"] == "ambiguo"
    assert out["concordancia"] == "discordam"
    assert out["confianca"] == 0.15


# ------------------------------- tecnica -------------------------------
def test_analise_tecnica_modo_teste_estrutura():
    v = analise_tecnica("BTCUSDT", usar_teste=True)
    assert v["modulo"] == "tecnica"
    assert v["direcao"] in {"cima", "baixo", "indefinido"}
    assert 0.0 <= v["confianca"] <= TETO_CONFIANCA
    assert v["dados_sinteticos"] is True
    assert v["futuros"]["sintetico"] is True
    assert {"rsi", "macd_hist", "sma50", "ema9", "ema21", "adx"} <= set(v["indicadores"])


def test_analise_tecnica_confianca_respeita_teto():
    # varios horizontes nao podem furar o teto de confianca
    for h in (1, 3, 5):
        v = analise_tecnica("BTCUSDT", horizonte_periodos=h, usar_teste=True)
        assert v["confianca"] <= TETO_CONFIANCA


# --- regressao: moedas muito baratas nao podem virar 0.0 (bug do round(x,2)) ---
@pytest.mark.parametrize("valor,esperado", [
    (61588.3, 61588.3),       # >= 1   -> 2 casas
    (1.23456, 1.23),
    (0.0723, 0.0723),         # >= 0.01 -> 4 casas
    (0.00094812, 0.000948),   # >= 0.0001 -> 6 casas
    (4.35e-06, 4.35e-06),     # < 0.0001 -> 8 casas (BONK)
])
def test_arred_preco_preserva_baratos(valor, esperado):
    assert _arred_preco(valor) == esperado


def test_arred_preco_nan_vira_none():
    assert _arred_preco(float("nan")) is None
    assert _arred_preco(None) is None


def test_arred_preco_baratos_nao_zeram():
    for v in (4.35e-06, 9.48e-06, 1e-7):
        assert _arred_preco(v) > 0  # nunca colapsa para 0.0
