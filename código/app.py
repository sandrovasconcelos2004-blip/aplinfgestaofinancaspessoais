"""Aplicação Web de Gestão de Finanças Pessoais.

Este módulo define o servidor Flask principal, configurando as rotas para
autenticação (registo e login), navegação, gestão de sessão de utilizadores
e gestão de carteiras e transações e grupos.
"""


import os
from decimal import ROUND_DOWN, Decimal, InvalidOperation
from datetime import date, datetime, time, timedelta
import pymysql
from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from itsdangerous import BadSignature, URLSafeTimedSerializer
from email_utils import enviar_email


# Módulo local com a função de ligação à base de dados MariaDB
from db import obter_ligacao

# Carregar variáveis de ambiente definidas no ficheiro .env
load_dotenv()

# Inicialização da aplicação Flask
app = Flask(__name__)

# Chave secreta usada para assinar cookies e proteger as sessões
app.secret_key = os.environ["SECRET_KEY"]

VALIDADE_TOKEN = 3600  # segundos
serializador = URLSafeTimedSerializer(app.secret_key, salt="recuperar-password")

# Categoria pré-definida usada apenas no registo do valor inicial das carteiras
CATEGORIA_SALDO_INICIAL = "Saldo Inicial"

# Funções dos membros de um grupo (têm de existir na tabela Funcoes)
FUNCAO_ADMINISTRADOR = "Administrador"
FUNCAO_MEMBRO = "Membro"

# Paleta de cores para as fatias do gráfico circular de despesas por categoria
CORES_GRAFICO = (
    "#0f7b5f",
    "#1971c2",
    "#e67700",
    "#6741d9",
    "#c2255c",
    "#0c8599",
    "#2b8a3e",
    "#d9480f",
    "#5c940d",
    "#862e9c",
)



def gerar_token(utilizador):
    """Cria o token de recuperação. Inclui parte do hash atual da palavra-passe,
    pelo que deixa de ser válido assim que a palavra-passe é alterada."""
    return serializador.dumps(
        {"id": utilizador["ID_Utilizador"], "hash": utilizador["Password"][-16:]}
    )


def obter_utilizador_do_token(token):
    """Devolve o utilizador a que o token pertence, ou None se for inválido ou tiver expirado."""
    try:
        dados = serializador.loads(token, max_age=VALIDADE_TOKEN)
    except BadSignature:
        return None

    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM Utilizadores WHERE ID_Utilizador = %s", (dados["id"],)
            )
            utilizador = cursor.fetchone()
    finally:
        ligacao.close()

    if utilizador and utilizador["Password"][-16:] == dados["hash"]:
        return utilizador
    return None


def obter_carteira_do_utilizador(cursor, id_carteira, id_utilizador):
    """Devolve a carteira se pertencer ao utilizador, ou None caso contrário.

    Usada em todas as rotas que recebem um ID de carteira, para impedir o
    acesso a carteiras de outros utilizadores.
    """
    cursor.execute(
        "SELECT * FROM Carteiras WHERE ID_Carteira = %s AND ID_Utilizador = %s",
        (id_carteira, id_utilizador),
    )
    return cursor.fetchone()


def converter_valor(texto):
    """Converte o texto de um formulário num Decimal com 2 casas decimais.

    Aceita vírgula ou ponto como separador. Devolve None se o valor for inválido.
    """
    try:
        valor = Decimal(texto.strip().replace(",", "."))
    except InvalidOperation:
        return None
    if not valor.is_finite():
        return None
    return valor.quantize(Decimal("0.01"))


def obter_categorias_do_utilizador(cursor, id_utilizador):
    """Devolve as categorias que o utilizador pode escolher: as pré-definidas e as suas.

    A categoria reservada ao valor inicial das carteiras não é incluída.
    """
    cursor.execute(
        "SELECT ID_Categoria, Categoria, ID_Utilizador FROM Categorias "
        "WHERE (ID_Utilizador IS NULL OR ID_Utilizador = %s) AND Categoria <> %s "
        "ORDER BY Categoria",
        (id_utilizador, CATEGORIA_SALDO_INICIAL),
    )
    return cursor.fetchall()


def obter_categoria_do_utilizador(cursor, id_categoria, id_utilizador):
    """Devolve a categoria se o utilizador a puder usar, ou None caso contrário.

    Impede a escolha de categorias de outros utilizadores ou da categoria reservada.
    """
    cursor.execute(
        "SELECT * FROM Categorias "
        "WHERE ID_Categoria = %s AND (ID_Utilizador IS NULL OR ID_Utilizador = %s) "
        "AND Categoria <> %s",
        (id_categoria, id_utilizador, CATEGORIA_SALDO_INICIAL),
    )
    return cursor.fetchone()

def obter_grupo_do_utilizador(cursor, id_grupo, id_utilizador):
    """Devolve o grupo, com a função do utilizador nele, se o utilizador for membro.

    Devolve None se o grupo não existir ou se o utilizador não pertencer a ele.
    """
    cursor.execute(
        "SELECT g.*, f.Funcao FROM Grupos g "
        "JOIN Membro_Grupo m ON m.ID_Grupo = g.ID_Grupo "
        "JOIN Funcoes f ON f.ID_Funcao = m.ID_Funcao "
        "WHERE g.ID_Grupo = %s AND m.ID_Utilizador = %s",
        (id_grupo, id_utilizador),
    )
    return cursor.fetchone()

def aplicar_transacoes_agendadas(cursor, id_utilizador):
    """Aplica ao saldo das carteiras do utilizador as transações agendadas cuja data já chegou."""
    cursor.execute(
        "SELECT t.ID_Transacao, t.Tipo, t.Valor, t.ID_Carteira FROM Transacoes t "
        "JOIN Carteiras c ON c.ID_Carteira = t.ID_Carteira "
        "WHERE c.ID_Utilizador = %s AND t.Aplicada = FALSE AND t.Data <= NOW() "
        "ORDER BY t.Data",
        (id_utilizador,),
    )
    for t in cursor.fetchall():
        # Marcar primeiro: se outro pedido já a aplicou, rowcount é 0 e não se aplica duas vezes
        cursor.execute(
            "UPDATE Transacoes SET Aplicada = TRUE WHERE ID_Transacao = %s AND Aplicada = FALSE",
            (t["ID_Transacao"],),
        )
        if cursor.rowcount == 0:
            continue
        variacao = t["Valor"] if t["Tipo"] == "receita" else -t["Valor"]
        cursor.execute(
            "UPDATE Carteiras SET Valor = Valor + %s WHERE ID_Carteira = %s",
            (variacao, t["ID_Carteira"]),
        )

# Expressão SQL: a transação t está ligada a uma despesa de grupo?
SQL_DE_GRUPO = (
    "(EXISTS (SELECT 1 FROM Transacoes_Grupo g WHERE g.ID_Transacao_Pessoal = t.ID_Transacao) "
    "OR EXISTS (SELECT 1 FROM Membros_Transacoes_Grupo p "
    "WHERE p.ID_Transacao_Pagamento = t.ID_Transacao OR p.ID_Transacao_Recebimento = t.ID_Transacao))"
)


def obter_transacao_do_utilizador(cursor, id_transacao, id_utilizador):
    """Devolve a transação se estiver numa carteira do utilizador, ou None caso contrário.

    FOR UPDATE bloqueia a linha até ao commit, para não ser alterada duas vezes ao mesmo tempo.
    """
    cursor.execute(
        "SELECT t.*, c.Categoria, " + SQL_DE_GRUPO + " AS De_Grupo FROM Transacoes t "
        "JOIN Carteiras w ON w.ID_Carteira = t.ID_Carteira "
        "LEFT JOIN Categorias c ON c.ID_Categoria = t.ID_Categoria "
        "WHERE t.ID_Transacao = %s AND w.ID_Utilizador = %s FOR UPDATE",
        (id_transacao, id_utilizador),
    )
    return cursor.fetchone()


