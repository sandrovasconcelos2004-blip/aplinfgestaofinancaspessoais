"""Construção e validação do documento XML de avaliação financeira.

Gera o XML conforme o contrato partilhado ``schemas/avaliacao_financeira.xsd``
e valida-o rigorosamente antes de ser devolvido à Finances4You.
"""

from datetime import datetime
from decimal import Decimal
import os
from lxml import etree


NAMESPACE_AVALIACAO = "http://finances4you.pt/schemas/avaliacao-financeira"
CAMINHO_XSD_AVALIACAO = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "schemas",
    "avaliacao_financeira.xsd",
)


class ErroValidacaoXML(Exception):
    """Erro levantado quando o XML gerado não cumpre o esquema XSD."""


def carregar_esquema_xsd():
    """Carrega e compila o esquema XSD de avaliação financeira."""
    documento_xsd = etree.parse(CAMINHO_XSD_AVALIACAO)
    return etree.XMLSchema(documento_xsd)


def _fmt_valor(valor):
    return f"{Decimal(valor).quantize(Decimal('0.01')):.2f}"


def _fmt_pct(valor):
    return f"{Decimal(valor).quantize(Decimal('0.1')):.1f}"


def gerar_xml_avaliacao(dados_json, avaliacao):
    """Constrói e valida contra o XSD o XML de avaliação de saúde financeira."""
    ns = f"{{{NAMESPACE_AVALIACAO}}}"

    raiz = etree.Element(
        f"{ns}AvaliacaoFinanceira",
        nsmap={None: NAMESPACE_AVALIACAO},
        attrib={
            "dataAvaliacao": datetime.now().replace(microsecond=0).isoformat(),
            "moeda": "EUR",
            "versao": "1.0",
        },
    )

    # Período analisado
    periodo_el = etree.SubElement(raiz, f"{ns}Periodo")
    etree.SubElement(periodo_el, f"{ns}DataInicio").text = dados_json["periodo"]["data_inicio"]
    etree.SubElement(periodo_el, f"{ns}DataFim").text = dados_json["periodo"]["data_fim"]

    # Utilizador
    u = dados_json["utilizador"]
    utilizador_el = etree.SubElement(raiz, f"{ns}Utilizador", attrib={"id": str(u["id"])})
    etree.SubElement(utilizador_el, f"{ns}Nome").text = u["nome"].strip()
    etree.SubElement(utilizador_el, f"{ns}Apelido").text = u["apelido"].strip()
    etree.SubElement(utilizador_el, f"{ns}Email").text = u["email"].strip()

    # Resumo Financeiro
    r = avaliacao["resumo"]
    resumo_el = etree.SubElement(raiz, f"{ns}ResumoFinanceiro")
    etree.SubElement(resumo_el, f"{ns}TotalReceitas").text = _fmt_valor(r["total_receitas"])
    etree.SubElement(resumo_el, f"{ns}TotalDespesas").text = _fmt_valor(r["total_despesas"])
    etree.SubElement(resumo_el, f"{ns}ResultadoLiquido").text = _fmt_valor(r["resultado_liquido"])
    etree.SubElement(resumo_el, f"{ns}SaldoTotalCarteiras").text = _fmt_valor(r["saldo_total_carteiras"])
    etree.SubElement(resumo_el, f"{ns}TotalTransacoes").text = str(r["total_transacoes"])
    etree.SubElement(resumo_el, f"{ns}TransacoesPendentes").text = str(r["transacoes_pendentes"])

    # Score Global
    sg = avaliacao["score_global"]
    score_el = etree.SubElement(raiz, f"{ns}ScoreGlobal")
    etree.SubElement(score_el, f"{ns}Pontuacao").text = str(sg["pontuacao"])
    etree.SubElement(score_el, f"{ns}Rating").text = sg["rating"]
    etree.SubElement(score_el, f"{ns}Classificacao").text = sg["classificacao"]

    # 4 Pilares
    pilares_el = etree.SubElement(raiz, f"{ns}Pilares")
    for p in avaliacao["pilares"]:
        pilar_el = etree.SubElement(pilares_el, f"{ns}Pilar", attrib={"codigo": p["codigo"]})
        etree.SubElement(pilar_el, f"{ns}Nome").text = p["nome"]
        etree.SubElement(pilar_el, f"{ns}Pontuacao").text = str(p["pontuacao"])
        etree.SubElement(pilar_el, f"{ns}Maximo").text = str(p["maximo"])
        etree.SubElement(pilar_el, f"{ns}Percentagem").text = _fmt_pct(p["percentagem"])
        etree.SubElement(pilar_el, f"{ns}IndicadorValor").text = p["indicador_valor"]
        etree.SubElement(pilar_el, f"{ns}Estado").text = p["estado"]
        etree.SubElement(pilar_el, f"{ns}Detalhes").text = p["detalhes"]

    # Distribuição de Categorias
    dist_el = etree.SubElement(raiz, f"{ns}DistribuicaoCategorias")
    for cat in avaliacao["distribuicao_categorias"]:
        cat_el = etree.SubElement(
            dist_el,
            f"{ns}CategoriaResumo",
            attrib={"natureza": cat["natureza"]},
        )
        etree.SubElement(cat_el, f"{ns}Nome").text = cat["nome"]
        etree.SubElement(cat_el, f"{ns}Total").text = _fmt_valor(cat["total"])
        etree.SubElement(cat_el, f"{ns}Percentagem").text = _fmt_pct(cat["percentagem"])

    # Recomendações
    recs_el = etree.SubElement(raiz, f"{ns}Recomendacoes")
    for rec in avaliacao["recomendacoes"]:
        rec_el = etree.SubElement(
            recs_el,
            f"{ns}Recomendacao",
            attrib={"prioridade": rec["prioridade"]},
        )
        rec_el.text = rec["texto"]

    # Validação obrigatória contra o esquema XSD partilhado
    esquema = carregar_esquema_xsd()
    try:
        esquema.assertValid(raiz)
    except etree.DocumentInvalid as erro:
        raise ErroValidacaoXML(str(erro)) from erro

    return etree.tostring(
        raiz,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8",
    )
