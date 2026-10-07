"""Aplicação Web de Gestão de Finanças Pessoais.

Este módulo define o servidor Flask principal, configurando as rotas para
autenticação (registo e login), navegação e gestão de sessão de utilizadores.
"""

import os
import pymysql
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

# Módulo local com a função de ligação à base de dados MariaDB
from db import obter_ligacao

# Carregar variáveis de ambiente definidas no ficheiro .env
load_dotenv()

# Inicialização da aplicação Flask
app = Flask(__name__)

# Chave secreta usada para assinar cookies e proteger as sessões
app.secret_key = os.environ["SECRET_KEY"]



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

        # Criação de hash seguro para a palavra-passe (não armazena texto simples)
        password_hash = generate_password_hash(request.form["password"])

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
            flash("Já existe uma conta com esse email.")
            return render_template("registo.html")
        finally:
            # Garantir o fecho da ligação, mesmo se ocorrer uma exceção
            ligacao.close()

        # Notificar o utilizador e redirecionar para a página de início de sessão
        flash("Conta criada. Já pode iniciar sessão.")
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
        flash("Email ou palavra-passe incorretos.")

    # Apresentar o formulário de login para pedidos GET ou falha de autenticação
    return render_template("login.html")



@app.route("/area_pessoal")
def area_pessoal():
    """Página principal do utilizador autenticado (Dashboard).

    Protegida por controlo de acesso: se o utilizador não tiver sessão iniciada,
    é redirecionado para a página de login.
    """
    if "id_utilizador" not in session:
        return redirect(url_for("login"))

    return render_template("area_pessoal.html", nome=session["nome"])


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