def transacao_bloqueada(transacao):
    """Transações de grupo e o saldo inicial não podem ser editados nem eliminados."""
    return bool(transacao["De_Grupo"]) or transacao["Categoria"] == CATEGORIA_SALDO_INICIAL


def efeito_no_saldo(tipo, valor):
    """Quanto a transação soma ao saldo: positivo numa receita, negativo numa despesa."""
    return valor if tipo == "receita" else -valor



def dividir_em_partes(valor, numero_partes):
    """Divide um valor em partes iguais, arredondadas ao cêntimo.

    Os cêntimos que sobram da divisão são dados, um a um, às primeiras partes,
    para que a soma das partes seja sempre igual ao valor total.
    Ex.: 50,00 por 3 -> [16,67, 16,67, 16,66]
    """
    parte = (valor / numero_partes).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    cents_que_sobram = int((valor - parte * numero_partes) * 100)
    return [
        parte + Decimal("0.01") if indice < cents_que_sobram else parte
        for indice in range(numero_partes)
    ]


@app.route("/registo", methods=["GET", "POST"])
def registo():
    """Registo de novos utilizadores.

    Processa o formulário de registo (POST), garantindo a higienização dos dados,
    a encriptação segura da palavra-passe e a inserção na base de dados.
    Em caso de pedido GET, apresenta a página de formulário.
    """
    if request.method == "POST":
        # Extração e normalização dos dados submetidos pelo utilizador
        nome = request.form["nome"].strip()
        apelido = request.form["apelido"].strip()
        email = request.form["email"].strip().lower()

        password = request.form["password"]
        confirmacao = request.form["password_confirmacao"]

        if password != confirmacao:
            flash("As palavras-passe não coincidem.", "erro")
            return render_template("registo.html")
        # Criação de hash seguro para a palavra-passe (não armazena texto simples)
        password_hash = generate_password_hash(password)


        # Estabelecer ligação à base de dados para guardar o utilizador
        ligacao = obter_ligacao()
        try:
            with ligacao.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO Utilizadores (Nome, Apelido, Email, Password) "
                    "VALUES (%s, %s, %s, %s)",
                    (nome, apelido, email, password_hash),
                )
            # Confirmar a transação na base de dados
            ligacao.commit()
        except pymysql.err.IntegrityError:
            # Capturar violação de chave única (ex.: email duplicado)
            flash("Já existe uma conta com esse email.", "erro")
            return render_template("registo.html")
        finally:
            # Garantir o fecho da ligação, mesmo se ocorrer uma exceção
            ligacao.close()

        # Notificar o utilizador e redirecionar para a página de início de sessão
        flash("Conta criada. Já pode iniciar sessão.", "sucesso")
        return redirect(url_for("login"))

    # Apresentar o template de registo quando acedido via GET
    return render_template("registo.html")



@app.route("/login", methods=["GET", "POST"])
def login():
    """Autenticação de utilizadores.

    Verifica as credenciais fornecidas (POST). Em caso de sucesso, inicia
    a sessão do utilizador e redireciona para a área pessoal.
    """
    if request.method == "POST":
        # Normalização do email para comparação
        email = request.form["email"].strip().lower()

        # Consulta à base de dados para obter os dados do utilizador
        ligacao = obter_ligacao()
        try:
            with ligacao.cursor() as cursor:
                cursor.execute("SELECT * FROM Utilizadores WHERE Email = %s", (email,))
                utilizador = cursor.fetchone()
        finally:
            ligacao.close()

        # Validação da existência do utilizador e verificação do hash da palavra-passe
        if utilizador and check_password_hash(utilizador["Password"], request.form["password"]):
            # Guarda os dados essenciais na sessão do utilizador
            session["id_utilizador"] = utilizador["ID_Utilizador"]
            session["nome"] = utilizador["Nome"]
            return redirect(url_for("area_pessoal"))

        # Feedback caso o email ou a palavra-passe não correspondam
        flash("Email ou palavra-passe incorretos.", "erro")

    # Apresentar o formulário de login para pedidos GET ou falha de autenticação
    return render_template("login.html")

def mes_anterior(ano_mes):
    ano, mes = ano_mes
    return (ano - 1, 12) if mes == 1 else (ano, mes - 1)


def mes_seguinte(ano_mes):
    ano, mes = ano_mes
    return (ano + 1, 1) if mes == 12 else (ano, mes + 1)


def obter_filtro_meses(pedido, com_futuro=True):
    """Período a mostrar e os três botões do filtro de datas.

    pedido: valor de ?mes= no URL ("AAAA-MM", "futuro" ou vazio = mês atual).
    com_futuro: False para não mostrar o botão "Futuro" (ex.: página dos grupos).
    Devolve (inicio, fim, filtros). fim é None no "futuro" (sem limite).
    """
    hoje = date.today()
    atual = (hoje.year, hoje.month)
    passado = mes_anterior(atual)

    def opcao(ano_mes, ativo=False):
        if ano_mes == atual:
            texto = "Mês atual"
        elif ano_mes == passado:
            texto = "Mês passado"
        else:
            texto = f"{ano_mes[1]:02d}/{ano_mes[0]}"
        # O mês atual não leva ?mes= no URL, por ser o valor por omissão
        valor = None if ano_mes == atual else f"{ano_mes[0]}-{ano_mes[1]:02d}"
        return {"texto": texto, "mes": valor, "ativo": ativo}

    futuro = {"texto": "Futuro", "mes": "futuro", "ativo": com_futuro and pedido == "futuro"}

    if com_futuro and pedido == "futuro":
        # A partir de amanhã às 00:00, ou seja, tudo o que é depois de hoje
        inicio = hoje + timedelta(days=1)
        return inicio, None, {"esquerda": opcao(passado), "centro": opcao(atual), "direita": futuro}

    try:
        data_pedida = datetime.strptime(pedido, "%Y-%m")
        escolhido = (data_pedida.year, data_pedida.month)
    except ValueError:
        escolhido = atual          # sem ?mes= ou valor inválido
    if escolhido > atual:
        escolhido = atual          # meses futuros veem-se pelo botão "Futuro"

    inicio = date(*escolhido, 1)
    fim = date(*mes_seguinte(escolhido), 1)
    if escolhido == atual:
        fim = hoje + timedelta(days=1)
       # o resto do mês fica no "Futuro"
       # Sem "Futuro", o mês atual é o último botão (à direita)
    if not com_futuro and escolhido == atual:
        return inicio, fim, {"esquerda": opcao(mes_anterior(passado)), "centro": opcao(passado), "direita": opcao(atual, ativo=True)}


    direita = futuro if escolhido == atual else opcao(atual)
    return inicio, fim, {"esquerda": opcao(mes_anterior(escolhido)), "centro": opcao(escolhido, ativo=True), "direita": direita}



