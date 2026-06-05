"""Coleta de dados da Binance — candles (spot) e dados de futuros.

Dados publicos nao precisam de chave de API. Em ambiente sem internet, ou com a
flag de teste, geramos candles sinteticos SO para validar a logica da pipeline.
Esses dados sinteticos nao representam o mercado real e vem sempre rotulados.
"""
import numpy as np
import pandas as pd
import requests

BASE_SPOT = "https://api.binance.com"
BASE_FUT = "https://fapi.binance.com"
TIMEOUT = 10


def obter_candles(symbol="BTCUSDT", intervalo="1d", limite=600, usar_teste=False):
    """Retorna (DataFrame OHLCV, eh_sintetico)."""
    if usar_teste:
        return _candles_sinteticos(limite), True
    try:
        url = f"{BASE_SPOT}/api/v3/klines"
        params = {"symbol": symbol, "interval": intervalo, "limit": limite}
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        dados = resp.json()
        df = pd.DataFrame(dados, columns=[
            "abertura_ts", "open", "high", "low", "close", "volume",
            "fechamento_ts", "quote_volume", "trades", "tb_base", "tb_quote", "ignore"])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        df["data"] = pd.to_datetime(df["fechamento_ts"], unit="ms")
        return df[["data", "open", "high", "low", "close", "volume"]], False
    except Exception as e:
        print(f"[aviso] Falha ao buscar a Binance ({e}). Caindo para dados sinteticos.")
        return _candles_sinteticos(limite), True


def obter_futuros(symbol="BTCUSDT", usar_teste=False):
    """Funding rate, long/short ratio e open interest (best-effort).

    Campos que falharem vem como None. O open interest agora e buscado de verdade
    (endpoint openInterestHist), junto com a variacao percentual recente.
    """
    if usar_teste:
        return {"funding_rate": 0.0001, "long_short_ratio": 1.0,
                "open_interest": 250000.0, "oi_variacao": 1.5, "sintetico": True}

    resultado = {"sintetico": False, "open_interest": None, "oi_variacao": None}

    # Funding rate
    try:
        r = requests.get(f"{BASE_FUT}/fapi/v1/premiumIndex",
                         params={"symbol": symbol}, timeout=TIMEOUT)
        r.raise_for_status()
        resultado["funding_rate"] = float(r.json().get("lastFundingRate", 0))
    except Exception:
        resultado["funding_rate"] = None

    # Long/short ratio
    try:
        r = requests.get(f"{BASE_FUT}/futures/data/globalLongShortAccountRatio",
                         params={"symbol": symbol, "period": "1d", "limit": 1},
                         timeout=TIMEOUT)
        r.raise_for_status()
        dados = r.json()
        resultado["long_short_ratio"] = float(dados[-1]["longShortRatio"]) if dados else None
    except Exception:
        resultado["long_short_ratio"] = None

    # Open interest (ultimo valor + variacao vs o periodo anterior)
    try:
        r = requests.get(f"{BASE_FUT}/futures/data/openInterestHist",
                         params={"symbol": symbol, "period": "1d", "limit": 2},
                         timeout=TIMEOUT)
        r.raise_for_status()
        dados = r.json()
        if dados:
            oi_atual = float(dados[-1]["sumOpenInterest"])
            resultado["open_interest"] = round(oi_atual, 2)
            if len(dados) >= 2:
                oi_ant = float(dados[-2]["sumOpenInterest"])
                if oi_ant:
                    resultado["oi_variacao"] = round((oi_atual / oi_ant - 1) * 100, 2)
    except Exception:
        pass

    return resultado


def _candles_sinteticos(n=600, seed=7):
    """Random walk com leve drift positivo — so para testar a pipeline offline."""
    rng = np.random.default_rng(seed)
    retornos = rng.normal(0.0005, 0.03, n)
    close = 30000 * np.exp(np.cumsum(retornos))
    open_ = np.concatenate([[close[0]], close[:-1]])
    teto = np.maximum(open_, close)
    piso = np.minimum(open_, close)
    high = teto * (1 + np.abs(rng.normal(0, 0.01, n)))
    low = piso * (1 - np.abs(rng.normal(0, 0.01, n)))
    vol = rng.uniform(1000, 5000, n)
    fim = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    datas = pd.date_range(end=fim, periods=n, freq="D")
    return pd.DataFrame({"data": datas, "open": open_, "high": high,
                         "low": low, "close": close, "volume": vol})
