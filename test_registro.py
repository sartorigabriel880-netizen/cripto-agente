"""Testes do histórico de análises em disco (registro.py)."""
import registro


def _isolar(monkeypatch, tmp_path):
    monkeypatch.setattr(registro, "PASTA", str(tmp_path))
    monkeypatch.setattr(registro, "ARQ", str(tmp_path / "h.jsonl"))


def test_registro_roundtrip_mais_recente_primeiro(monkeypatch, tmp_path):
    _isolar(monkeypatch, tmp_path)
    assert registro.listar() == []          # vazio no começo
    registro.registrar({"ativo": "BTCUSDT", "direcao": "cima"})
    registro.registrar({"ativo": "ETHUSDT", "direcao": "baixo"})
    out = registro.listar()
    assert [x["ativo"] for x in out] == ["ETHUSDT", "BTCUSDT"]  # ordem reversa


def test_registro_limpar(monkeypatch, tmp_path):
    _isolar(monkeypatch, tmp_path)
    registro.registrar({"ativo": "BTCUSDT"})
    registro.limpar()
    assert registro.listar() == []


def test_registro_apara_no_maximo(monkeypatch, tmp_path):
    _isolar(monkeypatch, tmp_path)
    monkeypatch.setattr(registro, "MAX_LINHAS", 5)
    for i in range(12):
        registro.registrar({"i": i})
    out = registro.listar(1000)
    assert len(out) == 5
    assert out[0]["i"] == 11  # mantém as últimas; a mais nova no topo


def test_registro_limite_no_listar(monkeypatch, tmp_path):
    _isolar(monkeypatch, tmp_path)
    for i in range(10):
        registro.registrar({"i": i})
    assert len(registro.listar(limite=3)) == 3
