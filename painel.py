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
from datetime import datetime

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

import registro                              # noqa: E402
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

VERDE, VERMELHO, NEUTRO = "#16C784", "#EA3943", "#616E85"
AZUL, LARANJA, ROXO = "#3861FB", "#F7931A", "#A66BFF"
SETA = {"cima": "⬆️", "baixo": "⬇️", "ambiguo": "↔️", "indefinido": "❓"}

# Intervalos suportados pela Binance (mesmos códigos da API de klines).
INTERVALOS = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h",
              "12h", "1d", "3d", "1w", "1M"]
INTERVALOS_LABEL = {
    "1m": "1 minuto", "3m": "3 minutos", "5m": "5 minutos", "15m": "15 minutos",
    "30m": "30 minutos", "1h": "1 hora", "2h": "2 horas", "4h": "4 horas",
    "6h": "6 horas", "8h": "8 horas", "12h": "12 horas", "1d": "1 dia",
    "3d": "3 dias", "1w": "1 semana", "1M": "1 mês"}


def _frase_alvo(intervalo, horizonte):
    """Frase do que está sendo previsto, ligada ao intervalo (a vela seguinte)."""
    lbl = INTERVALOS_LABEL.get(intervalo, intervalo)
    if horizonte <= 1:
        return f"a próxima vela de {lbl}"
    return f"as próximas {horizonte} velas de {lbl}"


POPULARES = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "ADAUSDT",
             "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT"]


@st.cache_data(ttl=3600, show_spinner=False)
def _ativos_disponiveis():
    """Lista de pares USDT da Binance (cacheada 1h), com os populares no topo."""
    from dados_binance import listar_pares_usdt
    pares = listar_pares_usdt()
    if not pares:
        return POPULARES  # fallback se a busca falhar
    topo = [p for p in POPULARES if p in pares]
    resto = [p for p in pares if p not in POPULARES]
    return topo + resto


@st.cache_data(ttl=60, show_spinner=False)
def _tecnica(ativo, intervalo, horizonte, modo_teste):
    """Análise técnica cacheada por 60s (clicar de novo no mesmo ativo é instantâneo)."""
    return analise_tecnica(ativo, intervalo, horizonte, 600, modo_teste)


@st.cache_data(ttl=120, show_spinner=False)
def _tecnica_leve(ativo, intervalo, modo_teste):
    """Versão leve (sem futuros) para a tabela de visão geral."""
    return analise_tecnica(ativo, intervalo, 1, 600, modo_teste, incluir_futuros=False)


def _indef(modulo):
    """Veredito vazio para um módulo que o usuário optou por NÃO rodar."""
    return {"modulo": modulo, "direcao": "indefinido", "confianca": 0.0,
            "raciocinio": "", "n_amostra": 0}


st.session_state.setdefault("recentes", [])

with st.sidebar:
    st.header("Configurar análise")
    lista_ativos = _ativos_disponiveis()

    if st.session_state["recentes"]:
        st.caption("Recentes")
        rcols = st.columns(len(st.session_state["recentes"]))
        for i, a in enumerate(st.session_state["recentes"]):
            if rcols[i].button(a.replace("USDT", ""), key=f"rec_{a}",
                               width="stretch"):
                st.session_state["ativo_widget"] = a
                st.rerun()

    ativo = st.selectbox(
        "Ativo", lista_ativos, key="ativo_widget",
        help="Qual criptomoeda analisar — a lista traz TODOS os pares USDT da "
             "Binance (os mais conhecidos no topo). Digite para buscar, ex.: "
             "'ADA', 'DOGE', 'PEPE'. O par termina em USDT porque o preço é "
             "cotado em dólar (BTCUSDT = Bitcoin, ETHUSDT = Ethereum…).")
    st.caption(f"{len(lista_ativos)} pares disponíveis")
    intervalo = st.selectbox(
        "Intervalo (vela da Binance)", INTERVALOS, index=INTERVALOS.index("1d"),
        help="O tamanho de cada vela — os MESMOS intervalos da Binance "
             "(1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M…). A análise prevê a "
             "PRÓXIMA vela desse intervalo: escolha 15m e ela olha a próxima "
             "vela de 15 minutos. Menores reagem rápido mas têm mais ruído.")
    horizonte = st.number_input(
        "Quantas velas à frente prever", 1, 30, 1,
        help="Quantas velas do intervalo escolhido prever. 1 = a próxima vela "
             "(o padrão). Ex.: intervalo 15m + 1 = próxima vela de 15 min; "
             "15m + 4 = daqui a 4 velas (1 hora). Quanto mais à frente, mais incerto.")
    st.caption(f"→ Vai analisar **{_frase_alvo(intervalo, int(horizonte))}**.")
    pontos = st.select_slider(
        "Pontos no gráfico", options=[30, 60, 120], value=60,
        help="Quantos períodos recentes mostrar no gráfico de preço.")
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
        "🔎 Analisar", type="primary", width="stretch",
        help="Roda as análises marcadas acima e mostra o veredito final. "
             "A parte de notícias pesquisa na web e pode levar alguns segundos.")

