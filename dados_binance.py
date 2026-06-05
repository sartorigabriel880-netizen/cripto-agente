"""Coleta de dados da Binance — candles (spot) e dados de futuros.

Dados publicos nao precisam de chave de API. Em ambiente sem internet, ou com a
flag de teste, geramos candles sinteticos SO para validar a logica da pipeline.
Esses dados sinteticos nao representam o mercado real e vem sempre rotulados.
"""
import numpy as np
import pandas as pd
import requests

# Fontes de candles (spot), tentadas em ordem. A 1a — data-api.binance.vision —
# e o endpoint PUBLICO de dados de mercado da Binance, que NAO tem bloqueio
# geografico; e o que faz funcionar quando o app roda num servidor (ex.: nuvem
# do Streamlit, nos EUA), onde api.binance.com costuma responder 451. A 2a fica
# como reserva. So caimos em dados sinteticos se TODAS falharem.
BASES_SPOT = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
]
BASE_SPOT = BASES_SPOT[0]  # compatibilidade
BASE_FUT = "https://fapi.binance.com"
TIMEOUT = 10


def obter_candles(symbol="BTCUSDT", intervalo="1d", limite=600, usar_teste=False):
    """Retorna (DataFrame OHLCV, eh_sintetico)."""
    if usar_teste:
        return _candles_sinteticos(limite), True
    params = {"symbol": symbol, "interval": intervalo, "limit": limite}
    erros = []
    for base in BASES_SPOT:
        try:
            resp = requests.get(f"{base}/api/v3/klines", params=params, timeout=TIMEOUT)
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
            erros.append(f"{base} ({e})")
            continue
    print(f"[aviso] Falha ao buscar candles em todas as fontes: {'; '.join(erros)}. "
          f"Caindo para dados sinteticos.")
    return _candles_sinteticos(limite), True


def listar_pares_usdt():
    """Lista todos os pares ...USDT em negociacao no spot da Binance.

    Usa o exchangeInfo do endpoint publico (sem bloqueio geografico). Filtra
    tokens alavancados (UP/DOWN/BULL/BEAR), que nao sao ativos 'de verdade'.
    Devolve lista ordenada; [] se todas as fontes falharem (o painel cai na
    lista curta padrao nesse caso).
    """
    for base in BASES_SPOT:
        try:
            r = requests.get(f"{base}/api/v3/exchangeInfo", timeout=15)
            r.raise_for_status()
            simbolos = r.json().get("symbols", [])
            pares = [s["symbol"] for s in simbolos
                     if s.get("status") == "TRADING"
                     and s.get("quoteAsset") == "USDT"
                     and not any(t in s["symbol"]
                                 for t in ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT"))]
            if pares:
                return sorted(pares)
        except Exception:
            continue
    return []


def obter_futuros(symbol="BTCUSDT", usar_teste=False):
    """Funding rate, long/short ratio e open interest (best-effort).

    Campos que falharem vem como None. O open interest agora e buscado de verdade
    (endpoint openInterestHist), junto com a variacao percentual recente.
    """
    if usar_teste:
        return {"funding_rate": 0.0001, "long_short_ratio": 1.0,
                "open_interest": 250000.0, "oi_variacao": 1.5, "sintetico": True}

    resultado = {"sintetico": False, "open_interest": None, "oi_variacao": None,
                 "oi_fonte": None}

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

    # Open interest: tenta Binance (ideal, com variacao) e, se falhar — tipico
    # quando o app roda num servidor nos EUA, onde a Binance de futuros bloqueia —
    # cai para a OKX, que costuma responder. So fica None se TODAS falharem.
    for fonte in (_oi_binance, _oi_okx):
        try:
            oi = fonte(symbol)
        except Exception:
            oi = None
        if oi and oi.get("open_interest") is not None:
            resultado.update(oi)
            break

    return resultado


def _oi_binance(symbol):
    """Open interest da Binance (valor + variacao vs o periodo anterior)."""
    r = requests.get(f"{BASE_FUT}/futures/data/openInterestHist",
                     params={"symbol": symbol, "period": "1d", "limit": 2},
                     timeout=TIMEOUT)
    r.raise_for_status()
    dados = r.json()
    if not dados:
        return None
    oi_atual = float(dados[-1]["sumOpenInterest"])
    variacao = None
    if len(dados) >= 2:
        oi_ant = float(dados[-2]["sumOpenInterest"])
        if oi_ant:
            variacao = round((oi_atual / oi_ant - 1) * 100, 2)
    return {"open_interest": round(oi_atual, 2), "oi_variacao": variacao,
            "oi_fonte": "Binance"}


def _oi_okx(symbol):
    """Open interest da OKX (reserva sem bloqueio geografico). So o valor — a OKX
    nao da a variacao nesse endpoint, entao oi_variacao fica None."""
    base = symbol[:-4] if symbol.upper().endswith("USDT") else symbol
    inst = f"{base.upper()}-USDT-SWAP"
    for host in ("https://www.okx.com", "https://aws.okx.com"):
        try:
            r = requests.get(f"{host}/api/v5/public/open-interest",
                             params={"instId": inst}, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json().get("data") or []
            if data and data[0].get("oiCcy"):
                return {"open_interest": round(float(data[0]["oiCcy"]), 2),
                        "oi_variacao": None, "oi_fonte": "OKX"}
        except Exception:
            continue
    return None


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