@app.route("/area_pessoal")
def area_pessoal():
    """Página principal do utilizador autenticado (Dashboard).

    Mostra as carteiras do utilizador e, da carteira selecionada (?carteira=ID,
    ou a primeira por omissão), o saldo e as transações por ordem cronológica.
    Protegida por controlo de acesso: sem sessão iniciada, redireciona para o login.
    """
    if "id_utilizador" not in session:
        return redirect(url_for("login"))

    id_utilizador = session["id_utilizador"]
    # Carteira pedida no URL; None se não vier ou não for um número
    id_carteira = request.args.get("carteira", type=int)
    inicio, fim, filtros = obter_filtro_meses(request.args.get("mes", ""))

    carteira = None
    transacoes = []

    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
            # Aplicar ao saldo as transações agendadas cuja data já chegou
            aplicar_transacoes_agendadas(cursor, id_utilizador)
            ligacao.commit()

            # Obter apenas as carteiras do utilizador da sessão
            cursor.execute(
                "SELECT ID_Carteira, Carteira, Valor FROM Carteiras "
                "WHERE ID_Utilizador = %s ORDER BY Carteira",
                (id_utilizador,),
            )
            carteiras = cursor.fetchall()

            # Categorias disponíveis para o formulário de nova transação
            categorias = obter_categorias_do_utilizador(cursor, id_utilizador)

            # Sem carteira indicada no URL, abrir a primeira
            if id_carteira is None and carteiras:
                id_carteira = carteiras[0]["ID_Carteira"]

            if id_carteira is not None:
                # Controlo de acesso: só o dono pode ver a carteira
                carteira = obter_carteira_do_utilizador(cursor, id_carteira, id_utilizador)
                if carteira is None:
                    abort(404)

                # Transações do período escolhido, da mais recente para a mais antiga
                sql = (
                    "SELECT t.*, c.Categoria, " + SQL_DE_GRUPO + " AS De_Grupo FROM Transacoes t "
                    "LEFT JOIN Categorias c ON c.ID_Categoria = t.ID_Categoria "
                    "WHERE t.ID_Carteira = %s AND t.Data >= %s "
                )
                parametros = [id_carteira, inicio]
                if fim is not None:
                    sql += "AND t.Data < %s "
                    parametros.append(fim)
                sql += "ORDER BY t.Data DESC, t.ID_Transacao DESC"
                cursor.execute(sql, parametros)
                transacoes = cursor.fetchall()
                for t in transacoes:
                    t["Bloqueada"] = transacao_bloqueada(t)


    finally:
        ligacao.close()

    return render_template(
        "area_pessoal.html",
        nome=session["nome"],
        carteiras=carteiras,
        carteira=carteira,
        transacoes=transacoes,
        categorias=categorias,
        filtros=filtros,
        hoje=date.today().isoformat(),
    )



@app.route("/carteira/criar", methods=["POST"])
def criar_carteira():
    """Criação de uma carteira com o valor inicial indicado pelo utilizador.

    O valor inicial fica também registado no histórico como "Saldo inicial".
    """
    if "id_utilizador" not in session:
        return redirect(url_for("login"))

    # Extração e validação dos dados do formulário
    nome_carteira = request.form["carteira"].strip()
    valor = converter_valor(request.form["valor"])

    if not nome_carteira:
        flash("Indique o nome da carteira.", "erro")
        return redirect(url_for("area_pessoal"))
    if valor is None or valor < 0:
        flash("O valor inicial tem de ser um número igual ou superior a 0.", "erro")
        return redirect(url_for("area_pessoal"))

    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
            # O dono da carteira vem sempre da sessão, nunca do formulário
            cursor.execute(
                "INSERT INTO Carteiras (Carteira, Valor, ID_Utilizador) VALUES (%s, %s, %s)",
                (nome_carteira, valor, session["id_utilizador"]),
            )
            # ID gerado pelo auto_increment para a carteira acabada de criar
            id_carteira = cursor.lastrowid

            # Registar o valor inicial no histórico, na categoria pré-definida "Saldo Inicial"
            if valor > 0:
                cursor.execute(
                    "SELECT ID_Categoria FROM Categorias "
                    "WHERE Categoria = %s AND ID_Utilizador IS NULL",
                    (CATEGORIA_SALDO_INICIAL,),
                )

                categoria = cursor.fetchone()
                cursor.execute(
                    "INSERT INTO Transacoes (Transacao, Tipo, Valor, ID_Carteira, ID_Categoria) "
                    "VALUES (%s, 'receita', %s, %s, %s)",
                    ("Saldo inicial", valor, id_carteira, categoria["ID_Categoria"]),
                )

        # Os dois INSERT só ficam gravados aqui (tudo ou nada)
        ligacao.commit()
    except pymysql.err.IntegrityError:
        # Violação de unique (ID_Utilizador, Carteira): este utilizador já tem esse nome
        ligacao.rollback()
        flash("Já tem uma carteira com esse nome.", "erro")
        return redirect(url_for("area_pessoal"))
    finally:
        ligacao.close()

    return redirect(url_for("area_pessoal", carteira=id_carteira))


@app.route("/carteira/<int:id_carteira>/transacoes/nova", methods=["POST"])
def nova_transacao(id_carteira):
    """Registo de uma receita ou despesa, atualizando o valor da carteira.

    O UPDATE da carteira e o INSERT da transação são confirmados em conjunto:
    se algum falhar, nenhum fica gravado.
    """
    if "id_utilizador" not in session:
        return redirect(url_for("login"))

    # Em qualquer caso, voltar ao dashboard com esta carteira aberta
    destino = url_for("area_pessoal", carteira=id_carteira)

    # Extração e validação dos dados do formulário
    descricao = request.form["transacao"].strip()
    tipo = request.form["tipo"]
    valor = converter_valor(request.form["valor"])
    id_categoria = request.form.get("categoria", type=int)
    data_texto = request.form.get("data", "")


    if not descricao:
        flash("Indique uma descrição.", "erro")
        return redirect(destino)
    if tipo not in ("receita", "despesa"):
        flash("Tipo de transação inválido.", "erro")
        return redirect(destino)
    if valor is None or valor <= 0:
        flash("O valor tem de ser superior a 0.", "erro")
        return redirect(destino)
    if id_categoria is None:
        flash("Escolha uma categoria.", "erro")
        return redirect(destino)
        
    try:
        data_escolhida = datetime.strptime(data_texto, "%Y-%m-%d").date()
    except ValueError:
        flash("Data inválida.", "erro")
        return redirect(destino)

    # Transação futura: fica agendada e só mexe no saldo quando chegar o dia.
    # A coluna Data é datetime: a futura fica às 00:00 desse dia, as outras com a hora atual.
    futura = data_escolhida > date.today()
    if futura:
        data_transacao = datetime.combine(data_escolhida, time())
    else:
        data_transacao = datetime.combine(data_escolhida, datetime.now().time())

    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
            # Controlo de acesso: só o dono pode alterar a carteira
            if obter_carteira_do_utilizador(cursor, id_carteira, session["id_utilizador"]) is None:
                abort(404)

            # Controlo de acesso: a categoria tem de ser pré-definida ou do próprio utilizador
            if obter_categoria_do_utilizador(cursor, id_categoria, session["id_utilizador"]) is None:
                flash("Escolha uma categoria válida.", "erro")
                return redirect(destino)

            # Atualização relativa do valor (a conta é feita pela base de dados).
            # Uma transação futura não mexe já no saldo: é aplicada por
            # aplicar_transacoes_agendadas quando chegar o dia.
            if not futura:
                if tipo == "receita":
                    cursor.execute(
                        "UPDATE Carteiras SET Valor = Valor + %s WHERE ID_Carteira = %s",
                        (valor, id_carteira),
                    )
                else:
                    # Só subtrai se houver saldo suficiente
                    cursor.execute(
                        "UPDATE Carteiras SET Valor = Valor - %s "
                        "WHERE ID_Carteira = %s AND Valor >= %s",
                        (valor, id_carteira, valor),
                    )
                    if cursor.rowcount == 0:
                        ligacao.rollback()
                        flash("Saldo insuficiente para esta despesa.", "erro")
                        return redirect(destino)

            # Registar a transação no histórico, com a data escolhida (agendada se for futura)
            cursor.execute(
                "INSERT INTO Transacoes (Transacao, Tipo, Valor, ID_Carteira, ID_Categoria, Data, Aplicada) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (descricao, tipo, valor, id_carteira, id_categoria, data_transacao, not futura),
            )

        ligacao.commit()
    except Exception:
        # Qualquer falha desfaz o UPDATE e o INSERT
        ligacao.rollback()
        raise
    finally:
        ligacao.close()

    if futura:
        flash("Transação agendada. O saldo só muda na data escolhida.", "sucesso")
    else:
        flash("Transação adicionada.", "sucesso")
    return redirect(destino)