tem_chave = bool(os.environ.get("ANTHROPIC_API_KEY"))
if usar_fundamental and not tem_chave and not modo_teste:
    st.info("Sem chave de API configurada: a análise de notícias não vai rodar "
            "(só a técnica). Desmarque '📰 Fundamental' para esconder este aviso.")


def _bloco_metricas(vt):
    """Cards de preço/indicadores/futuros + gráfico (preço + médias)."""
    cols = st.columns(4)
    var = vt.get("variacao_pct", 0.0)
    cor_var = VERDE if var >= 0 else VERMELHO
    seta_var = "▲" if var >= 0 else "▼"
    sub_preco = (f"<span style='color:{cor_var};font-weight:600'>"
                 f"{seta_var} {var:+.2f}%</span> no período")
    cols[0].markdown(_card("Preço atual", f"${vt['preco_atual']:,.2f}", sub=sub_preco),
                     unsafe_allow_html=True)

    rsi = vt["indicadores"]["rsi"]
    if rsi > 70:
        cor_rsi, zona = VERMELHO, "sobrecomprado"
    elif rsi < 30:
        cor_rsi, zona = VERDE, "sobrevendido"
    else:
        cor_rsi, zona = NEUTRO, "neutro"
    cols[1].markdown(_card("RSI", f"{rsi}", cor=cor_rsi, sub=zona), unsafe_allow_html=True)

    macd_h = vt["indicadores"]["macd_hist"]
    cols[2].markdown(_card("MACD hist", f"{macd_h}",
                           cor=VERDE if macd_h >= 0 else VERMELHO,
                           sub="momentum"), unsafe_allow_html=True)

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

    # Funding rate + Long/Short (com reserva OKX para funcionar na nuvem)
    st.write("")
    f2 = st.columns(2)
    fr = vt["futuros"].get("funding_rate")
    if fr is not None:
        nota = "longs pagam shorts" if fr >= 0 else "shorts pagam longs"
        f2[0].markdown(_card("Funding rate", f"{fr * 100:+.4f}%",
                             cor=VERDE if fr >= 0 else VERMELHO, sub=nota),
                       unsafe_allow_html=True)
    else:
        f2[0].markdown(_card("Funding rate", "—", sub="indisponível"),
                       unsafe_allow_html=True)
    ls = vt["futuros"].get("long_short_ratio")
    if ls is not None:
        f2[1].markdown(_card("Long / Short", f"{ls:.2f}",
                             cor=VERDE if ls >= 1 else VERMELHO,
                             sub="> 1 = mais comprados"), unsafe_allow_html=True)
    else:
        f2[1].markdown(_card("Long / Short", "—", sub="indisponível"),
                       unsafe_allow_html=True)

    # Gráfico: preço + médias móveis (SMA50 / EMA21)
    serie = vt.get("serie_preco") or []
    if serie:
        n = min(int(pontos), len(serie))
        dfc = pd.DataFrame({
            "Preço": serie[-n:],
            "SMA50": (vt.get("serie_sma50") or [None] * n)[-n:],
            "EMA21": (vt.get("serie_ema21") or [None] * n)[-n:],
        })
        st.write("")
        st.caption("Preço + médias móveis (últimos períodos)")
        st.line_chart(dfc, height=260, color=[AZUL, LARANJA, ROXO])


tab_det, tab_geral, tab_hist = st.tabs(
    ["🔎 Análise detalhada", "📊 Visão geral", "🕘 Histórico"])

