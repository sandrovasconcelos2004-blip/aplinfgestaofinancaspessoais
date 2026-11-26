"""Utilitários para geração e validação de exportações XML de transações pessoais.

Constrói o documento XML no formato definido por ``schemas/transacoes_pessoais.xsd``
e valida-o rigorosamente contra o esquema XSD antes de o devolver ao cliente.
"""

from datetime import datetime
from decimal import Decimal
import os
from lxml import etree


NAMESPACE_TRANSACOES = "http://finances4you.pt/schemas/transacoes-pessoais"
NAMESPACE_AVALIACAO = "http://finances4you.pt/schemas/avaliacao-financeira"
DIRETORIO_SCHEMAS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "schemas",
)
CAMINHO_XSD = os.path.join(DIRETORIO_SCHEMAS, "transacoes_pessoais.xsd")
CAMINHO_XSD_AVALIACAO = os.path.join(DIRETORIO_SCHEMAS, "avaliacao_financeira.xsd")
CAMINHO_XSL_AVALIACAO = os.path.join(DIRETORIO_SCHEMAS, "avaliacao_financeira.xsl")


class ErroValidacaoXML(Exception):
    """Erro levantado quando o XML gerado não cumpre o esquema XSD."""


def carregar_esquema_xsd():
    """Carrega e compila o esquema XSD das transações pessoais."""
    documento_xsd = etree.parse(CAMINHO_XSD)
    return etree.XMLSchema(documento_xsd)


def _formatar_valor(valor):
    """Formata um valor numérico com exatamente duas casas decimais."""
    return f"{Decimal(valor).quantize(Decimal('0.01')):.2f}"


