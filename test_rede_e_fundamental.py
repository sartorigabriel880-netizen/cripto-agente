"""Testes das bordas que tocam o mundo externo — com tudo MOCKADO.

Aqui nao ha rede nem API de verdade: trocamos `requests.get` e o cliente
`Anthropic` por dublês para exercitar exatamente os caminhos que so aparecem
quando a coisa externa responde, falha ou expira. O que importa testar e a
NOSSA logica de reacao (cair para sintetico, devolver None, usar cache, parsear
o JSON), nao a Binance nem o Claude.

Rodar:
    python -m pytest -q
"""
import sys
import types

import pytest

import cache
import dados_binance as db
import fundamental as fund


# --------------------------- helpers de mock ----------------------------
class _Resp:
    """Dublê minimo de uma resposta do requests."""
    def __init__(self, payload, erro=None):
        self._payload = payload
        self._erro = erro

    def raise_for_status(self):
        if self._erro:
            raise self._erro

    def json(self):
        return self._payload


def _kline(close, ts=1735689600000):
    # 12 colunas no formato da Binance: precos como string, timestamps (idx 0 e 6)
    # como inteiro em ms — igual ao retorno real do endpoint klines.
    return [ts, "0", "0", "0", str(close), "10",
            ts, "0", "5", "0", "0", "0"]


# ----------------------------- obter_candles ----------------------------
def test_obter_candles_sucesso_parseia_df(monkeypatch):
    payload = [_kline(100 + i) for i in range(5)]
    monkeypatch.setattr(db.requests, "get", lambda *a, **k: _Resp(payload))
    df, sintetico = db.obter_candles("BTCUSDT", limite=5)
    assert sintetico is False
    assert list(df.columns) == ["data", "open", "high", "low", "close", "volume"]
    assert len(df) == 5
    assert df["close"].iloc[-1] == 104.0


def test_obter_candles_falha_cai_para_sintetico(monkeypatch, capsys):
    def _boom(*a, **k):
        raise db.requests.RequestException("sem rede")
    monkeypatch.setattr(db.requests, "get", _boom)
    df, sintetico = db.obter_candles("BTCUSDT", limite=120)
    assert sintetico is True            # caiu para o gerador offline
    assert len(df) == 120
    assert "sintetic" in capsys.readouterr().out.lower()  # avisou o usuario


def test_obter_candles_modo_teste_nao_chama_rede(monkeypatch):
    def _nao_pode(*a, **k):
        raise AssertionError("nao deveria tocar a rede no modo teste")
    monkeypatch.setattr(db.requests, "get", _nao_pode)
    df, sintetico = db.obter_candles(usar_teste=True, limite=60)
    assert sintetico is True and len(df) == 60


# ----------------------------- obter_futuros ----------------------------
def test_obter_futuros_sucesso_le_tres_endpoints(monkeypatch):
    def _fake_get(url, **k):
        if "premiumIndex" in url:
            return _Resp({"lastFundingRate": "0.0002"})
        if "globalLongShortAccountRatio" in url:
            return _Resp([{"longShortRatio": "1.25"}])
        if "openInterestHist" in url:
            return _Resp([{"sumOpenInterest": "100"}, {"sumOpenInterest": "110"}])
        raise AssertionError(f"url inesperada: {url}")
    monkeypatch.setattr(db.requests, "get", _fake_get)
    f = db.obter_futuros("BTCUSDT")
    assert f["sintetico"] is False
    assert f["funding_rate"] == pytest.approx(0.0002)
    assert f["long_short_ratio"] == pytest.approx(1.25)
    assert f["open_interest"] == 110.0
    assert f["oi_variacao"] == pytest.approx(10.0)  # 110/100 - 1 = +10%


def test_obter_futuros_falhas_viram_none(monkeypatch):
    def _boom(*a, **k):
        raise db.requests.RequestException("derrubou tudo")
    monkeypatch.setattr(db.requests, "get", _boom)
    f = db.obter_futuros("BTCUSDT")
    assert f["funding_rate"] is None
    assert f["long_short_ratio"] is None
    assert f["open_interest"] is None
    assert f["oi_variacao"] is None
    assert f["sintetico"] is False  # falha de rede != dado sintetico