@app.route("/transacao/<int:id_transacao>/eliminar", methods=["POST"])
def eliminar_transacao(id_transacao):
    """Eliminação de uma transação, devolvendo à carteira o efeito que teve no saldo."""
    if "id_utilizador" not in session:
        return redirect(url_for("login"))

    destino = url_for("area_pessoal")
    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
            # Controlo de acesso: só transações das carteiras do próprio utilizador
            transacao = obter_transacao_do_utilizador(cursor, id_transacao, session["id_utilizador"])
            if transacao is None:
                abort(404)
            destino = url_for("area_pessoal", carteira=transacao["ID_Carteira"])

            if transacao_bloqueada(transacao):
                flash("Esta transação faz parte de um grupo ou é o saldo inicial e não pode ser eliminada.", "erro")
                return redirect(destino)

            # Desfazer o efeito no saldo (só se já tinha sido aplicada; as agendadas ainda não mexeram)
            if transacao["Aplicada"]:
                variacao = -efeito_no_saldo(transacao["Tipo"], transacao["Valor"])
                cursor.execute(
                    "UPDATE Carteiras SET Valor = Valor + %s "
                    "WHERE ID_Carteira = %s AND Valor + %s >= 0",
                    (variacao, transacao["ID_Carteira"], variacao),
                )
                if cursor.rowcount == 0:
                    ligacao.rollback()
                    flash("Saldo insuficiente para eliminar esta receita.", "erro")
                    return redirect(destino)

            cursor.execute("DELETE FROM Transacoes WHERE ID_Transacao = %s", (id_transacao,))
        ligacao.commit()
    except Exception:
        ligacao.rollback()
        raise
    finally:
        ligacao.close()

    flash("Transação eliminada.", "sucesso")
    return redirect(destino)

@app.route("/transacao/<int:id_transacao>/editar", methods=["POST"])
def editar_transacao(id_transacao):
    """Edição de uma transação, acertando o saldo da carteira com a diferença.

    O tipo (receita/despesa) e a carteira não mudam.
    """
    if "id_utilizador" not in session:
        return redirect(url_for("login"))

    id_utilizador = session["id_utilizador"]
    descricao = request.form["transacao"].strip()
    valor = converter_valor(request.form["valor"])
    id_categoria = request.form.get("categoria", type=int)
    data_texto = request.form.get("data", "")

    destino = url_for("area_pessoal")
    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
            transacao = obter_transacao_do_utilizador(cursor, id_transacao, id_utilizador)
            if transacao is None:
                abort(404)
            destino = url_for("area_pessoal", carteira=transacao["ID_Carteira"])

            if transacao_bloqueada(transacao):
                flash("Esta transação faz parte de um grupo ou é o saldo inicial e não pode ser editada.", "erro")
                return redirect(destino)

            # Validação dos dados do formulário (as mesmas regras da criação)
            if not descricao:
                flash("Indique uma descrição.", "erro")
                return redirect(destino)
            if valor is None or valor <= 0:
                flash("O valor tem de ser superior a 0.", "erro")
                return redirect(destino)
            if id_categoria is None or obter_categoria_do_utilizador(cursor, id_categoria, id_utilizador) is None:
                flash("Escolha uma categoria válida.", "erro")
                return redirect(destino)
            try:
                data_escolhida = datetime.strptime(data_texto, "%Y-%m-%d").date()
            except ValueError:
                flash("Data inválida.", "erro")
                return redirect(destino)

            # Data: se o dia não mudou, mantém-se a hora original
            futura = data_escolhida > date.today()
            if data_escolhida == transacao["Data"].date():
                data_transacao = transacao["Data"]
            elif futura:
                data_transacao = datetime.combine(data_escolhida, time())
            else:
                data_transacao = datetime.combine(data_escolhida, datetime.now().time())

            # Diferença no saldo: tira-se o efeito antigo (se já tinha sido aplicado)
            # e põe-se o novo (se a nova data não for futura)
            efeito_antigo = efeito_no_saldo(transacao["Tipo"], transacao["Valor"]) if transacao["Aplicada"] else 0
            efeito_novo = 0 if futura else efeito_no_saldo(transacao["Tipo"], valor)
            variacao = efeito_novo - efeito_antigo

            if variacao != 0:
                cursor.execute(
                    "UPDATE Carteiras SET Valor = Valor + %s "
                    "WHERE ID_Carteira = %s AND Valor + %s >= 0",
                    (variacao, transacao["ID_Carteira"], variacao),
                )
                if cursor.rowcount == 0:
                    ligacao.rollback()
                    flash("Saldo insuficiente para esta alteração.", "erro")
                    return redirect(destino)

            cursor.execute(
                "UPDATE Transacoes SET Transacao = %s, Valor = %s, ID_Categoria = %s, "
                "Data = %s, Aplicada = %s WHERE ID_Transacao = %s",
                (descricao, valor, id_categoria, data_transacao, not futura, id_transacao),
            )
        ligacao.commit()
    except Exception:
        ligacao.rollback()
        raise
    finally:
        ligacao.close()

    flash("Transação atualizada.", "sucesso")
    return redirect(destino)


@app.route("/categoria/criar", methods=["POST"])
def criar_categoria():
    """Criação de uma categoria personalizada para o utilizador autenticado.

    Não permite repetir o nome de uma categoria pré-definida ou já criada pelo utilizador.
    """
    if "id_utilizador" not in session:
        return redirect(url_for("login"))

    nome_categoria = request.form["categoria"].strip()
    # Carteira aberta no dashboard, usada apenas para lá voltar
    id_carteira = request.form.get("carteira", type=int)
    destino = url_for("area_pessoal", carteira=id_carteira)

    if not nome_categoria:
        flash("Indique o nome da categoria.", "erro")
        return redirect(destino)

    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
            # Verificar se já existe com esse nome (pré-definida ou do utilizador)
            cursor.execute(
                "SELECT ID_Categoria FROM Categorias "
                "WHERE Categoria = %s AND (ID_Utilizador IS NULL OR ID_Utilizador = %s)",
                (nome_categoria, session["id_utilizador"]),
            )
            if cursor.fetchone():
                flash("Essa categoria já existe.", "erro")
                return redirect(destino)

            # O dono da categoria vem sempre da sessão, nunca do formulário
            cursor.execute(
                "INSERT INTO Categorias (Categoria, ID_Utilizador) VALUES (%s, %s)",
                (nome_categoria, session["id_utilizador"]),
            )
        ligacao.commit()
    except pymysql.err.IntegrityError:
        # Violação de unique (ID_Utilizador, Categoria)
        ligacao.rollback()
        flash("Essa categoria já existe.", "erro")
        return redirect(destino)
    finally:
        ligacao.close()

    flash("Categoria criada.", "sucesso")
    return redirect(destino)

