from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import date

app = Flask(__name__)
app.secret_key = "chave-do-sistema-acoes-solidarias"

DATABASE = "banco.db"


# ==========================================================
# BANCO DE DADOS
# ==========================================================

def conectar():
    conexao = sqlite3.connect(DATABASE)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


def criar_banco():

    conexao = conectar()

    # Beneficiários
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS beneficiarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            tipo TEXT NOT NULL,
            bairro TEXT,
            data_cadastro TEXT NOT NULL,
            situacao TEXT NOT NULL DEFAULT 'Ativo'
        )
    """)

    # Necessidades
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS necessidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            beneficiario_id INTEGER NOT NULL,
            categoria TEXT NOT NULL,
            item TEXT NOT NULL,
            quantidade REAL NOT NULL,
            prioridade TEXT NOT NULL,
            situacao TEXT NOT NULL DEFAULT 'Pendente',
            data_cadastro TEXT NOT NULL,
            FOREIGN KEY (beneficiario_id)
                REFERENCES beneficiarios(id)
                ON DELETE CASCADE
        )
    """)

    # Doações
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS doacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doador TEXT NOT NULL,
            data TEXT NOT NULL,
            observacao TEXT
        )
    """)

    # Itens das doações
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS itens_doacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doacao_id INTEGER NOT NULL,
            item TEXT NOT NULL,
            categoria TEXT NOT NULL,
            quantidade REAL NOT NULL,
            quantidade_disponivel REAL NOT NULL,
            FOREIGN KEY (doacao_id)
                REFERENCES doacoes(id)
                ON DELETE CASCADE
        )
    """)

    # Ações solidárias
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS acoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            data TEXT NOT NULL,
            descricao TEXT,
            situacao TEXT NOT NULL DEFAULT 'Planejada'
        )
    """)

    # Atendimentos
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS atendimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            necessidade_id INTEGER NOT NULL,
            acao_id INTEGER NOT NULL,
            quantidade_atendida REAL NOT NULL,
            data TEXT NOT NULL,
            observacao TEXT,
            FOREIGN KEY (necessidade_id)
                REFERENCES necessidades(id)
                ON DELETE CASCADE,
            FOREIGN KEY (acao_id)
                REFERENCES acoes(id)
                ON DELETE CASCADE
        )
    """)

    conexao.commit()
    conexao.close()


# ==========================================================
# FUNÇÕES AUXILIARES
# ==========================================================

def obter_quantidade_atendida(necessidade_id):

    conexao = conectar()

    resultado = conexao.execute("""
        SELECT COALESCE(SUM(quantidade_atendida), 0) AS total
        FROM atendimentos
        WHERE necessidade_id = ?
    """, (necessidade_id,)).fetchone()

    conexao.close()

    return resultado["total"]


def atualizar_situacao_necessidade(necessidade_id):

    conexao = conectar()

    necessidade = conexao.execute("""
        SELECT quantidade
        FROM necessidades
        WHERE id = ?
    """, (necessidade_id,)).fetchone()

    if not necessidade:
        conexao.close()
        return

    atendida = conexao.execute("""
        SELECT COALESCE(SUM(quantidade_atendida), 0) AS total
        FROM atendimentos
        WHERE necessidade_id = ?
    """, (necessidade_id,)).fetchone()["total"]

    quantidade = necessidade["quantidade"]

    if atendida <= 0:
        situacao = "Pendente"

    elif atendida < quantidade:
        situacao = "Parcialmente atendida"

    else:
        situacao = "Atendida"

    conexao.execute("""
        UPDATE necessidades
        SET situacao = ?
        WHERE id = ?
    """, (situacao, necessidade_id))

    conexao.commit()
    conexao.close()


# ==========================================================
# DASHBOARD
# ==========================================================

@app.route("/")
def dashboard():

    conexao = conectar()

    beneficiarios = conexao.execute("""
        SELECT COUNT(*) AS total
        FROM beneficiarios
    """).fetchone()["total"]

    necessidades = conexao.execute("""
        SELECT COUNT(*) AS total
        FROM necessidades
    """).fetchone()["total"]

    pendentes = conexao.execute("""
        SELECT COUNT(*) AS total
        FROM necessidades
        WHERE situacao = 'Pendente'
    """).fetchone()["total"]

    parciais = conexao.execute("""
        SELECT COUNT(*) AS total
        FROM necessidades
        WHERE situacao = 'Parcialmente atendida'
    """).fetchone()["total"]

    atendidas = conexao.execute("""
        SELECT COUNT(*) AS total
        FROM necessidades
        WHERE situacao = 'Atendida'
    """).fetchone()["total"]

    doacoes = conexao.execute("""
        SELECT COUNT(*) AS total
        FROM doacoes
    """).fetchone()["total"]

    acoes = conexao.execute("""
        SELECT COUNT(*) AS total
        FROM acoes
    """).fetchone()["total"]

    conexao.close()

    return render_template(
        "dashboard.html",
        beneficiarios=beneficiarios,
        necessidades=necessidades,
        pendentes=pendentes,
        parciais=parciais,
        atendidas=atendidas,
        doacoes=doacoes,
        acoes=acoes
    )