def gerar_xml_transacoes(utilizador, carteiras, categorias, transacoes, data_inicio, data_fim):
    """Gera o XML das transações pessoais do utilizador e valida-o contra o XSD.

    Parâmetros:
        utilizador: dicionário com ID_Utilizador, Nome, Apelido e Email.
        carteiras: lista de carteiras do utilizador (ID_Carteira, Carteira, Valor).
        categorias: lista de categorias referenciadas (ID_Categoria, Categoria, ID_Utilizador).
        transacoes: lista de transações do período (ID_Transacao, Transacao, Tipo,
                    Valor, Data, Aplicada, ID_Carteira, ID_Categoria).
        data_inicio: objeto ``date`` correspondente ao início do período (inclusivo).
        data_fim: objeto ``date`` correspondente ao fim do período (inclusivo).

    Devolve os bytes UTF-8 do documento XML validado.
    Levanta ``ErroValidacaoXML`` caso o documento não respeite o XSD.
    """
    ns = f"{{{NAMESPACE_TRANSACOES}}}"

    raiz = etree.Element(
        f"{ns}ExportacaoTransacoes",
        nsmap={None: NAMESPACE_TRANSACOES},
        attrib={
            "dataExportacao": datetime.now().replace(microsecond=0).isoformat(),
            "moeda": "EUR",
            "versao": "1.0",
        },
    )

    # Período escolhido pelo utilizador
    periodo_el = etree.SubElement(raiz, f"{ns}Periodo")
    etree.SubElement(periodo_el, f"{ns}DataInicio").text = data_inicio.isoformat()
    etree.SubElement(periodo_el, f"{ns}DataFim").text = data_fim.isoformat()

    # Dados públicos do utilizador autenticado (sem Password)
    utilizador_el = etree.SubElement(
        raiz,
        f"{ns}Utilizador",
        attrib={"id": str(utilizador["ID_Utilizador"])},
    )
    etree.SubElement(utilizador_el, f"{ns}Nome").text = utilizador["Nome"].strip()
    etree.SubElement(utilizador_el, f"{ns}Apelido").text = utilizador["Apelido"].strip()
    etree.SubElement(utilizador_el, f"{ns}Email").text = utilizador["Email"].strip()

    # Carteiras do utilizador
    carteiras_el = etree.SubElement(raiz, f"{ns}Carteiras")
    for carteira in carteiras:
        carteira_el = etree.SubElement(
            carteiras_el,
            f"{ns}Carteira",
            attrib={"id": str(carteira["ID_Carteira"])},
        )
        etree.SubElement(carteira_el, f"{ns}Nome").text = carteira["Carteira"].strip()
        etree.SubElement(carteira_el, f"{ns}Saldo").text = _formatar_valor(carteira["Valor"])

    # Categorias usadas nas transações exportadas
    categorias_el = etree.SubElement(raiz, f"{ns}Categorias")
    for categoria in categorias:
        categoria_el = etree.SubElement(
            categorias_el,
            f"{ns}Categoria",
            attrib={
                "id": str(categoria["ID_Categoria"])
            },
        )
        etree.SubElement(categoria_el, f"{ns}Nome").text = categoria["Categoria"].strip()

    # Transações pessoais no período
    transacoes_el = etree.SubElement(raiz, f"{ns}Transacoes")
    total_receitas = Decimal("0.00")
    total_despesas = Decimal("0.00")

    for transacao in transacoes:
        valor_dec = Decimal(transacao["Valor"]).quantize(Decimal("0.01"))
        if transacao["Tipo"] == "receita":
            total_receitas += valor_dec
        else:
            total_despesas += valor_dec

        transacao_el = etree.SubElement(
            transacoes_el,
            f"{ns}Transacao",
            attrib={
                "id": str(transacao["ID_Transacao"]),
                "idCarteira": str(transacao["ID_Carteira"]),
                "idCategoria": str(transacao["ID_Categoria"]),
            },
        )
        etree.SubElement(transacao_el, f"{ns}Descricao").text = transacao["Transacao"].strip()
        etree.SubElement(transacao_el, f"{ns}Tipo").text = transacao["Tipo"]
        etree.SubElement(transacao_el, f"{ns}Valor").text = f"{valor_dec:.2f}"
        etree.SubElement(transacao_el, f"{ns}Data").text = (
            transacao["Data"].replace(microsecond=0).isoformat()
        )
        etree.SubElement(transacao_el, f"{ns}Aplicada").text = (
            "true" if bool(transacao["Aplicada"]) else "false"
        )

    # Resumo do período exportado
    resumo_el = etree.SubElement(raiz, f"{ns}Resumo")
    etree.SubElement(resumo_el, f"{ns}TotalTransacoes").text = str(len(transacoes))
    etree.SubElement(resumo_el, f"{ns}TotalReceitas").text = f"{total_receitas:.2f}"
    etree.SubElement(resumo_el, f"{ns}TotalDespesas").text = f"{total_despesas:.2f}"
    etree.SubElement(resumo_el, f"{ns}ResultadoLiquido").text = (
        f"{(total_receitas - total_despesas):.2f}"
    )

    # Validação obrigatória contra o esquema XSD antes de exportar
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


def carregar_esquema_avaliacao_xsd():
    """Carrega e compila o esquema XSD do relatório de avaliação financeira."""
    documento_xsd = etree.parse(CAMINHO_XSD_AVALIACAO)
    return etree.XMLSchema(documento_xsd)


def validar_xml_avaliacao(xml_bytes):
    """Faz parse e valida o XML de avaliação financeira contra ``avaliacao_financeira.xsd``.

    Devolve o elemento raiz ``lxml.etree._Element`` se for válido.
    Levanta ``ErroValidacaoXML`` se o XML estiver mal formado ou violar o XSD.
    """
    try:
        documento = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as erro:
        raise ErroValidacaoXML(f"XML mal formado: {erro}") from erro

    esquema = carregar_esquema_avaliacao_xsd()
    try:
        esquema.assertValid(documento)
    except etree.DocumentInvalid as erro:
        raise ErroValidacaoXML(str(erro)) from erro

    return documento


def transformar_avaliacao_html(xml_bytes):
    """Valida o XML de avaliação financeira e transforma-o em HTML via XSLT."""
    documento = validar_xml_avaliacao(xml_bytes)
    folha_xsl = etree.parse(CAMINHO_XSL_AVALIACAO)
    transformacao = etree.XSLT(folha_xsl)
    resultado = transformacao(documento)
    return str(resultado)