@app.route("/grupos")
def grupos():
    """Página de grupos do utilizador autenticado.

    Mostra os grupos de que o utilizador é membro, os convites pendentes e,
    do grupo selecionado (?grupo=ID, ou o primeiro por omissão), os membros
    e as transações de grupo com a parte de cada membro.
    """
    if "id_utilizador" not in session:
        return redirect(url_for("login"))

    id_utilizador = session["id_utilizador"]
    id_grupo = request.args.get("grupo", type=int)
    inicio, fim, filtros = obter_filtro_meses(request.args.get("mes", ""), com_futuro=False)

    grupo = None
    membros = []
    transacoes_grupo = []

    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
            # Aplicar ao saldo as transações agendadas cuja data já chegou
            aplicar_transacoes_agendadas(cursor, id_utilizador)
            ligacao.commit()

            # Grupos de que o utilizador é membro, com a sua função em cada um
            cursor.execute(
                "SELECT g.ID_Grupo, g.Grupo, f.Funcao FROM Grupos g "
                "JOIN Membro_Grupo m ON m.ID_Grupo = g.ID_Grupo "
                "JOIN Funcoes f ON f.ID_Funcao = m.ID_Funcao "
                "WHERE m.ID_Utilizador = %s ORDER BY g.Grupo",
                (id_utilizador,),
            )
            lista_grupos = cursor.fetchall()

            # Convites pendentes dirigidos ao utilizador
            cursor.execute(
                "SELECT c.ID_Convite, g.Grupo, u.Nome, u.Apelido FROM Convites c "
                "JOIN Grupos g ON g.ID_Grupo = c.ID_Grupo "
                "JOIN Utilizadores u ON u.ID_Utilizador = c.ID_Convidou "
                "WHERE c.ID_Utilizador = %s ORDER BY c.Data DESC",
                (id_utilizador,),
            )
            convites = cursor.fetchall()

            # Carteiras e categorias do utilizador, para o formulário de nova transação de grupo
            cursor.execute(
                "SELECT ID_Carteira, Carteira, Valor FROM Carteiras "
                "WHERE ID_Utilizador = %s ORDER BY Carteira",
                (id_utilizador,),
            )
            carteiras = cursor.fetchall()
            categorias = obter_categorias_do_utilizador(cursor, id_utilizador)

            # Sem grupo indicado no URL, abrir o primeiro
            if id_grupo is None and lista_grupos:
                id_grupo = lista_grupos[0]["ID_Grupo"]

            if id_grupo is not None:
                # Controlo de acesso: só os membros podem ver o grupo
                grupo = obter_grupo_do_utilizador(cursor, id_grupo, id_utilizador)
                if grupo is None:
                    abort(404)

                # Membros do grupo, com o administrador primeiro
                cursor.execute(
                    "SELECT u.ID_Utilizador, u.Nome, u.Apelido, f.Funcao FROM Membro_Grupo m "
                    "JOIN Utilizadores u ON u.ID_Utilizador = m.ID_Utilizador "
                    "JOIN Funcoes f ON f.ID_Funcao = m.ID_Funcao "
                    "WHERE m.ID_Grupo = %s "
                    "ORDER BY f.Funcao = %s DESC, u.Nome, u.Apelido",
                    (id_grupo, FUNCAO_ADMINISTRADOR),
                )
                membros = cursor.fetchall()

                # Transações do grupo no período escolhido, da mais recente para a mais antiga
                sql = (
                    "SELECT t.ID_Transacao_Grupo, t.Transacao, t.Valor, t.Data, "
                    "c.Categoria, u.Nome, u.Apelido FROM Transacoes_Grupo t "
                    "JOIN Categorias c ON c.ID_Categoria = t.ID_Categoria "
                    "JOIN Utilizadores u ON u.ID_Utilizador = t.ID_Utilizador "
                    "WHERE t.ID_Grupo = %s AND t.Data >= %s "
                )
                parametros = [id_grupo, inicio]
                if fim is not None:
                    sql += "AND t.Data < %s "
                    parametros.append(fim)
                sql += "ORDER BY t.Data DESC, t.ID_Transacao_Grupo DESC"
                cursor.execute(sql, parametros)
                transacoes_grupo = cursor.fetchall()


                # Partes de todas as transações do grupo (uma só consulta)
                cursor.execute(
                    "SELECT p.ID_Transacao_Grupo, p.ID_Utilizador, p.Valor, p.Pago, "
                    "u.Nome, u.Apelido FROM Membros_Transacoes_Grupo p "
                    "JOIN Transacoes_Grupo t ON t.ID_Transacao_Grupo = p.ID_Transacao_Grupo "
                    "JOIN Utilizadores u ON u.ID_Utilizador = p.ID_Utilizador "
                    "WHERE t.ID_Grupo = %s ORDER BY u.Nome, u.Apelido",
                    (id_grupo,),
                )
                # Juntar a cada transação a lista das suas partes
                partes_por_transacao = {}
                for parte in cursor.fetchall():
                    partes_por_transacao.setdefault(parte["ID_Transacao_Grupo"], []).append(parte)
                for transacao in transacoes_grupo:
                    transacao["partes"] = partes_por_transacao.get(transacao["ID_Transacao_Grupo"], [])
    finally:
        ligacao.close()

    return render_template(
        "grupos.html",
        nome=session["nome"],
        id_utilizador=id_utilizador,
        grupos=lista_grupos,
        grupo=grupo,
        membros=membros,
        convites=convites,
        carteiras=carteiras,
        categorias=categorias,
        transacoes_grupo=transacoes_grupo,
        filtros=filtros,
        hoje=date.today().isoformat(),
        e_administrador=grupo is not None and grupo["Funcao"] == FUNCAO_ADMINISTRADOR,
    )

@app.route("/grupo/criar", methods=["POST"])
def criar_grupo():
    """Criação de um grupo. Quem o cria fica como administrador."""
    if "id_utilizador" not in session:
        return redirect(url_for("login"))

    nome_grupo = request.form["grupo"].strip()
    if not nome_grupo:
        flash("Indique o nome do grupo.", "erro")
        return redirect(url_for("grupos"))

    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
            cursor.execute("INSERT INTO Grupos (Grupo) VALUES (%s)", (nome_grupo,))
            id_grupo = cursor.lastrowid

            # O criador entra no grupo como administrador (dono vem da sessão)
            cursor.execute(
                "INSERT INTO Membro_Grupo (ID_Grupo, ID_Utilizador, ID_Funcao) "
                "SELECT %s, %s, ID_Funcao FROM Funcoes WHERE Funcao = %s",
                (id_grupo, session["id_utilizador"], FUNCAO_ADMINISTRADOR),
            )
            if cursor.rowcount == 0:
                raise RuntimeError("A função 'Administrador' não existe na tabela Funcoes.")
        # O grupo e o administrador só ficam gravados juntos
        ligacao.commit()
    except Exception:
        ligacao.rollback()
        raise
    finally:
        ligacao.close()

    flash("Grupo criado.", "sucesso")
    return redirect(url_for("grupos", grupo=id_grupo))

@app.route("/grupo/<int:id_grupo>/convidar", methods=["POST"])
def convidar_membro(id_grupo):
    """Convite de um utilizador (pelo email) para o grupo. Só o administrador pode convidar."""
    if "id_utilizador" not in session:
        return redirect(url_for("login"))

    destino = url_for("grupos", grupo=id_grupo)
    email = request.form["email"].strip().lower()
    # Mensagem igual quer a conta exista quer não, para não revelar emails registados
    mensagem_enviado = "Se existir uma conta com esse email, o convite foi enviado."

    if not email:
        flash("Indique o email da pessoa a convidar.", "erro")
        return redirect(destino)

    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
            # Controlo de acesso: tem de ser membro e administrador do grupo
            grupo = obter_grupo_do_utilizador(cursor, id_grupo, session["id_utilizador"])
            if grupo is None:
                abort(404)
            if grupo["Funcao"] != FUNCAO_ADMINISTRADOR:
                abort(403)

            cursor.execute(
                "SELECT ID_Utilizador, Nome FROM Utilizadores WHERE Email = %s", (email,)
            )

            convidado = cursor.fetchone()
            if convidado is None:
                flash(mensagem_enviado)
                return redirect(destino)

            # Já é membro? (inclui o próprio administrador)
            cursor.execute(
                "SELECT 1 FROM Membro_Grupo WHERE ID_Grupo = %s AND ID_Utilizador = %s",
                (id_grupo, convidado["ID_Utilizador"]),
            )
            if cursor.fetchone():
                flash("Essa pessoa já é membro do grupo.", "erro")
                return redirect(destino)

            cursor.execute(
                "INSERT INTO Convites (ID_Grupo, ID_Utilizador, ID_Convidou) VALUES (%s, %s, %s)",
                (id_grupo, convidado["ID_Utilizador"], session["id_utilizador"]),
            )
        ligacao.commit()
    except pymysql.err.IntegrityError:
        # Violação de unique (ID_Grupo, ID_Utilizador): já há um convite pendente
        ligacao.rollback()
        flash(mensagem_enviado)
        return redirect(destino)
    finally:
        ligacao.close()

        # Avisar o convidado por email (uma falha no envio não anula o convite)
    url_base = os.environ.get("URL_BASE", request.host_url).rstrip("/")
    ligacao_grupos = url_base + url_for("grupos")
    try:
        enviar_email(
            email,
            f"Convite para o grupo \"{grupo['Grupo']}\"",
            f"Olá {convidado['Nome']},\n\n"
            f"{session['nome']} convidou-o(a) para o grupo \"{grupo['Grupo']}\" "
            "no Finances4You.\n\n"
            "Para aceitar ou recusar o convite, inicie sessão e abra a página de grupos:\n\n"
            f"{ligacao_grupos}\n\n"
            "Se não conhece quem o convidou, pode simplesmente recusar o convite.\n",
        )
    except (OSError, KeyError):
        app.logger.exception("Falha ao enviar o email de convite.")


    flash(mensagem_enviado)
    return redirect(destino)