# ==========================================================
# BENEFICIÁRIOS
# ==========================================================

@app.route("/beneficiarios")
def beneficiarios():

    conexao = conectar()

    lista = conexao.execute("""
        SELECT *
        FROM beneficiarios
        ORDER BY id DESC
    """).fetchall()

    conexao.close()

    return render_template(
        "beneficiarios.html",
        beneficiarios=lista
    )


@app.route("/beneficiarios/novo", methods=["GET", "POST"])
def novo_beneficiario():

    if request.method == "POST":

        codigo = request.form["codigo"].strip()
        tipo = request.form["tipo"]
        bairro = request.form["bairro"].strip()

        try:

            conexao = conectar()

            conexao.execute("""
                INSERT INTO beneficiarios
                (codigo, tipo, bairro, data_cadastro)
                VALUES (?, ?, ?, ?)
            """, (
                codigo,
                tipo,
                bairro,
                date.today().isoformat()
            ))

            conexao.commit()
            conexao.close()

            flash("Beneficiário cadastrado com sucesso.", "success")

            return redirect(url_for("beneficiarios"))

        except sqlite3.IntegrityError:

            flash("O código informado já está cadastrado.", "danger")

    return render_template("beneficiario_form.html")


# ==========================================================
# NECESSIDADES
# ==========================================================

@app.route("/necessidades")
def necessidades():

    conexao = conectar()

    lista = conexao.execute("""
        SELECT
            necessidades.*,
            beneficiarios.codigo
        FROM necessidades
        INNER JOIN beneficiarios
            ON necessidades.beneficiario_id = beneficiarios.id
        ORDER BY necessidades.id DESC
    """).fetchall()

    resultado = []

    for necessidade in lista:

        atendida = conexao.execute("""
            SELECT COALESCE(SUM(quantidade_atendida), 0) AS total
            FROM atendimentos
            WHERE necessidade_id = ?
        """, (necessidade["id"],)).fetchone()["total"]

        restante = max(
            necessidade["quantidade"] - atendida,
            0
        )

        resultado.append({
            "id": necessidade["id"],
            "codigo": necessidade["codigo"],
            "categoria": necessidade["categoria"],
            "item": necessidade["item"],
            "quantidade": necessidade["quantidade"],
            "atendida": atendida,
            "restante": restante,
            "prioridade": necessidade["prioridade"],
            "situacao": necessidade["situacao"]
        })

    conexao.close()

    return render_template(
        "necessidades.html",
        necessidades=resultado
    )


@app.route("/necessidades/nova", methods=["GET", "POST"])
def nova_necessidade():

    conexao = conectar()

    beneficiarios = conexao.execute("""
        SELECT *
        FROM beneficiarios
        WHERE situacao = 'Ativo'
        ORDER BY codigo
    """).fetchall()

    if request.method == "POST":

        beneficiario_id = request.form["beneficiario_id"]
        categoria = request.form["categoria"]
        item = request.form["item"].strip()
        quantidade = float(request.form["quantidade"])
        prioridade = request.form["prioridade"]

        conexao.execute("""
            INSERT INTO necessidades
            (
                beneficiario_id,
                categoria,
                item,
                quantidade,
                prioridade,
                data_cadastro
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            beneficiario_id,
            categoria,
            item,
            quantidade,
            prioridade,
            date.today().isoformat()
        ))

        conexao.commit()
        conexao.close()

        flash("Necessidade cadastrada com sucesso.", "success")

        return redirect(url_for("necessidades"))

    conexao.close()

    return render_template(
        "necessidade_form.html",
        beneficiarios=beneficiarios
    )


# ==========================================================
# DOAÇÕES
# ==========================================================

@app.route("/doacoes")
def doacoes():

    conexao = conectar()

    lista = conexao.execute("""
        SELECT
            doacoes.id,
            doacoes.doador,
            doacoes.data,
            doacoes.observacao,
            COALESCE(SUM(itens_doacao.quantidade), 0) AS total_itens
        FROM doacoes
        LEFT JOIN itens_doacao
            ON doacoes.id = itens_doacao.doacao_id
        GROUP BY doacoes.id
        ORDER BY doacoes.id DESC
    """).fetchall()

    conexao.close()

    return render_template(
        "doacoes.html",
        doacoes=lista
    )


@app.route("/doacoes/nova", methods=["GET", "POST"])
def nova_doacao():

    if request.method == "POST":

        doador = request.form["doador"].strip()
        observacao = request.form["observacao"].strip()

        itens = request.form.getlist("item[]")
        categorias = request.form.getlist("categoria[]")
        quantidades = request.form.getlist("quantidade[]")

        if not itens:
            flash("Informe pelo menos um item.", "danger")
            return render_template("doacao_form.html")

        conexao = conectar()

        cursor = conexao.execute("""
            INSERT INTO doacoes
            (doador, data, observacao)
            VALUES (?, ?, ?)
        """, (
            doador,
            date.today().isoformat(),
            observacao
        ))

        doacao_id = cursor.lastrowid

        for item, categoria, quantidade in zip(
            itens,
            categorias,
            quantidades
        ):

            if item.strip() and float(quantidade) > 0:

                conexao.execute("""
                    INSERT INTO itens_doacao
                    (
                        doacao_id,
                        item,
                        categoria,
                        quantidade,
                        quantidade_disponivel
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    doacao_id,
                    item.strip(),
                    categoria,
                    float(quantidade),
                    float(quantidade)
                ))

        conexao.commit()
        conexao.close()

        flash("Doação registrada com sucesso.", "success")

        return redirect(url_for("doacoes"))

    return render_template("doacao_form.html")


