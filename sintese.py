"""Camada de sintese: combina os dois vereditos num veredito final.

O caso MAIS VALIOSO e a discordancia: quando fundamental e tecnica apontam para
lados opostos, o honesto e dizer que o sinal e ambiguo, nao forcar um cima/baixo.

Sobre a confianca: quando os dois concordam, ha um bonus — mas proporcional ao
modulo MENOS confiante. Assim, dois palpites fracos que concordam NAO viram um
palpite forte (era o que inflava a confianca antes).
"""

TETO_FINAL = 0.8


def sintetizar(v_fundamental, v_tecnica):
    df_dir = v_fundamental["direcao"]
    dt_dir = v_tecnica["direcao"]
    cf = v_fundamental.get("confianca", 0.0)
    ct = v_tecnica.get("confianca", 0.0)
    opinaram = [d for d in (df_dir, dt_dir) if d in ("cima", "baixo")]

    # Ninguem cravou direcao.
    if not opinaram:
        return _final("indefinido", 0.0, "indefinido", "Nenhum modulo cravou uma direcao.")

    # So um modulo opinou (tipico no modo gratis, sem o fundamental).
    if df_dir == "indefinido" or dt_dir == "indefinido":
        if dt_dir in ("cima", "baixo"):
            ativo, conf = v_tecnica, ct
        else:
            ativo, conf = v_fundamental, cf
        conf = round(conf * 0.7, 2)  # desconto por faltar confirmacao do outro lado
        return _final(ativo["direcao"], conf, "parcial",
                      f"So o modulo '{ativo['modulo']}' opinou; o outro ficou indefinido.")

    # Os dois opinaram e CONCORDAM.
    if df_dir == dt_dir:
        media = (cf + ct) / 2
        bonus = 0.15 * min(cf, ct)  # bonus so e relevante se AMBOS estao confiantes
        conf = round(min(media + bonus, TETO_FINAL), 2)
        return _final(df_dir, conf, "concordam",
                      "Fundamental e tecnica apontam para o mesmo lado.")

    # Os dois opinaram e DISCORDAM — o resultado mais honesto.
    return _final("ambiguo", 0.15, "discordam",
                  f"Fundamental diz '{df_dir}' e tecnica diz '{dt_dir}'. "
                  f"Sinal ambiguo — melhor nao cravar.")


def _final(direcao, confianca, concordancia, resumo):
    return {
        "direcao": direcao,
        "confianca": confianca,
        "concordancia": concordancia,
        "resumo": resumo,
        "aviso": "Ferramenta de pesquisa, nao sinal de trade. "
                 "Direcao de 1 periodo e dominada por ruido.",
    }