@app.route("/convite/<int:id_convite>/aceitar", methods=["POST"])
def aceitar_convite(id_convite):
    """Aceitação de um convite: o utilizador passa a membro do grupo."""
    if "id_utilizador" not in session:
        return redirect(url_for("login"))

    id_utilizador = session["id_utilizador"]
    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
            # Controlo de acesso: o convite tem de ser dirigido a este utilizador
            cursor.execute(
                "SELECT ID_Grupo FROM Convites WHERE ID_Convite = %s AND ID_Utilizador = %s",
                (id_convite, id_utilizador),
            )
            convite = cursor.fetchone()
            if convite is None:
                abort(404)

            cursor.execute(
                "INSERT INTO Membro_Grupo (ID_Grupo, ID_Utilizador, ID_Funcao) "
                "SELECT %s, %s, ID_Funcao FROM Funcoes WHERE Funcao = %s",
                (convite["ID_Grupo"], id_utilizador, FUNCAO_MEMBRO),
            )
            if cursor.rowcount == 0:
                raise RuntimeError("A função 'Membro' não existe na tabela Funcoes.")

            cursor.execute("DELETE FROM Convites WHERE ID_Convite = %s", (id_convite,))
        # Entrar no grupo e apagar o convite acontecem juntos
        ligacao.commit()
    except Exception:
        ligacao.rollback()
        raise
    finally:
        ligacao.close()

    flash("Entrou no grupo.", "sucesso")
    return redirect(url_for("grupos", grupo=convite["ID_Grupo"]))

@app.route("/convite/<int:id_convite>/recusar", methods=["POST"])
def recusar_convite(id_convite):
    """Recusa de um convite: o convite é apagado."""
    if "id_utilizador" not in session:
        return redirect(url_for("login"))

    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
            # O WHERE só apaga o convite se for dirigido a este utilizador
            cursor.execute(
                "DELETE FROM Convites WHERE ID_Convite = %s AND ID_Utilizador = %s",
                (id_convite, session["id_utilizador"]),
            )
            if cursor.rowcount == 0:
                abort(404)
        ligacao.commit()
    finally:
        ligacao.close()

    flash("Convite recusado.")
    return redirect(url_for("grupos"))

@app.route("/grupo/<int:id_grupo>/membros/<int:id_membro>/remover", methods=["POST"])
def remover_membro(id_grupo, id_membro):
    """Remoção de um membro do grupo. Só o administrador pode remover.

    Não deixa remover quem ainda tem contas por acertar no grupo.
    """
    if "id_utilizador" not in session:
        return redirect(url_for("login"))

    id_utilizador = session["id_utilizador"]
    destino = url_for("grupos", grupo=id_grupo)

    # O administrador não se pode remover a si próprio (o grupo ficaria sem administrador)
    if id_membro == id_utilizador:
        flash("Não pode remover-se a si próprio do grupo.", "erro")
        return redirect(destino)

    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
            # Controlo de acesso: tem de ser membro e administrador do grupo
            grupo = obter_grupo_do_utilizador(cursor, id_grupo, id_utilizador)
            if grupo is None:
                abort(404)
            if grupo["Funcao"] != FUNCAO_ADMINISTRADOR:
                abort(403)

            # Partes por pagar: que o membro deve, ou que lhe devem a ele
            cursor.execute(
                "SELECT 1 FROM Membros_Transacoes_Grupo p "
                "JOIN Transacoes_Grupo t ON t.ID_Transacao_Grupo = p.ID_Transacao_Grupo "
                "WHERE t.ID_Grupo = %s AND p.Pago = FALSE "
                "AND (p.ID_Utilizador = %s OR t.ID_Utilizador = %s) LIMIT 1",
                (id_grupo, id_membro, id_membro),
            )
            if cursor.fetchone():
                flash("Este membro ainda tem partes por pagar ou por receber no grupo.", "erro")
                return redirect(destino)

            cursor.execute(
                "DELETE FROM Membro_Grupo WHERE ID_Grupo = %s AND ID_Utilizador = %s",
                (id_grupo, id_membro),
            )
            if cursor.rowcount == 0:
                flash("Essa pessoa já não é membro do grupo.", "erro")
                return redirect(destino)
        ligacao.commit()
    except Exception:
        ligacao.rollback()
        raise
    finally:
        ligacao.close()

    flash("Membro removido do grupo.", "sucesso")
    return redirect(destino)

