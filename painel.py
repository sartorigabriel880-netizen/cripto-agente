"""Painel visual do agente de cripto (Streamlit).

Rodar no PC:
    streamlit run painel.py
(ou dois cliques no abrir_painel.bat, no Windows)

A chave da API vem de:
  - variavel de ambiente ANTHROPIC_API_KEY (uso no seu PC), ou
  - st.secrets["ANTHROPIC_API_KEY"] (quando publicado na nuvem).

Senha opcional (para quando publicar): defina st.secrets["senha_painel"].
Sem senha definida, o painel abre direto (uso local).
"""
import os

import streamlit as st

st.set_page_config(page_title="Agente Cripto", page_icon="📊", layout="wide")


def _segredo(nome):
    """Le um valor dos secrets do Streamlit sem quebrar se nao existir (uso local)."""
    try:
        return st.secrets[nome]
    except Exception:
        return None


# Passa a chave/modelo dos secrets (nuvem) para variaveis de ambiente, para que
# o fundamental.py (que le os.environ) funcione sem nenhuma alteracao.
if _segredo("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = _segredo("ANTHROPIC_API_KEY")
if _segredo("MODELO_CLAUDE"):
    os.environ["MODELO_CLAUDE"] = _segredo("MODELO_CLAUDE")

from tecnica import analise_tecnica          # noqa: E402
from fundamental import analise_fundamental  # noqa: E402
from sintese import sintetizar               # noqa: E402


def _texto_seguro(s):
    """Escapa os caracteres que o markdown do Streamlit interpretaria como
    formatacao, para o texto livre do modelo sair LITERAL.

    Viloes ja vistos no texto das noticias:
      - '$'  : dois cifroes ligam modo LaTeX e embaralham valores ('$63K ... $4B')
      - '~'  : dois tils viram tachado/riscado ('~$80K ... ~21%' risca o meio)
      - '*' '_' '`' : negrito/italico/codigo acidentais
    Escapamos a contrabarra primeiro para nao escapar duas vezes.
    """
    s = s or ""
    for ch in ["\\", "`", "*", "_", "~", "$"]:
        s = s.replace(ch, "\\" + ch)
    return s


# ---------- Porta de senha (so ativa se houver senha nos secrets) ----------
def liberado():
    senha_certa = _segredo("senha_painel")
    if not senha_certa:
        return True  # sem senha configurada: libera (uso local)
    if st.session_state.get("autorizado"):
        return True
    st.title("🔒 Painel protegido")
    digitada = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if digitada == senha_certa:
            st.session_state["autorizado"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    return False


if not liberado():
    st.stop()


# ---------------------------- Interface ----------------------------
st.title("📊 Agente de análise de cripto")
st.caption("Macro + notícias + técnica num veredito só. "
           "Ferramenta de pesquisa — não é sinal de trade.")

with st.sidebar:
    st.header("Configurar análise")
    ativo = st.selectbox(
        "Ativo", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "Outro..."],
        help="Qual criptomoeda analisar. O par termina em USDT porque o preço é "
             "cotado em dólar — ex.: BTCUSDT = Bitcoin, ETHUSDT = Ethereum, "
             "SOLUSDT = Solana, XRPUSDT = XRP. Escolha 'Outro...' para digitar "
             "qualquer outro par disponível na Binance (ex.: ADAUSDT).")
    if ativo == "Outro...":
        ativo = st.text_input(
            "Digite o par (ex.: ADAUSDT)", "BTCUSDT",
            help="Use o formato MOEDA+USDT, tudo junto e em maiúsculas, "
                 "exatamente como na Binance. Ex.: ADAUSDT, DOGEUSDT, BNBUSDT.").upper()
    intervalo = st.selectbox(
        "Intervalo", ["1d", "4h", "1h", "15m"], index=0,
        help="O tempo que cada vela (candle) do gráfico representa. "
             "1d = 1 dia por vela, 4h = 4 horas, 1h = 1 hora, 15m = 15 minutos. "
             "Intervalos menores reagem mais rápido às mudanças, mas têm mais "
             "ruído; maiores mostram a tendência de fundo.")
    horizonte = st.number_input(
        "Horizonte (períodos à frente)", 1, 30, 1,
        help="Quantos períodos à frente a análise tenta enxergar — e cada "
             "período tem o tamanho do Intervalo acima. Ex.: horizonte 1 com "
             "intervalo 1d = previsão para o próximo dia; horizonte 3 com 4h = "
             "as próximas 12 horas. Quanto maior o horizonte, mais incerto.")
    modo_teste = st.checkbox(
        "Modo teste (dados sintéticos, offline)", value=False,
        help="Liga dados INVENTADOS (gerados pelo computador) só para testar o "
             "painel sem internet. NÃO refletem o mercado real — deixe "
             "DESMARCADO para uma análise de verdade com dados da Binance.")

    st.markdown("**Quais análises rodar**")
    usar_tecnica = st.checkbox(
        "📈 Técnica (indicadores)", value=True,
        help="Veredito a partir de indicadores de preço (RSI, MACD, médias, "
             "open interest) e do histórico. Rápida e gratuita — não usa a API.")
    usar_fundamental = st.checkbox(
        "📰 Fundamental (notícias/macro)", value=True,
        help="Veredito a partir de notícias, macro e sentimento, pesquisando na "
             "web com IA. Leva alguns segundos e consome créditos da API "
             "(Anthropic). Desmarque para uma análise só técnica, mais rápida.")

    analisar = st.button(
        "🔎 Analisar", type="primary", use_container_width=True,
        help="Roda as análises marcadas acima e mostra o veredito final. "
             "A parte de notícias pesquisa na web e pode levar alguns segundos.")

tem_chave = bool(os.environ.get("ANTHROPIC_API_KEY"))
if usar_fundamental and not tem_chave and not modo_teste:
    st.info("Sem chave de API configurada: a análise de notícias não vai rodar "
            "(só a técnica). Desmarque '📰 Fundamental' para esconder este aviso.")

SETA = {"cima": "⬆️", "baixo": "⬇️", "ambiguo": "↔️", "indefinido": "❓"}


def _indef(modulo):
    """Veredito vazio para um módulo que o usuário optou por NÃO rodar."""
    return {"modulo": modulo, "direcao": "indefinido", "confianca": 0.0,
            "raciocinio": "", "n_amostra": 0}


if analisar and not usar_tecnica and not usar_fundamental:
    st.warning("Marque ao menos uma análise (📈 Técnica e/ou 📰 Fundamental) "
               "na barra lateral.")
elif analisar:
    with st.spinner("Analisando… (se as notícias estiverem ligadas, "
                    "a pesquisa na web pode levar alguns segundos)"):
        vt = (analise_tecnica(ativo, intervalo, int(horizonte), 600, modo_teste)
              if usar_tecnica else _indef("tecnica"))
        vf = (analise_fundamental(ativo, int(horizonte))
              if usar_fundamental else _indef("fundamental"))
        final = sintetizar(vf, vt)

    if usar_tecnica and vt.get("dados_sinteticos"):
        st.warning("MODO TESTE: dados sintéticos — não refletem o mercado real.")

    st.subheader(f"Veredito final — {ativo}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Direção", f"{SETA.get(final['direcao'], '')} {final['direcao'].upper()}")
    c2.metric("Confiança", f"{final['confianca']:.2f}")
    c3.metric("Concordância", final["concordancia"])
    st.caption(final["resumo"])

    # Linha de métricas de preço só faz sentido quando a técnica rodou.
    if usar_tecnica:
        cols = st.columns(4)
        cols[0].metric("Preço atual", f"{vt['preco_atual']:,}")
        cols[1].metric("RSI", vt["indicadores"]["rsi"])
        cols[2].metric("MACD hist", vt["indicadores"]["macd_hist"])
        oi = vt["futuros"].get("open_interest")
        oi_var = vt["futuros"].get("oi_variacao")
        cols[3].metric("Open interest", f"{oi:,}" if oi is not None else "—",
                       delta=f"{oi_var}%" if oi_var is not None else None)

    st.divider()
    col_f, col_t = st.columns(2)
    with col_f:
        st.markdown("### 📰 Veredito 1 — fundamental (notícias/macro)")
        if not usar_fundamental:
            st.info("Desativada nesta busca. Marque '📰 Fundamental' na barra "
                    "lateral para incluir notícias e macro.")
        else:
            st.write(f"**Direção:** {vf['direcao']}  |  **Confiança:** {vf['confianca']}  "
                     f"|  **Episódios análogos (n):** {vf.get('n_amostra', '-')}")
            if vf.get("do_cache"):
                st.caption("↺ resultado reaproveitado do cache (não consumiu API)")
            st.write(_texto_seguro(vf["raciocinio"]))
            if vf.get("fontes"):
                st.markdown("**Fontes:**")
                for url in vf["fontes"][:8]:
                    st.markdown(f"- [{url}]({url})")
    with col_t:
        st.markdown("### 📈 Veredito 2 — técnica")
        if not usar_tecnica:
            st.info("Desativada nesta busca. Marque '📈 Técnica' na barra "
                    "lateral para incluir indicadores.")
        else:
            st.write(f"**Direção:** {vt['direcao']}  |  **Confiança:** {vt['confianca']}  "
                     f"|  **Casos análogos (n):** {vt['n_amostra']}")
            st.write(_texto_seguro(vt["raciocinio"]))
            with st.expander("Indicadores e futuros (detalhe)"):
                st.json({"indicadores": vt["indicadores"], "futuros": vt["futuros"]})

    st.divider()
    st.caption("⚠️ " + final["aviso"] +
               " Olhe sempre o raciocínio e o n_amostra, não só o número da confiança.")
else:
    st.info("Escolha o ativo na barra lateral e clique em **Analisar**.")