with tab_det:
    if analisar and not usar_tecnica and not usar_fundamental:
        st.warning("Marque ao menos uma análise (📈 Técnica e/ou 📰 Fundamental) "
                   "na barra lateral.")
    elif analisar:
        with st.spinner("Analisando… (se as notícias estiverem ligadas, "
                        "a pesquisa na web pode levar alguns segundos)"):
            vt = (_tecnica(ativo, intervalo, int(horizonte), modo_teste)
                  if usar_tecnica else _indef("tecnica"))
            vf = (analise_fundamental(ativo, int(horizonte))
                  if usar_fundamental else _indef("fundamental"))
            final = sintetizar(vf, vt)

        # registra nos recentes (mais novo primeiro, sem repetir, máx. 4)
        rec = [a for a in st.session_state["recentes"] if a != ativo]
        st.session_state["recentes"] = ([ativo] + rec)[:4]

        # grava no histórico de análises (disco)
        registro.registrar({
            "quando": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "ativo": ativo,
            "intervalo": intervalo,
            "alvo": _frase_alvo(intervalo, int(horizonte)),
            "direcao": final["direcao"],
            "confianca": final["confianca"],
            "concordancia": final["concordancia"],
            "tecnica": vt.get("direcao"),
            "fundamental": vf.get("direcao"),
            "teste": bool(modo_teste),
        })

        if usar_tecnica and vt.get("dados_sinteticos"):
            st.warning("MODO TESTE: dados sintéticos — não refletem o mercado real.")

        st.subheader(f"Veredito final — {ativo}")
        legenda = f"Prevendo **{_frase_alvo(intervalo, int(horizonte))}**."
        if usar_tecnica and vt.get("ultimo_candle"):
            legenda += f"  ·  Vela mais recente: {vt['ultimo_candle']} (UTC)."
        st.caption(legenda)

        cor_dir = COR_DIR.get(final["direcao"], "#0D1421")
        c1, c2, c3 = st.columns(3)
        c1.markdown(_card("Direção",
                          f"{SETA.get(final['direcao'], '')} {final['direcao'].upper()}",
                          cor=cor_dir), unsafe_allow_html=True)
        c2.markdown(_card("Confiança", f"{final['confianca']:.2f}",
                          sub="0 a 1 — teto baixo de propósito"), unsafe_allow_html=True)
        c3.markdown(_card("Concordância", final["concordancia"].capitalize()),
                    unsafe_allow_html=True)
        st.progress(min(max(float(final["confianca"]), 0.0), 1.0))
        st.caption(final["resumo"])
        st.write("")

        if usar_tecnica:
            _bloco_metricas(vt)

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
                if vt.get("hist_pct_alta") is not None:
                    st.caption(f"🕮 Histórico: em {vt['n_amostra']} casos parecidos, "
                               f"subiu {vt['hist_pct_alta'] * 100:.0f}% das vezes "
                               f"(confiança da amostra: {vt.get('hist_confianca', '-')}).")
                st.write(_texto_seguro(vt["raciocinio"]))
                with st.expander("Indicadores e futuros (detalhe)"):
                    st.json({"indicadores": vt["indicadores"], "futuros": vt["futuros"]})

        # Exportar resumo
        resumo_txt = (
            f"Agente Cripto — {ativo} ({intervalo}, horizonte {int(horizonte)})\n"
            f"Vela mais recente: {vt.get('ultimo_candle', '-')} UTC\n\n"
            f"VEREDITO FINAL: {final['direcao'].upper()} "
            f"(confianca {final['confianca']:.2f}, {final['concordancia']})\n"
            f"{final['resumo']}\n\n"
            f"Tecnica: {vt['direcao']} (conf {vt.get('confianca', '-')}) — "
            f"{vt.get('raciocinio', '')}\n\n"
            f"Fundamental: {vf['direcao']} (conf {vf.get('confianca', '-')}) — "
            f"{vf.get('raciocinio', '')}\n")
        st.download_button("⬇️ Baixar resumo (.txt)", resumo_txt,
                           file_name=f"{ativo}_analise.txt", mime="text/plain")

        st.caption("⚠️ " + final["aviso"] +
                   " Olhe sempre o raciocínio e o n_amostra, não só o número da confiança.")
    else:
        st.info("Escolha o ativo na barra lateral e clique em **🔎 Analisar**.")