# -------------------------------- cache ---------------------------------
def test_cache_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "PASTA", str(tmp_path))
    cache.cache_set("chave:x", {"a": 1})
    assert cache.cache_get("chave:x", ttl_segundos=3600) == {"a": 1}


def test_cache_expira(monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "PASTA", str(tmp_path))
    cache.cache_set("chave:y", {"a": 2})
    # ttl ridiculamente curto + relogio adiantado => considerado expirado
    monkeypatch.setattr(cache.time, "time", lambda: 10 ** 12)
    assert cache.cache_get("chave:y", ttl_segundos=1) is None


def test_cache_ttl_zero_desliga(monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "PASTA", str(tmp_path))
    cache.cache_set("chave:z", {"a": 3})
    assert cache.cache_get("chave:z", ttl_segundos=0) is None


# ------------------------- fundamental: helpers -------------------------
def test_parsear_json_extrai_objeto_no_meio():
    assert fund._parsear_json('lixo antes {"direcao": "cima"} lixo depois') == {"direcao": "cima"}


def test_parsear_json_invalido_devolve_none():
    assert fund._parsear_json("sem chaves aqui") is None
    assert fund._parsear_json("") is None


def test_num_robusto():
    assert fund._num("0.5") == 0.5
    assert fund._num("nao-numero") == 0.0


# ------------------------- fundamental: fluxo ---------------------------
def test_fundamental_sem_chave_devolve_indefinido(monkeypatch):
    monkeypatch.setattr(fund, "cache_get", lambda *a, **k: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = fund.analise_fundamental("BTCUSDT", cache_min=0)
    assert out["modulo"] == "fundamental"
    assert out["direcao"] == "indefinido"
    assert out["confianca"] == 0.0


def test_fundamental_usa_cache_sem_chamar_api(monkeypatch):
    guardado = {"modulo": "fundamental", "direcao": "cima", "confianca": 0.4,
                "raciocinio": "x", "fontes": [], "n_amostra": 3}
    monkeypatch.setattr(fund, "cache_get", lambda *a, **k: guardado)
    # se tentasse criar o client Anthropic, falharia o teste
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    out = fund.analise_fundamental("BTCUSDT", cache_min=60)
    assert out["direcao"] == "cima"
    assert out["do_cache"] is True


def _instalar_anthropic_fake(monkeypatch, texto_resposta):
    """Injeta um modulo 'anthropic' falso cujo client devolve `texto_resposta`."""
    bloco = types.SimpleNamespace(type="text", text=texto_resposta)
    resp = types.SimpleNamespace(content=[bloco])

    class _Messages:
        def create(self, **kwargs):
            return resp

    class _Anthropic:
        def __init__(self, **kwargs):
            self.messages = _Messages()

    mod = types.ModuleType("anthropic")
    mod.Anthropic = _Anthropic
    monkeypatch.setitem(sys.modules, "anthropic", mod)


def test_fundamental_parseia_resposta_e_grava_cache(monkeypatch):
    monkeypatch.setattr(fund, "cache_get", lambda *a, **k: None)
    gravados = {}
    monkeypatch.setattr(fund, "cache_set", lambda chave, valor: gravados.update({chave: valor}))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    _instalar_anthropic_fake(monkeypatch, (
        '{"direcao": "baixo", "confianca": 0.3, "raciocinio": "macro pesado", '
        '"fontes": ["http://ex.com"], "episodios_analogos": 7}'))

    out = fund.analise_fundamental("BTCUSDT", cache_min=0)
    assert out["direcao"] == "baixo"
    assert out["confianca"] == 0.3
    assert out["n_amostra"] == 7
    assert out["fontes"] == ["http://ex.com"]
    assert out["do_cache"] is False
    assert gravados  # resultado bom foi para o cache


def test_fundamental_json_quebrado_nao_grava_cache(monkeypatch):
    monkeypatch.setattr(fund, "cache_get", lambda *a, **k: None)
    chamou = {"set": False}
    monkeypatch.setattr(fund, "cache_set", lambda *a, **k: chamou.update({"set": True}))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    _instalar_anthropic_fake(monkeypatch, "isso nao e json nenhum")

    out = fund.analise_fundamental("BTCUSDT", cache_min=0)
    assert out["direcao"] == "indefinido"
    assert chamou["set"] is False  # nao guarda 'indefinido'
