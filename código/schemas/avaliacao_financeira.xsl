<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:av="http://finances4you.pt/schemas/avaliacao-financeira"
                exclude-result-prefixes="av">

    <xsl:output method="html" encoding="UTF-8" indent="yes" omit-xml-declaration="yes"/>

    <xsl:template match="/av:AvaliacaoFinanceira">
        <div class="relatorio-score">
            <!-- Cartão principal de destaque do Score -->
            <section class="cartao-score-hero rating-{av:ScoreGlobal/av:Rating}">
                <div class="score-hero-info">
                    <span class="score-etiqueta">Avaliação de Saúde Financeira</span>
                    <h1 class="score-titulo">
                        <xsl:value-of select="av:ScoreGlobal/av:Classificacao"/>
                    </h1>
                    <p class="score-meta">
                        Utilizador:
                        <strong>
                            <xsl:value-of select="av:Utilizador/av:Nome"/>
                            <xsl:text> </xsl:text>
                            <xsl:value-of select="av:Utilizador/av:Apelido"/>
                        </strong>
                        <xsl:text> · Período: </xsl:text>
                        <strong><xsl:value-of select="av:Periodo/av:DataInicio"/></strong>
                        <xsl:text> a </xsl:text>
                        <strong><xsl:value-of select="av:Periodo/av:DataFim"/></strong>
                    </p>
                </div>

                <div class="score-hero-badge">
                    <div class="score-circulo">
                        <strong class="score-numero">
                            <xsl:value-of select="av:ScoreGlobal/av:Pontuacao"/>
                        </strong>
                        <span class="score-de-100">/ 100</span>
                    </div>
                    <span class="badge-rating rating-{av:ScoreGlobal/av:Rating}">
                        Rating <xsl:value-of select="av:ScoreGlobal/av:Rating"/>
                    </span>
                </div>
            </section>

            <!-- Resumo financeiro do período -->
            <section class="quadro-resumo score-resumo-grid">
                <div class="bloco-resumo">
                    <span class="rotulo-resumo">Total de receitas</span>
                    <strong class="valor-resumo valor-receita">
                        +<xsl:value-of select="translate(av:ResumoFinanceiro/av:TotalReceitas, '.', ',')"/> €
                    </strong>
                </div>
                <div class="bloco-resumo">
                    <span class="rotulo-resumo">Total de despesas</span>
                    <strong class="valor-resumo valor-despesa">
                        −<xsl:value-of select="translate(av:ResumoFinanceiro/av:TotalDespesas, '.', ',')"/> €
                    </strong>
                </div>
                <div class="bloco-resumo">
                    <span class="rotulo-resumo">Resultado líquido</span>
                    <xsl:choose>
                        <xsl:when test="number(av:ResumoFinanceiro/av:ResultadoLiquido) &gt;= 0">
                            <strong class="valor-resumo valor-receita">
                                +<xsl:value-of select="translate(av:ResumoFinanceiro/av:ResultadoLiquido, '.', ',')"/> €
                            </strong>
                        </xsl:when>
                        <xsl:otherwise>
                            <strong class="valor-resumo valor-despesa">
                                <xsl:value-of select="translate(av:ResumoFinanceiro/av:ResultadoLiquido, '.', ',')"/> €
                            </strong>
                        </xsl:otherwise>
                    </xsl:choose>
                </div>
                <div class="bloco-resumo">
                    <span class="rotulo-resumo">Saldo total em carteiras</span>
                    <strong class="valor-resumo">
                        <xsl:value-of select="translate(av:ResumoFinanceiro/av:SaldoTotalCarteiras, '.', ',')"/> €
                    </strong>
                </div>
            </section>

            <!-- Os 4 pilares do score -->
            <section class="quadro-relatorio">
                <h2>Análise por Pilar</h2>
                <div class="grelha-pilares">
                    <xsl:for-each select="av:Pilares/av:Pilar">
                        <article class="cartao-pilar estado-{av:Estado}">
                            <div class="pilar-topo">
                                <h3><xsl:value-of select="av:Nome"/></h3>
                                <span class="pilar-pontos">
                                    <strong><xsl:value-of select="av:Pontuacao"/></strong> / <xsl:value-of select="av:Maximo"/> pts
                                </span>
                            </div>

                            <div class="pilar-indicador">
                                <span><xsl:value-of select="av:IndicadorValor"/></span>
                                <span class="etiqueta-estado estado-{av:Estado}">
                                    <xsl:choose>
                                        <xsl:when test="av:Estado = 'otimo'">Ótimo</xsl:when>
                                        <xsl:when test="av:Estado = 'bom'">Bom</xsl:when>
                                        <xsl:when test="av:Estado = 'alerta'">Alerta</xsl:when>
                                        <xsl:otherwise>Crítico</xsl:otherwise>
                                    </xsl:choose>
                                </span>
                            </div>

                            <div class="barra-progresso" role="progressbar"
                                 aria-valuenow="{av:Pontuacao}"
                                 aria-valuemin="0"
                                 aria-valuemax="{av:Maximo}">
                                <div class="barra-progresso-preenchimento estado-{av:Estado}"
                                     style="width: {av:Percentagem}%;"/>
                            </div>

                            <p class="pilar-detalhes"><xsl:value-of select="av:Detalhes"/></p>
                        </article>
                    </xsl:for-each>
                </div>
            </section>

            <!-- Distribuição de despesas por categoria -->
            <section class="quadro-relatorio">
                <h2>Distribuição de Despesas por Categoria</h2>
                <xsl:choose>
                    <xsl:when test="av:DistribuicaoCategorias/av:CategoriaResumo">
                        <table class="tabela-score">
                            <thead>
                                <tr>
                                    <th>Categoria</th>
                                    <th>Natureza</th>
                                    <th class="coluna-num">Peso</th>
                                    <th class="coluna-num">Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                <xsl:for-each select="av:DistribuicaoCategorias/av:CategoriaResumo">
                                    <tr>
                                        <td><strong><xsl:value-of select="av:Nome"/></strong></td>
                                        <td>
                                            <span class="etiqueta-natureza natureza-{@natureza}">
                                                <xsl:choose>
                                                    <xsl:when test="@natureza = 'essencial'">Essencial</xsl:when>
                                                    <xsl:when test="@natureza = 'discricionario'">Discricionário</xsl:when>
                                                    <xsl:otherwise>Outros</xsl:otherwise>
                                                </xsl:choose>
                                            </span>
                                        </td>
                                        <td class="coluna-num">
                                            <xsl:value-of select="translate(av:Percentagem, '.', ',')"/>%
                                        </td>
                                        <td class="coluna-num">
                                            <strong><xsl:value-of select="translate(av:Total, '.', ',')"/> €</strong>
                                        </td>
                                    </tr>
                                </xsl:for-each>
                            </tbody>
                        </table>
                    </xsl:when>
                    <xsl:otherwise>
                        <p class="sem-dados-relatorio">Não foram registadas despesas no período analisado.</p>
                    </xsl:otherwise>
                </xsl:choose>
            </section>

            <!-- Recomendações -->
            <section class="quadro-relatorio">
                <h2>Recomendações</h2>
                <ul class="lista-recomendacoes">
                    <xsl:for-each select="av:Recomendacoes/av:Recomendacao">
                        <li class="item-recomendacao prioridade-{@prioridade}">
                            <span class="badge-prioridade prioridade-{@prioridade}">
                                <xsl:choose>
                                    <xsl:when test="@prioridade = 'alta'">Prioridade Alta</xsl:when>
                                    <xsl:when test="@prioridade = 'media'">Prioridade Média</xsl:when>
                                    <xsl:otherwise>Nota Positiva</xsl:otherwise>
                                </xsl:choose>
                            </span>
                            <p><xsl:value-of select="."/></p>
                        </li>
                    </xsl:for-each>
                </ul>
            </section>

            <p class="score-rodape">
                Avaliação gerada em <xsl:value-of select="@dataAvaliacao"/>
                <xsl:text> · Transações analisadas: </xsl:text>
                <strong><xsl:value-of select="av:ResumoFinanceiro/av:TotalTransacoes"/></strong>
                <xsl:text> (Pendentes: </xsl:text>
                <strong><xsl:value-of select="av:ResumoFinanceiro/av:TransacoesPendentes"/></strong>
                <xsl:text>)</xsl:text>
            </p>
        </div>
    </xsl:template>

</xsl:stylesheet>