with tab_geral:
    st.markdown("#### Comparar vários ativos de uma vez")
    st.caption("Só a parte técnica (rápida, sem gastar API). Use o **Intervalo** "
               "escolhido na barra lateral.")
    sel = st.multiselect("Ativos para comparar", lista_ativos,
                         default=POPULARES[:6], max_selections=15)
    if st.button("📊 Comparar", type="primary"):
        if not sel:
            st.info("Escolha ao menos um ativo.")
        else:
            linhas, prog = [], st.progress(0.0)
            for i, a in enumerate(sel):
                try:
                    v = _tecnica_leve(a, intervalo, modo_teste)
                    linhas.append({
                        "Ativo": a.replace("USDT", ""),
                        "Preço": v["preco_atual"],
                        "Variação %": v.get("variacao_pct", 0.0),
                        "RSI": v["indicadores"]["rsi"],
                        "Direção": f"{SETA.get(v['direcao'], '')} {v['direcao']}",
                        "Tendência": [x for x in (v.get("serie_preco") or []) if x is not None],
                    })
                except Exception:
                    linhas.append({"Ativo": a.replace("USDT", ""), "Preço": None,
                                   "Variação %": None, "RSI": None,
                                   "Direção": "erro", "Tendência": []})
                prog.progress((i + 1) / len(sel))
            prog.empty()
            st.dataframe(
                pd.DataFrame(linhas), hide_index=True, width="stretch",
                column_config={
                    "Preço": st.column_config.NumberColumn(format="$%.4f"),
                    "Variação %": st.column_config.NumberColumn(format="%.2f%%"),
                    "RSI": st.column_config.NumberColumn(format="%.0f"),
                    "Tendência": st.column_config.LineChartColumn("Tendência", width="medium"),
                })
            st.caption("⚠️ Pesquisa, não sinal de trade. Direção de 1 período é "
                       "dominada por ruído — olhe o conjunto, não um número isolado.")

with tab_hist:
    st.markdown("#### Histórico de análises")
    st.caption("Cada análise detalhada que você roda fica registrada aqui "
               "(mais recente no topo). Persiste ao recarregar a página.")
    hist = registro.listar(100)
    if not hist:
        st.info("Ainda não há análises. Rode uma na aba **🔎 Análise detalhada**.")
    else:
        dfh = pd.DataFrame(hist)
        ordem = ["quando", "ativo", "intervalo", "direcao", "confianca",
                 "concordancia", "tecnica", "fundamental", "teste"]
        dfh = dfh[[c for c in ordem if c in dfh.columns]].rename(columns={
            "quando": "Quando", "ativo": "Ativo", "intervalo": "Interv.",
            "direcao": "Direção", "confianca": "Confiança",
            "concordancia": "Concord.", "tecnica": "Téc.",
            "fundamental": "Fund.", "teste": "Teste"})
        st.dataframe(
            dfh, hide_index=True, width="stretch",
            column_config={
                "Confiança": st.column_config.NumberColumn(format="%.2f"),
                "Teste": st.column_config.CheckboxColumn(),
            })
        st.caption(f"{len(hist)} análise(s) no histórico.")
        h1, h2 = st.columns(2)
        h1.download_button(
            "⬇️ Baixar histórico (CSV)",
            dfh.to_csv(index=False).encode("utf-8"),
            file_name="historico_analises.csv", mime="text/csv", width="stretch")
        if h2.button("🗑️ Limpar histórico", width="stretch"):
            registro.limpar()
            st.rerun()

with st.expander("❓ Como ler este painel"):
    st.markdown("""
- **Direção / Confiança / Concordância:** o veredito final junta a técnica e a fundamental.
  Quando elas **discordam**, o resultado é `ambíguo` de propósito — é o sinal mais honesto.
- **Confiança (0 a 1):** tem **teto baixo de propósito**. Direção de 1 período é dominada por
  ruído, então um número alto seria desonesto. Olhe o **raciocínio** e o **n_amostra**.
- **n_amostra:** em quantos casos históricos parecidos o agente está se baseando. Poucos casos
  (amostra pequena) = pouca confiança, mesmo que os indicadores estejam alinhados.
- **RSI:** força do movimento. > 70 = sobrecomprado (esticado pra cima), < 30 = sobrevendido.
- **MACD hist:** momentum — positivo (verde) favorece alta, negativo (vermelho) favorece baixa.
- **Funding / Long-Short / Open interest:** termômetro do mercado de futuros (posicionamento).

**Ferramenta de pesquisa, não recomendação de investimento.**
""")
