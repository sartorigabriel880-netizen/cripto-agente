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

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Agente Cripto", page_icon="📊", layout="wide")

# ---- Estilo "claro, orientado a dados" (inspirado no CoinMarketCap) ----
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 2.2rem; max-width: 1200px; }
/* Métricas viram cards com borda suave */
[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #EFF2F5;
    border-radius: 14px;
    padding: 14px 18px;
    box-shadow: 0 1px 2px rgba(16,24,40,0.04);
}
[data-testid="stMetricLabel"] p {
    font-size: .78rem; color: #616E85; font-weight: 600;
    text-transform: uppercase; letter-spacing: .03em;
}
[data-testid="stMetricValue"] { font-weight: 700; }
/* Títulos um pouco mais sóbrios */
h1 { font-weight: 800; letter-spacing: -.02em; }
h3 { font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# Paleta de direção (verde sobe / vermelho desce / cinza neutro) — estilo CMC.
COR_DIR = {"cima": "#16C784", "baixo": "#EA3943",
           "ambiguo": "#A6B0C3", "indefinido": "#A6B0C3"}


def _card(titulo, valor, cor=None, sub=None):
    """Cartão simples (título pequeno + valor grande), opcionalmente colorido."""
    cor_css = f"color:{cor};" if cor else "color:#0D1421;"
    sub_html = (f"<div style='font-size:.78rem;color:#616E85;margin-top:6px'>{sub}</div>"
                if sub else "")
    return f"""<div style="background:#FFFFFF;border:1px solid #EFF2F5;border-radius:14px;
        padding:16px 18px;box-shadow:0 1px 2px rgba(16,24,40,.04);height:100%">
        <div style="font-size:.78rem;color:#616E85;font-weight:600;
            text-transform:uppercase;letter-spacing:.03em">{titulo}</div>
        <div style="font-size:1.7rem;font-weight:700;{cor_css}margin-top:2px">{valor}</div>
        {sub_html}</div>"""


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
    cor_dir = COR_DIR.get(final["direcao"], "#0D1421")
    c1, c2, c3 = st.columns(3)
    c1.markdown(_card("Direção",
                      f"{SETA.get(final['direcao'], '')} {final['direcao'].upper()}",
                      cor=cor_dir), unsafe_allow_html=True)
    c2.markdown(_card("Confiança", f"{final['confianca']:.2f}",
                      sub="0 a 1 — teto baixo de propósito"), unsafe_allow_html=True)
    c3.markdown(_card("Concordância", final["concordancia"].capitalize()),
                unsafe_allow_html=True)
    st.caption(final["resumo"])
    st.write("")  # respiro

    # Linha de métricas de preço só faz sentido quando a técnica rodou.
    if usar_tecnica:
        VERDE, VERMELHO, NEUTRO = "#16C784", "#EA3943", "#616E85"
        cols = st.columns(4)

        # Preço + variação % do último período (verde/vermelho com seta)
        var = vt.get("variacao_pct", 0.0)
        cor_var = VERDE if var >= 0 else VERMELHO
        seta_var = "▲" if var >= 0 else "▼"
        sub_preco = (f"<span style='color:{cor_var};font-weight:600'>"
                     f"{seta_var} {var:+.2f}%</span> no período")
        cols[0].markdown(_card("Preço atual", f"${vt['preco_atual']:,.2f}", sub=sub_preco),
                         unsafe_allow_html=True)

        # RSI colorido: vermelho sobrecomprado (>70), verde sobrevendido (<30)
        rsi = vt["indicadores"]["rsi"]
        if rsi > 70:
            cor_rsi, zona = VERMELHO, "sobrecomprado"
        elif rsi < 30:
            cor_rsi, zona = VERDE, "sobrevendido"
        else:
            cor_rsi, zona = NEUTRO, "neutro"
        cols[1].markdown(_card("RSI", f"{rsi}", cor=cor_rsi, sub=zona), unsafe_allow_html=True)

        # MACD histograma: verde positivo / vermelho negativo
        macd_h = vt["indicadores"]["macd_hist"]
        cols[2].markdown(_card("MACD hist", f"{macd_h}",
                               cor=VERDE if macd_h >= 0 else VERMELHO,
                               sub="momentum"), unsafe_allow_html=True)

        # Open interest (Binance local; OKX como reserva na nuvem)
        oi = vt["futuros"].get("open_interest")
        oi_var = vt["futuros"].get("oi_variacao")
        oi_fonte = vt["futuros"].get("oi_fonte")
        if oi_var is not None:
            sub_oi = (f"<span style='color:{VERDE if oi_var >= 0 else VERMELHO}'>"
                      f"{oi_var:+.1f}%</span> · {oi_fonte or ''}")
        elif oi is not None:
            sub_oi = f"via {oi_fonte}" if oi_fonte else "snapshot"
        else:
            sub_oi = "indisponível"
        cols[3].markdown(_card("Open interest", f"{oi:,.0f}" if oi is not None else "—",
                               sub=sub_oi), unsafe_allow_html=True)

        # Mini-gráfico (sparkline) do preço recente
        serie = vt.get("serie_preco")
        if serie:
            st.write("")
            st.caption("Preço — últimos períodos")
            cor_linha = VERDE if serie[-1] >= serie[0] else VERMELHO
            st.line_chart(pd.DataFrame({"preço": serie}), height=150, color=cor_linha)

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
