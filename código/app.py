import os
import pymysql
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import obter_ligacao

load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]


@app.route("/registo", methods=["GET", "POST"])
def registo():
    if request.method == "POST":
        nome = request.form["nome"].strip()
        apelido = request.form["apelido"].strip()
        email = request.form["email"].strip().lower()
        password_hash = generate_password_hash(request.form["password"])

        ligacao = obter_ligacao()
        try:
            with ligacao.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO Utilizadores (Nome, Apelido, Email, Password) "
                    "VALUES (%s, %s, %s, %s)",
                    (nome, apelido, email, password_hash),
                )
            ligacao.commit()
        except pymysql.err.IntegrityError:
            flash("Já existe uma conta com esse email.")
            return render_template("registo.html")
        finally:
            ligacao.close()

        flash("Conta criada. Já pode iniciar sessão.")
        return redirect(url_for("login"))

    return render_template("registo.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()

        ligacao = obter_ligacao()
        try:
            with ligacao.cursor() as cursor:
                cursor.execute("SELECT * FROM Utilizadores WHERE Email = %s", (email,))
                utilizador = cursor.fetchone()
        finally:
            ligacao.close()

        if utilizador and check_password_hash(utilizador["Password"], request.form["password"]):
            session["id_utilizador"] = utilizador["ID_Utilizador"]
            session["nome"] = utilizador["Nome"]
            return redirect(url_for("area_pessoal"))

        flash("Email ou palavra-passe incorretos.")

    return render_template("login.html")


@app.route("/area_pessoal")
def area_pessoal():
    if "id_utilizador" not in session:
        return redirect(url_for("login"))
    return render_template("area_pessoal.html", nome=session["nome"])


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/index")
def index():
    return render_template("index.html")
