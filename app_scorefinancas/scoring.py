"""Motor de cálculo de Score de Saúde Financeira.

Consome o payload JSON produzido pela Finances4You (GET /api/v1/transacoes)
e calcula uma pontuação de 0 a 100 (Rating A–E) distribuída por 4 pilares:
    1. Taxa de Poupança (máx. 35 pts)
    2. Equilíbrio Essencial vs. Lazer (máx. 25 pts)
    3. Liquidez / Reserva das Carteiras (máx. 25 pts)
    4. Controlo de Pendentes (máx. 15 pts)
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


CATEGORIA_SALDO_INICIAL = "Saldo Inicial"
CATEGORIAS_ESSENCIAIS = {"Alimentação", "Casa", "Saúde", "Transportes"}
CATEGORIAS_DISCRICIONARIAS = {"Lazer"}


def _dec(valor):
    return Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _pct(numerador, denominador):
    if denominador <= 0:
        return Decimal("0.0")
    bruto = (Decimal(numerador) / Decimal(denominador)) * Decimal("100")
    limitado = max(Decimal("0.0"), min(Decimal("100.0"), bruto))
    return limitado.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _fmt_pct_pt(valor_dec):
    return f"{valor_dec:.1f}".replace(".", ",") + "%"


def _estado_por_percentagem(pct):
    if pct >= Decimal("80.0"):
        return "otimo"
    if pct >= Decimal("60.0"):
        return "bom"
    if pct >= Decimal("40.0"):
        return "alerta"
    return "critico"


def _classificar_natureza(categoria):
    if categoria in CATEGORIAS_ESSENCIAIS:
        return "essencial"
    if categoria in CATEGORIAS_DISCRICIONARIAS:
        return "discricionario"
    return "outros"


def _rating_global(pontuacao):
    if pontuacao >= 85:
        return "A", "Excelente"
    if pontuacao >= 70:
        return "B", "Bom"
    if pontuacao >= 50:
        return "C", "Razoável"
    if pontuacao >= 30:
        return "D", "Atenção"
    return "E", "Crítico"


def calcular_avaliacao(dados_json):
    """Calcula o resumo financeiro, os 4 pilares, o score global e recomendações."""
    periodo = dados_json["periodo"]
    data_inicio = date.fromisoformat(periodo["data_inicio"])
    data_fim = date.fromisoformat(periodo["data_fim"])
    dias_periodo = max(1, (data_fim - data_inicio).days + 1)
    meses_periodo = max(Decimal("1.0"), Decimal(dias_periodo) / Decimal("30"))

    carteiras = dados_json.get("carteiras", [])
    transacoes = dados_json.get("transacoes", [])

    saldo_total_carteiras = sum((_dec(c["saldo"]) for c in carteiras), Decimal("0.00"))

    # Excluir "Saldo Inicial" dos fluxos do período para não distorcer receitas reais
    transacoes_operacionais = [
        t for t in transacoes if t.get("categoria") != CATEGORIA_SALDO_INICIAL
    ]

    total_receitas = Decimal("0.00")
    total_despesas = Decimal("0.00")
    transacoes_pendentes = 0
    despesas_por_categoria = defaultdict(lambda: Decimal("0.00"))

    for t in transacoes_operacionais:
        valor = _dec(t["valor"])
        if not t.get("aplicada", True):
            transacoes_pendentes += 1

        if t["tipo"] == "receita":
            total_receitas += valor
        else:
            total_despesas += valor
            despesas_por_categoria[t["categoria"]] += valor

    resultado_liquido = (total_receitas - total_despesas).quantize(Decimal("0.01"))
    total_transacoes = len(transacoes_operacionais)

    # ------------------------------------------------------------------
    # Pilar 1: Taxa de Poupança (máx. 35 pts)
    # ------------------------------------------------------------------
    max_poupanca = 35
    if total_receitas > 0:
        taxa_poupanca = ((resultado_liquido / total_receitas) * Decimal("100")).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
        indicador_poupanca = _fmt_pct_pt(taxa_poupanca)
        if taxa_poupanca >= Decimal("20.0"):
            pts_poupanca = 35
            det_poupanca = "Poupa pelo menos 20% das receitas do período, superando a referência recomendada."
        elif taxa_poupanca >= Decimal("10.0"):
            pts_poupanca = 25
            det_poupanca = "Taxa de poupança positiva entre 10% e 20%; há margem para reforçar a poupança."
        elif taxa_poupanca >= Decimal("0.0"):
            pts_poupanca = 15
            det_poupanca = "Receitas cobrem as despesas, mas a folga de poupança é reduzida (abaixo de 10%)."
        else:
            pts_poupanca = 5 if taxa_poupanca >= Decimal("-15.0") else 0
            det_poupanca = "As despesas ultrapassaram as receitas no período, gerando défice financeiro."
    elif total_despesas == 0:
        pts_poupanca = 20
        indicador_poupanca = "Sem movimentos"
        det_poupanca = "Não foram registadas receitas nem despesas operacionais neste período."
    else:
        pts_poupanca = 0
        indicador_poupanca = "Sem receitas"
        det_poupanca = "Existem despesas registadas sem receitas operacionais no período selecionado."

    pct_poupanca = _pct(pts_poupanca, max_poupanca)
    pilar_poupanca = {
        "codigo": "poupanca",
        "nome": "Taxa de Poupança",
        "pontuacao": pts_poupanca,
        "maximo": max_poupanca,
        "percentagem": pct_poupanca,
        "indicador_valor": indicador_poupanca,
        "estado": _estado_por_percentagem(pct_poupanca),
        "detalhes": det_poupanca,
    }

    # ------------------------------------------------------------------
    # Pilar 2: Equilíbrio Essencial vs. Lazer (máx. 25 pts)
    # ------------------------------------------------------------------
    max_equilibrio = 25
    total_discricionario_outros = sum(
        (
            val
            for cat, val in despesas_por_categoria.items()
            if _classificar_natureza(cat) != "essencial"
        ),
        Decimal("0.00"),
    )
    if total_despesas > 0:
        peso_nao_essencial = _pct(total_discricionario_outros, total_despesas)
        indicador_equilibrio = f"{_fmt_pct_pt(peso_nao_essencial)} não essencial"
        if peso_nao_essencial <= Decimal("30.0"):
            pts_equilibrio = 25
            det_equilibrio = "Excelente equilíbrio: despesas em Lazer e Outros mantêm-se até 30% do total."
        elif peso_nao_essencial <= Decimal("45.0"):
            pts_equilibrio = 17
            det_equilibrio = "Despesas não essenciais moderadas (entre 30% e 45% do total gasto)."
        elif peso_nao_essencial <= Decimal("60.0"):
            pts_equilibrio = 9
            det_equilibrio = "Peso elevado em Lazer e Outros (45% a 60%), reduzindo a eficiência do orçamento."
        else:
            pts_equilibrio = 3
            det_equilibrio = "Mais de 60% das despesas concentram-se fora de categorias essenciais."
    else:
        pts_equilibrio = 20
        indicador_equilibrio = "Sem despesas"
        det_equilibrio = "Não existem despesas registadas no período para avaliar a distribuição."

    pct_equilibrio = _pct(pts_equilibrio, max_equilibrio)
    pilar_equilibrio = {
        "codigo": "equilibrio",
        "nome": "Equilíbrio Essencial vs. Lazer",
        "pontuacao": pts_equilibrio,
        "maximo": max_equilibrio,
        "percentagem": pct_equilibrio,
        "indicador_valor": indicador_equilibrio,
        "estado": _estado_por_percentagem(pct_equilibrio),
        "detalhes": det_equilibrio,
    }

    # ------------------------------------------------------------------
    # Pilar 3: Liquidez / Reserva das Carteiras (máx. 25 pts)
    # ------------------------------------------------------------------
    max_liquidez = 25
    despesa_media_mensal = total_despesas / meses_periodo
    if despesa_media_mensal > 0:
        meses_reserva = (saldo_total_carteiras / despesa_media_mensal).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
        indicador_liquidez = f"{meses_reserva:.1f}".replace(".", ",") + " meses de reserva"
        if meses_reserva >= Decimal("3.0"):
            pts_liquidez = 25
            det_liquidez = "Reserva sólida nas carteiras, cobrindo 3 ou mais meses de despesa média."
        elif meses_reserva >= Decimal("1.5"):
            pts_liquidez = 18
            det_liquidez = "Boa liquidez de curto prazo (entre 1,5 e 3 meses de despesas)."
        elif meses_reserva >= Decimal("0.5"):
            pts_liquidez = 10
            det_liquidez = "Liquidez limitada (menos de 1,5 meses de reserva disponível)."
        else:
            pts_liquidez = 3
            det_liquidez = "Fundo de emergência muito baixo face ao ritmo atual de despesas."
    else:
        if saldo_total_carteiras > 0:
            pts_liquidez = 25
            indicador_liquidez = f"{saldo_total_carteiras:.2f}".replace(".", ",") + " € disponíveis"
            det_liquidez = "Saldo positivo em carteiras sem despesas registadas no período."
        else:
            pts_liquidez = 10
            indicador_liquidez = "0,00 € disponíveis"
            det_liquidez = "Carteiras sem saldo disponível neste momento."

    pct_liquidez = _pct(pts_liquidez, max_liquidez)
    pilar_liquidez = {
        "codigo": "liquidez",
        "nome": "Liquidez das Carteiras",
        "pontuacao": pts_liquidez,
        "maximo": max_liquidez,
        "percentagem": pct_liquidez,
        "indicador_valor": indicador_liquidez,
        "estado": _estado_por_percentagem(pct_liquidez),
        "detalhes": det_liquidez,
    }

    # ------------------------------------------------------------------
    # Pilar 4: Controlo de Pendentes (máx. 15 pts)
    # ------------------------------------------------------------------
    max_pendentes = 15
    if total_transacoes > 0:
        taxa_aplicadas = _pct(total_transacoes - transacoes_pendentes, total_transacoes)
        indicador_pendentes = f"{_fmt_pct_pt(taxa_aplicadas)} aplicadas"
        if taxa_aplicadas >= Decimal("95.0"):
            pts_pendentes = 15
            det_pendentes = "Praticamente todas as transações do período já estão liquidadas."
        elif taxa_aplicadas >= Decimal("80.0"):
            pts_pendentes = 11
            det_pendentes = "Bom controlo de agendamentos, com poucos movimentos ainda pendentes."
        elif taxa_aplicadas >= Decimal("60.0"):
            pts_pendentes = 6
            det_pendentes = "Volume moderado de transações pendentes; acompanhe os próximos débitos."
        else:
            pts_pendentes = 2
            det_pendentes = "Mais de 40% das transações continuam pendentes de aplicação."
    else:
        pts_pendentes = 15
        indicador_pendentes = "Sem pendentes"
        det_pendentes = "Não existem compromissos pendentes no período."

    pct_pendentes = _pct(pts_pendentes, max_pendentes)
    pilar_pendentes = {
        "codigo": "pendentes",
        "nome": "Controlo de Pendentes",
        "pontuacao": pts_pendentes,
        "maximo": max_pendentes,
        "percentagem": pct_pendentes,
        "indicador_valor": indicador_pendentes,
        "estado": _estado_por_percentagem(pct_pendentes),
        "detalhes": det_pendentes,
    }

    pilares = [pilar_poupanca, pilar_equilibrio, pilar_liquidez, pilar_pendentes]
    pontuacao_global = sum(p["pontuacao"] for p in pilares)
    rating, classificacao = _rating_global(pontuacao_global)

    # Distribuição de despesas por categoria (ordenada do maior para o menor valor)
    distribuicao_categorias = []
    for nome_cat, total_cat in sorted(
        despesas_por_categoria.items(), key=lambda item: (-item[1], item[0])
    ):
        distribuicao_categorias.append(
            {
                "nome": nome_cat,
                "natureza": _classificar_natureza(nome_cat),
                "total": total_cat,
                "percentagem": _pct(total_cat, total_despesas),
            }
        )

    # Recomendações automáticas com base nos pilares abaixo de 70%
    recomendacoes = []
    mensagens_por_pilar = {
        "poupanca": "Procure aumentar a sua taxa de poupança para pelo menos 20% das receitas, revendo despesas recorrentes.",
        "equilibrio": "Reduza o peso de despesas em Lazer e Outros para menos de 30% do total de gastos do período.",
        "liquidez": "Reforce o saldo das suas carteiras até acumular uma reserva equivalente a pelo menos 3 meses de despesas.",
        "pendentes": "Reveja as transações agendadas/pendentes para garantir que o saldo futuro cobre todos os compromissos.",
    }
    for pilar in sorted(pilares, key=lambda p: p["percentagem"]):
        if pilar["percentagem"] < Decimal("40.0"):
            recomendacoes.append(
                {"prioridade": "alta", "texto": mensagens_por_pilar[pilar["codigo"]]}
            )
        elif pilar["percentagem"] < Decimal("70.0"):
            recomendacoes.append(
                {"prioridade": "media", "texto": mensagens_por_pilar[pilar["codigo"]]}
            )

    if not recomendacoes:
        recomendacoes.append(
            {
                "prioridade": "baixa",
                "texto": "Excelente gestão financeira! Todos os pilares estão acima de 70% — mantenha a disciplina atual.",
            }
        )

    return {
        "resumo": {
            "total_receitas": total_receitas,
            "total_despesas": total_despesas,
            "resultado_liquido": resultado_liquido,
            "saldo_total_carteiras": saldo_total_carteiras,
            "total_transacoes": total_transacoes,
            "transacoes_pendentes": transacoes_pendentes,
        },
        "score_global": {
            "pontuacao": pontuacao_global,
            "rating": rating,
            "classificacao": classificacao,
        },
        "pilares": pilares,
        "distribuicao_categorias": distribuicao_categorias,
        "recomendacoes": recomendacoes,
    }