@app.route("/grupo/<int:id_grupo>/transacoes/nova", methods=["POST"])
def nova_transacao_grupo(id_grupo):
    """Registo de uma despesa de grupo, paga por quem a cria.

    O valor total sai da carteira escolhida por quem cria (despesa pessoal) e é
    dividido em partes iguais pelos membros selecionados. A parte de quem cria
    fica logo paga. Tudo é gravado em conjunto: se algo falhar, nada fica gravado.
    """
    if "id_utilizador" not in session:
        return redirect(url_for("login"))

    id_utilizador = session["id_utilizador"]
    destino = url_for("grupos", grupo=id_grupo)

    # Extração e validação dos dados do formulário
    descricao = request.form["transacao"].strip()
    valor = converter_valor(request.form["valor"])
    id_categoria = request.form.get("categoria", type=int)
    id_carteira = request.form.get("carteira", type=int)
    # Vários checkboxes com o mesmo name: getlist devolve todos os que foram marcados
    ids_membros = list(dict.fromkeys(request.form.getlist("membros", type=int)))
    data_texto = request.form.get("data", "")

    if not descricao:
        flash("Indique uma descrição.", "erro")
        return redirect(destino)
    if valor is None or valor <= 0:
        flash("O valor tem de ser superior a 0.", "erro")
        return redirect(destino)
    if id_categoria is None or id_carteira is None:
        flash("Escolha uma categoria e uma carteira.", "erro")
        return redirect(destino)
    if not ids_membros:
        flash("Selecione pelo menos um membro.", "erro")
        return redirect(destino)
    if valor < Decimal("0.01") * len(ids_membros):
        flash("O valor é demasiado pequeno para dividir por tantos membros.", "erro")
        return redirect(destino)
    try:
        data_escolhida = datetime.strptime(data_texto, "%Y-%m-%d").date()
    except ValueError:
        flash("Data inválida.", "erro")
        return redirect(destino)
    if data_escolhida > date.today():
        flash("A data não pode ser no futuro.", "erro")
        return redirect(destino)

    # A coluna Data é datetime: junta-se a hora atual ao dia escolhido
    data_transacao = datetime.combine(data_escolhida, datetime.now().time())


    # Quem paga fica em primeiro, para absorver os cêntimos que sobram da divisão
    if id_utilizador in ids_membros:
        ids_membros.remove(id_utilizador)
        ids_membros.insert(0, id_utilizador)

    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
            # Controlo de acesso: grupo, categoria e carteira
            if obter_grupo_do_utilizador(cursor, id_grupo, id_utilizador) is None:
                abort(404)
            if obter_categoria_do_utilizador(cursor, id_categoria, id_utilizador) is None:
                flash("Escolha uma categoria válida.", "erro")
                return redirect(destino)
            if obter_carteira_do_utilizador(cursor, id_carteira, id_utilizador) is None:
                flash("Escolha uma carteira válida.", "erro")
                return redirect(destino)

            # Os membros selecionados têm de pertencer a este grupo
            cursor.execute("SELECT ID_Utilizador FROM Membro_Grupo WHERE ID_Grupo = %s", (id_grupo,))
            membros_do_grupo = {linha["ID_Utilizador"] for linha in cursor.fetchall()}
            if not set(ids_membros) <= membros_do_grupo:
                flash("Selecione apenas membros deste grupo.", "erro")
                return redirect(destino)

            # 1. Despesa pessoal: o valor total sai da carteira de quem paga
            cursor.execute(
                "UPDATE Carteiras SET Valor = Valor - %s "
                "WHERE ID_Carteira = %s AND Valor >= %s",
                (valor, id_carteira, valor),
            )
            if cursor.rowcount == 0:
                ligacao.rollback()
                flash("Saldo insuficiente na carteira escolhida.", "erro")
                return redirect(destino)

            cursor.execute(
                "INSERT INTO Transacoes (Transacao, Tipo, Valor, ID_Carteira, ID_Categoria, Data) "
                "VALUES (%s, 'despesa', %s, %s, %s, %s)",
                (descricao, valor, id_carteira, id_categoria, data_transacao),
            )

            id_transacao_pessoal = cursor.lastrowid

            # 2. Transação de grupo, ligada à despesa pessoal
            cursor.execute(
                "INSERT INTO Transacoes_Grupo "
                "(Transacao, Valor, ID_Grupo, ID_Categoria, ID_Utilizador, ID_Transacao_Pessoal, Data) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (descricao, valor, id_grupo, id_categoria, id_utilizador, id_transacao_pessoal, data_transacao),
            )

            id_transacao_grupo = cursor.lastrowid

            # 3. Uma parte por membro; a de quem pagou fica logo paga
            partes = dividir_em_partes(valor, len(ids_membros))
            for id_membro, parte in zip(ids_membros, partes):
                pago = id_membro == id_utilizador
                cursor.execute(
                    "INSERT INTO Membros_Transacoes_Grupo "
                    "(ID_Transacao_Grupo, ID_Utilizador, Valor, Pago, Data_Pagamento) "
                    "VALUES (%s, %s, %s, %s, IF(%s, NOW(), NULL))",
                    (id_transacao_grupo, id_membro, parte, pago, pago),
                )
        ligacao.commit()
    except Exception:
        # Qualquer falha desfaz o UPDATE da carteira e todos os INSERT
        ligacao.rollback()
        raise
    finally:
        ligacao.close()

    flash("Transação de grupo criada.", "sucesso")
    return redirect(destino)

@app.route("/grupo/<int:id_grupo>/transacoes/<int:id_transacao_grupo>/pagar", methods=["POST"])
def pagar_parte(id_grupo, id_transacao_grupo):
    """Pagamento da parte do utilizador autenticado numa transação de grupo.

    O valor da parte sai da carteira escolhida pelo membro (despesa) e entra na
    carteira com que quem criou a transação pagou a conta (receita). Tudo é
    gravado em conjunto: se algo falhar, nada fica gravado.
    """
    if "id_utilizador" not in session:
        return redirect(url_for("login"))

    id_utilizador = session["id_utilizador"]
    destino = url_for("grupos", grupo=id_grupo)
    id_carteira = request.form.get("carteira", type=int)

    if id_carteira is None:
        flash("Escolha a carteira com que vai pagar.", "erro")
        return redirect(destino)

    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
            # Controlo de acesso: a carteira de onde sai o dinheiro tem de ser do próprio utilizador
            if obter_carteira_do_utilizador(cursor, id_carteira, id_utilizador) is None:
                flash("Escolha uma carteira válida.", "erro")
                return redirect(destino)

            # A parte por pagar deste utilizador e a carteira de quem pagou a conta.
            # FOR UPDATE bloqueia a linha até ao commit: a mesma parte não pode ser paga duas vezes.
            cursor.execute(
                "SELECT p.Valor, t.Transacao, t.ID_Categoria, tp.ID_Carteira AS ID_Carteira_Credor "
                "FROM Membros_Transacoes_Grupo p "
                "JOIN Transacoes_Grupo t ON t.ID_Transacao_Grupo = p.ID_Transacao_Grupo "
                "LEFT JOIN Transacoes tp ON tp.ID_Transacao = t.ID_Transacao_Pessoal "
                "WHERE p.ID_Transacao_Grupo = %s AND t.ID_Grupo = %s "
                "AND p.ID_Utilizador = %s AND p.Pago = FALSE "
                "FOR UPDATE",
                (id_transacao_grupo, id_grupo, id_utilizador),
            )
            parte = cursor.fetchone()
            if parte is None:
                abort(404)
            if parte["ID_Carteira_Credor"] is None:
                flash("Não foi possível identificar a carteira de quem pagou esta despesa.", "erro")
                return redirect(destino)

            valor = parte["Valor"]

            # 1. Despesa na carteira de quem paga a sua parte (só se houver saldo)
            cursor.execute(
                "UPDATE Carteiras SET Valor = Valor - %s "
                "WHERE ID_Carteira = %s AND Valor >= %s",
                (valor, id_carteira, valor),
            )
            if cursor.rowcount == 0:
                ligacao.rollback()
                flash("Saldo insuficiente na carteira escolhida.", "erro")
                return redirect(destino)

            cursor.execute(
                "INSERT INTO Transacoes (Transacao, Tipo, Valor, ID_Carteira, ID_Categoria) "
                "VALUES (%s, 'despesa', %s, %s, %s)",
                (f"A minha parte: {parte['Transacao']}"[:100], valor, id_carteira, parte["ID_Categoria"]),
            )
            id_transacao_pagamento = cursor.lastrowid

            # 2. Receita na carteira com que quem criou a transação pagou a conta
            cursor.execute(
                "UPDATE Carteiras SET Valor = Valor + %s WHERE ID_Carteira = %s",
                (valor, parte["ID_Carteira_Credor"]),
            )
            cursor.execute(
                "INSERT INTO Transacoes (Transacao, Tipo, Valor, ID_Carteira, ID_Categoria) "
                "VALUES (%s, 'receita', %s, %s, %s)",
                (
                    f"Reembolso de {session['nome']}: {parte['Transacao']}"[:100],
                    valor,
                    parte["ID_Carteira_Credor"],
                    parte["ID_Categoria"],
                ),
            )
            id_transacao_recebimento = cursor.lastrowid

            # 3. Marcar a parte como paga, ligada às duas transações pessoais
            cursor.execute(
                "UPDATE Membros_Transacoes_Grupo "
                "SET Pago = TRUE, Data_Pagamento = NOW(), "
                "ID_Transacao_Pagamento = %s, ID_Transacao_Recebimento = %s "
                "WHERE ID_Transacao_Grupo = %s AND ID_Utilizador = %s",
                (id_transacao_pagamento, id_transacao_recebimento, id_transacao_grupo, id_utilizador),
            )
        ligacao.commit()
    except Exception:
        # Qualquer falha desfaz os movimentos nas duas carteiras
        ligacao.rollback()
        raise
    finally:
        ligacao.close()

    flash("A sua parte foi paga.", "sucesso")
    return redirect(destino)

