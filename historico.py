"""Taxa-base condicional: 'quando os indicadores estavam assim, o que o preco fez depois?'

ATENCAO — a armadilha que voce mesmo precisa vigiar:
  1) Cada condicao a mais ENCOLHE a amostra. Se voce exigir RSI + MACD + funding
     + sentimento batendo ao mesmo tempo, sai de milhares de dias para uns 5 casos.
     5 casos nao e estatistica, e ruido.
  2) O mercado nao e estavel. Um padrao de 2021 pode estar morto em 2026.
Por isso esta funcao SEMPRE devolve n_amostra e uma confianca. Um veredito que
nao diz em quanta historia ele esta pisando nao deve ser levado a serio.
"""


def _bucket_rsi(v):
    if v < 30:
        return "sobrevendido"
    if v < 45:
        return "fraco"
    if v < 55:
        return "neutro"
    if v < 70:
        return "forte"
    return "sobrecomprado"


def _estado(linha):
    """Estado discreto dos indicadores numa linha do DataFrame.

    De proposito usamos POUCAS condicoes (RSI + sinal do MACD) para manter a
    amostra grande. Acrescentar mais condicoes aqui melhora a 'semelhanca' mas
    derruba o n — faca isso com consciencia.
    """
    return (
        _bucket_rsi(linha["rsi"]),
        "macd_bull" if linha["macd_hist"] > 0 else "macd_bear",
    )


def _confianca_amostra(n, pct):
    margem = abs(pct - 0.5)
    if n < 20:
        return "muito baixa"
    if n < 50:
        return "baixa"
    if n < 150:
        return "media" if margem >= 0.05 else "baixa"
    return "alta" if margem >= 0.07 else "media"


def taxa_base_condicional(df, horizonte_periodos=1):
    """Compara o estado atual com o historico e mede quantas vezes o preco subiu depois."""
    estado_atual = _estado(df.iloc[-1])
    altas = 0
    total = 0
    # Vai ate len-horizonte para sempre existir um retorno futuro disponivel.
    for i in range(50, len(df) - horizonte_periodos):
        if _estado(df.iloc[i]) == estado_atual:
            atual = df["close"].iloc[i]
            futuro = df["close"].iloc[i + horizonte_periodos]
            total += 1
            if futuro > atual:
                altas += 1
    pct_alta = (altas / total) if total else 0.5
    return {
        "estado_atual": estado_atual,
        "n_amostra": total,
        "pct_alta": round(pct_alta, 3),
        "confianca_amostra": _confianca_amostra(total, pct_alta),
    }
