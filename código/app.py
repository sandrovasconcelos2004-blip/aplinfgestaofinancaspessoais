"""Aplicação Web de Gestão de Finanças Pessoais.

Este módulo define o servidor Flask principal, configurando as rotas para
autenticação (registo e login), navegação, gestão de sessão de utilizadores
e gestão de carteiras e transações.
"""


import os
from decimal import Decimal, InvalidOperation
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
    carteira = None
    transacoes = []

    ligacao = obter_ligacao()
    try:
        with ligacao.cursor() as cursor:
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

                # Transações da mais recente para a mais antiga, com o nome da categoria
                cursor.execute(
                    "SELECT t.*, c.Categoria FROM Transacoes t "
                    "LEFT JOIN Categorias c ON c.ID_Categoria = t.ID_Categoria "
                    "WHERE t.ID_Carteira = %s "
                    "ORDER BY t.Data DESC, t.ID_Transacao DESC",
                    (id_carteira,),
                )
                transacoes = cursor.fetchall()
    finally:
        ligacao.close()

    return render_template(
        "area_pessoal.html",
        nome=session["nome"],
        carteiras=carteiras,
        carteira=carteira,
        transacoes=transacoes,
        categorias=categorias,
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

            # Atualização relativa do valor: a conta é feita pela base de dados
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

            # Registar a transação no histórico (a Data é preenchida automaticamente)
            cursor.execute(
                "INSERT INTO Transacoes (Transacao, Tipo, Valor, ID_Carteira, ID_Categoria) "
                "VALUES (%s, %s, %s, %s, %s)",
                (descricao, tipo, valor, id_carteira, id_categoria),
            )
        ligacao.commit()
    except Exception:
        # Qualquer falha desfaz o UPDATE e o INSERT
        ligacao.rollback()
        raise
    finally:
        ligacao.close()

    flash("Transação adicionada.", "sucesso")
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

