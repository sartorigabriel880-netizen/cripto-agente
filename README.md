# Agente de análise de cripto

Agente que combina **duas análises independentes** num veredito final:

- **Veredito 1 — fundamental (ntc/info):** macro + notícias + redes sociais + comparação histórica, via Claude + `web_search` (requer `ANTHROPIC_API_KEY`, com cache).
- **Veredito 2 — técnica:** indicadores + open interest + comparação histórica condicional.
- **Veredito final:** a síntese junta os dois; discordância = sinal ambíguo (não força cima/baixo).

## Painel visual (clicar e abrir)

O `painel.py` abre uma tela no navegador (feita com Streamlit) em vez do terminal.

**No PC (mais fácil):** dê **dois cliques no `abrir_painel.bat`**. Ele sobe o painel e abre o navegador sozinho. (Equivale a rodar `python -m streamlit run painel.py`.)

**No celular, na mesma rede Wi-Fi do PC:** com o painel rodando, o terminal mostra uma linha **Network URL** (algo como `http://192.168.x.x:8501`). Abra esse endereço no navegador do celular e use "Adicionar à tela inicial" para virar um ícone. (O PC precisa estar ligado e rodando o painel; se o celular não conectar, libere o acesso no Firewall do Windows quando ele perguntar.)

**No celular em qualquer lugar (PC desligado):** publique na nuvem (Streamlit Community Cloud, grátis). O código já está pronto: defina nos *Secrets* do app:
```
ANTHROPIC_API_KEY = "sua-chave"
senha_painel = "uma-senha-sua"     # protege o painel para so voce usar
```
Com `senha_painel` definida, o painel pede senha antes de abrir (no PC local, sem secret, abre direto).

## Linha de comando (alternativa ao painel)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sua-chave"     # Windows: $env:ANTHROPIC_API_KEY="..."

python main.py BTCUSDT                    # um ativo
python main.py BTCUSDT ETHUSDT SOLUSDT    # varios
python main.py --todos                    # BTC, ETH, SOL e XRP
python main.py BTCUSDT --intervalo 4h --horizonte 3
python main.py BTCUSDT --teste            # dados sinteticos (offline)
python main.py BTCUSDT --sem-cache        # forca nova busca
```

## Arquivos

| Arquivo | O que faz |
|---|---|
| `painel.py` | **painel visual (Streamlit)** |
| `abrir_painel.bat` | atalho de clique no Windows para abrir o painel |
| `main.py` | versão linha de comando; 1+ ativos, `--todos`, cache |
| `dados_binance.py` | candles + futuros (funding, long/short, open interest) |
| `indicadores.py` | RSI, MACD, médias, Bollinger, ATR |
| `historico.py` | taxa-base condicional |
| `tecnica.py` | `analise_tecnica()` → veredito 2 |
| `fundamental.py` | `analise_fundamental()` → veredito 1 (com cache) |
| `sintese.py` | `sintetizar()` → veredito final |
| `cache.py` | cache em disco (TTL) para o fundamental |

## Como ler

Confiança dominada pela **qualidade da evidência** (edge histórico + `n_amostra`), com tetos baixos de propósito — direção de 1 período é dominada por ruído. **Olhe o raciocínio e o `n_amostra`, não só o número.** Painel de pesquisa, não sinal de trade.
