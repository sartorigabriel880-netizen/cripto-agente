"""Calculo de indicadores tecnicos a partir de candles OHLCV (pandas DataFrame).

Tudo calculado a mao de proposito: zero dependencia fragil e voce enxerga
exatamente como cada indicador e formado. Se um dia quiser, da pra trocar por
pandas-ta ou pela lib `ta` sem mexer no resto.
"""
import pandas as pd


def sma(serie, periodo):
    """Media movel simples."""
    return serie.rolling(periodo).mean()


def ema(serie, periodo):
    """Media movel exponencial."""
    return serie.ewm(span=periodo, adjust=False).mean()


def rsi(close, periodo=14):
    """Indice de forca relativa (suavizacao de Wilder)."""
    delta = close.diff()
    ganho = delta.clip(lower=0)
    perda = -delta.clip(upper=0)
    media_ganho = ganho.ewm(alpha=1 / periodo, adjust=False).mean()
    media_perda = perda.ewm(alpha=1 / periodo, adjust=False).mean()
    rs = media_ganho / media_perda
    return 100 - (100 / (1 + rs))


def macd(close, rapida=12, lenta=26, sinal=9):
    """Retorna (linha_macd, linha_sinal, histograma)."""
    linha = ema(close, rapida) - ema(close, lenta)
    linha_sinal = ema(linha, sinal)
    histograma = linha - linha_sinal
    return linha, linha_sinal, histograma


def bollinger(close, periodo=20, desvios=2):
    """Retorna (banda_superior, media, banda_inferior)."""
    media = sma(close, periodo)
    desvio = close.rolling(periodo).std()
    return media + desvios * desvio, media, media - desvios * desvio


def atr(df, periodo=14):
    """Average True Range — mede volatilidade."""
    alta_baixa = df["high"] - df["low"]
    alta_fech = (df["high"] - df["close"].shift()).abs()
    baixa_fech = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([alta_baixa, alta_fech, baixa_fech], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / periodo, adjust=False).mean()


def adicionar_indicadores(df):
    """Acrescenta as colunas de indicadores ao DataFrame de candles."""
    df = df.copy()
    df["rsi"] = rsi(df["close"])
    df["macd"], df["macd_sinal"], df["macd_hist"] = macd(df["close"])
    df["sma20"] = sma(df["close"], 20)
    df["sma50"] = sma(df["close"], 50)
    df["ema9"] = ema(df["close"], 9)
    df["ema21"] = ema(df["close"], 21)
    df["bb_sup"], df["bb_mid"], df["bb_inf"] = bollinger(df["close"])
    df["atr"] = atr(df)
    return df