@app.route("/relatorios")
def relatorios():
    """Página de relatórios financeiros do utilizador autenticado.

    Apresenta o resumo do período escolhido (total de despesas, total de
    receitas e lucro/prejuízo) e um gráfico circular com a distribuição das
    despesas por categoria, para todas as carteiras ou para uma carteira
    específica (?carteira=ID), excluindo o saldo inicial.
    """
    if "id_utilizador" not in session:
        return redirect(url_for("login"))

    id_utilizador = session["id_utilizador"]
    id_carteira = request.args.get("carteira", type=int)
    inicio, fim, filtros = obter_filtro_meses(request.args.get("mes", ""))
    mes_ativo = "futuro" if filtros["direita"]["ativo"] else filtros["centro"]["mes"]

    carteira = None
    total_receitas = Decimal("0.00")
    total_despesas = Decimal("0.00")
    despesas_categorias = []

    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
            # Aplicar ao saldo as transações agendadas cuja data já chegou
            aplicar_transacoes_agendadas(cursor, id_utilizador)
            ligacao.commit()

            # Carteiras do utilizador para a barra lateral
            cursor.execute(
                "SELECT ID_Carteira, Carteira, Valor FROM Carteiras "
                "WHERE ID_Utilizador = %s ORDER BY Carteira",
                (id_utilizador,),
            )
            carteiras = cursor.fetchall()
            saldo_total = sum((c["Valor"] for c in carteiras), Decimal("0.00"))

            if id_carteira is not None:
                # Controlo de acesso: só o dono pode ver o relatório da carteira
                carteira = obter_carteira_do_utilizador(cursor, id_carteira, id_utilizador)
                if carteira is None:
                    abort(404)

            # Condições comuns às consultas do relatório (período, carteira e exclusão do saldo inicial)
            condicoes = (
                "WHERE w.ID_Utilizador = %s "
                "AND (c.Categoria IS NULL OR c.Categoria <> %s) "
                "AND t.Data >= %s "
            )
            parametros = [id_utilizador, CATEGORIA_SALDO_INICIAL, inicio]
            if fim is not None:
                condicoes += "AND t.Data < %s "
                parametros.append(fim)
            if id_carteira is not None:
                condicoes += "AND t.ID_Carteira = %s "
                parametros.append(id_carteira)

            # 1. Totais de receitas e despesas do período
            cursor.execute(
                "SELECT "
                "COALESCE(SUM(CASE WHEN t.Tipo = 'receita' THEN t.Valor ELSE 0 END), 0) AS Total_Receitas, "
                "COALESCE(SUM(CASE WHEN t.Tipo = 'despesa' THEN t.Valor ELSE 0 END), 0) AS Total_Despesas "
                "FROM Transacoes t "
                "JOIN Carteiras w ON w.ID_Carteira = t.ID_Carteira "
                "LEFT JOIN Categorias c ON c.ID_Categoria = t.ID_Categoria "
                + condicoes,
                parametros,
            )
            totais = cursor.fetchone()
            total_receitas = Decimal(totais["Total_Receitas"]).quantize(Decimal("0.01"))
            total_despesas = Decimal(totais["Total_Despesas"]).quantize(Decimal("0.01"))

            # 2. Despesas agrupadas por categoria para o gráfico circular
            cursor.execute(
                "SELECT COALESCE(c.Categoria, 'Sem categoria') AS Categoria, SUM(t.Valor) AS Total "
                "FROM Transacoes t "
                "JOIN Carteiras w ON w.ID_Carteira = t.ID_Carteira "
                "LEFT JOIN Categorias c ON c.ID_Categoria = t.ID_Categoria "
                + condicoes
                + "AND t.Tipo = 'despesa' "
                "GROUP BY c.ID_Categoria, c.Categoria "
                "ORDER BY Total DESC, Categoria",
                parametros,
            )
            linhas_categorias = cursor.fetchall()

            acumulado = 0.0
            for indice, linha in enumerate(linhas_categorias):
                valor_cat = Decimal(linha["Total"]).quantize(Decimal("0.01"))
                percentagem = (
                    (valor_cat * Decimal("100") / total_despesas).quantize(Decimal("0.1"))
                    if total_despesas > 0
                    else Decimal("0.0")
                )
                if indice == len(linhas_categorias) - 1:
                    fatia = max(0.0, round(100.0 - acumulado, 4))
                else:
                    fatia = min(
                        max(0.0, round(100.0 - acumulado, 4)),
                        round(float(valor_cat * Decimal("100") / total_despesas), 4),
                    )
                despesas_categorias.append(
                    {
                        "Categoria": linha["Categoria"],
                        "Total": valor_cat,
                        "Percentagem": percentagem,
                        "Fatia": fatia,
                        "Inicio": round(acumulado, 4),
                        "Cor": CORES_GRAFICO[indice % len(CORES_GRAFICO)],
                    }
                )
                acumulado += fatia
    finally:
        ligacao.close()

    resultado_liquido = total_receitas - total_despesas

    return render_template(
        "relatorios.html",
        nome=session["nome"],
        carteiras=carteiras,
        carteira=carteira,
        saldo_total=saldo_total,
        total_despesas=total_despesas,
        total_receitas=total_receitas,
        resultado_liquido=resultado_liquido,
        despesas_categorias=despesas_categorias,
        filtros=filtros,
        mes_ativo=mes_ativo,
    )


@app.route("/logout")
def logout():
    """Terminar a sessão do utilizador.

    Limpa todas as variáveis armazenadas na sessão e redireciona para o login.
    """
    session.clear()
    return redirect(url_for("login"))


@app.route("/index")
def index():
    """Página inicial pública da aplicação."""
    return render_template("index.html")


@app.route("/recuperar", methods=["GET", "POST"])
def recuperar():
    if request.method == "POST":
        email = request.form["email"].strip().lower()

        ligacao = obter_ligacao()
        try:
            with ligacao.cursor() as cursor:
                cursor.execute("SELECT * FROM Utilizadores WHERE Email = %s", (email,))
                utilizador = cursor.fetchone()
        finally:
            ligacao.close()

        if utilizador:
            url_base = os.environ.get("URL_BASE", request.host_url).rstrip("/")
            ligacao_repor = url_base + url_for("repor", token=gerar_token(utilizador))
            try:
                enviar_email(
                    email,
                    "Recuperação da palavra-passe",
                    f"Olá {utilizador['Nome']},\n\n"
                    "Para definir uma nova palavra-passe, abra a ligação seguinte "
                    "(válida durante 1 hora):\n\n"
                    f"{ligacao_repor}\n\n"
                    "Se não pediu a recuperação da conta, ignore este email.\n",
                )
            except (OSError, KeyError):
                app.logger.exception("Falha ao enviar o email de recuperação.")

        # A mesma mensagem quer a conta exista quer não, para não revelar emails registados.
        flash("Se existir uma conta com esse email, enviámos instruções para repor a palavra-passe.")
        return redirect(url_for("login"))

    return render_template("recuperar.html")


@app.route("/repor/<token>", methods=["GET", "POST"])
def repor(token):
    utilizador = obter_utilizador_do_token(token)
    if not utilizador:
        flash("A ligação de recuperação é inválida ou expirou.", "erro")
        return redirect(url_for("recuperar"))

    if request.method == "POST":
        password = request.form["password"]
        if password != request.form["confirmacao"]:
            flash("As palavras-passe não coincidem.", "erro")
            return render_template("repor.html")

        ligacao = obter_ligacao()
        try:
            with ligacao.cursor() as cursor:
                cursor.execute(
                    "UPDATE Utilizadores SET Password = %s WHERE ID_Utilizador = %s",
                    (generate_password_hash(password), utilizador["ID_Utilizador"]),
                )
            ligacao.commit()
        finally:
            ligacao.close()

        flash("Palavra-passe alterada. Já pode iniciar sessão.", "sucesso")
        return redirect(url_for("login"))

    return render_template("repor.html")