# ==========================================================
# AÇÕES SOLIDÁRIAS
# ==========================================================

@app.route("/acoes")
def acoes():

    conexao = conectar()

    lista = conexao.execute("""
        SELECT *
        FROM acoes
        ORDER BY data DESC
    """).fetchall()

    conexao.close()

    return render_template(
        "acoes.html",
        acoes=lista
    )


@app.route("/acoes/nova", methods=["GET", "POST"])
def nova_acao():

    if request.method == "POST":

        nome = request.form["nome"].strip()
        data_acao = request.form["data"]
        descricao = request.form["descricao"].strip()

        conexao = conectar()

        conexao.execute("""
            INSERT INTO acoes
            (nome, data, descricao)
            VALUES (?, ?, ?)
        """, (
            nome,
            data_acao,
            descricao
        ))

        conexao.commit()
        conexao.close()

        flash("Ação solidária cadastrada.", "success")

        return redirect(url_for("acoes"))

    return render_template("acao_form.html")


# ==========================================================
# ATENDIMENTO
# ==========================================================

@app.route("/atendimentos/novo", methods=["GET", "POST"])
def novo_atendimento():

    conexao = conectar()

    necessidades = conexao.execute("""
        SELECT
            necessidades.*,
            beneficiarios.codigo
        FROM necessidades
        INNER JOIN beneficiarios
            ON necessidades.beneficiario_id = beneficiarios.id
        WHERE necessidades.situacao != 'Atendida'
        ORDER BY necessidades.prioridade DESC
    """).fetchall()

    acoes = conexao.execute("""
        SELECT *
        FROM acoes
        WHERE situacao != 'Finalizada'
        ORDER BY data DESC
    """).fetchall()

    if request.method == "POST":

        necessidade_id = int(
            request.form["necessidade_id"]
        )

        acao_id = int(
            request.form["acao_id"]
        )

        quantidade = float(
            request.form["quantidade"]
        )

        observacao = request.form["observacao"].strip()

        necessidade = conexao.execute("""
            SELECT quantidade
            FROM necessidades
            WHERE id = ?
        """, (necessidade_id,)).fetchone()

        ja_atendido = conexao.execute("""
            SELECT COALESCE(SUM(quantidade_atendida), 0) AS total
            FROM atendimentos
            WHERE necessidade_id = ?
        """, (necessidade_id,)).fetchone()["total"]

        restante = necessidade["quantidade"] - ja_atendido

        if quantidade <= 0:

            flash(
                "A quantidade deve ser maior que zero.",
                "danger"
            )

        elif quantidade > restante:

            flash(
                f"A quantidade máxima disponível é {restante}.",
                "danger"
            )

        else:

            conexao.execute("""
                INSERT INTO atendimentos
                (
                    necessidade_id,
                    acao_id,
                    quantidade_atendida,
                    data,
                    observacao
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                necessidade_id,
                acao_id,
                quantidade,
                date.today().isoformat(),
                observacao
            ))

            conexao.commit()
            conexao.close()

            atualizar_situacao_necessidade(
                necessidade_id
            )

            flash(
                "Atendimento registrado com sucesso.",
                "success"
            )

            return redirect(
                url_for("necessidades")
            )

    conexao.close()

    return render_template(
        "atendimento_form.html",
        necessidades=necessidades,
        acoes=acoes
    )


# ==========================================================
# EXECUÇÃO
# ==========================================================

if __name__ == "__main__":

    criar_banco()

    app.run(
        debug=True
    )
