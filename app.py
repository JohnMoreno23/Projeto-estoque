from flask import Flask, render_template, request, redirect, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
import csv
from io import StringIO

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///estoque.db'
# Desativa o aviso sobre o rastreamento de modificações
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Definindo o modelo Notebook


class Notebook(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    modelo = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    estado = db.Column(db.String(50), nullable=False)
    numero_serie = db.Column(db.String(100), nullable=True)
    colaborador = db.Column(db.String(100), nullable=True)
    motivo_entrada = db.Column(db.String(255), nullable=True)
    setor = db.Column(db.String(100), nullable=True) 
    data = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class OutrosEquipamentos(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    estado = db.Column(db.String(50), nullable=False)
    data = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)



@app.route('/estoque')
def estoque_view():
    notebooks = Notebook.query.all()  # Consulta os notebooks
    outros_itens = OutrosEquipamentos.query.all()  # Consulta outros equipamentos
    return render_template('estoque.html', itens=notebooks, outros_itens=outros_itens)


@app.route("/cadastro", methods=["POST"])
def cadastro_notebook():
    modelo = request.form["modelo"]
    quantidade = int(request.form["quantidade"])
    data = request.form["data"]

    item = Notebook.query.filter_by(modelo=modelo, estado="novo").first()
    if item:
        item.quantidade += quantidade
    else:
        novo_item = Notebook(modelo=modelo, quantidade=quantidade,
                             estado="novo", data=datetime.strptime(data, "%Y-%m-%d"))
        db.session.add(novo_item)
    db.session.commit()

    return redirect(url_for("estoque_view"))


@app.route("/entrada", methods=["POST"])
def entrada_notebook():
    modelo = request.form["modelo"]
    quantidade = int(request.form["quantidade"])
    estado = request.form["estado"]  # Verifica o estado (novo ou usado)
    numero_serie = request.form["numero_serie"]
    colaborador = request.form["colaborador"]
    motivo_entrada = request.form["motivo_entrada"]
    data = request.form["data"]

    # Alteração: Verifica se o notebook é novo ou usado
    item = Notebook.query.filter_by(modelo=modelo, estado=estado).first()

    if item:
        item.quantidade += quantidade
    else:
        novo_item = Notebook(modelo=modelo, quantidade=quantidade, estado=estado,
                             numero_serie=numero_serie, colaborador=colaborador,
                             motivo_entrada=motivo_entrada, data=datetime.strptime(data, "%Y-%m-%d"))
        db.session.add(novo_item)

    db.session.commit()
    return redirect(url_for("estoque_view"))


@app.route("/saida", methods=["POST"])
def saida_notebook():
    modelo = request.form["modelo"]
    quantidade = int(request.form["quantidade"])
    estado = request.form["estado"]
    numero_serie = request.form["numero_serie"]
    colaborador = request.form["colaborador"]
    motivo_saida = request.form["motivo_saida"]
    setor = request.form["setor"] 
    data = request.form["data"]

    item = Notebook.query.filter_by(modelo=modelo, estado=estado).first()

    if item:
        if item.quantidade >= quantidade:
            item.quantidade -= quantidade
            item.numero_serie = numero_serie
            item.colaborador = colaborador
            item.motivo_entrada = motivo_saida  # Este campo será usado para o motivo de saída
            item.setor = setor  # Registrar o setor
            item.data = datetime.strptime(data, "%Y-%m-%d")
        else:
            erro = f"Quantidade insuficiente no estoque para o modelo {modelo} ({
                estado})."
            itens = Notebook.query.all()
            return render_template("estoque.html", itens=itens, erro=erro)
    else:
        erro = f"Modelo {
            modelo} ({estado}) não encontrado no estoque. Verifique o cadastro."
        itens = Notebook.query.all()
        return render_template("estoque.html", itens=itens, erro=erro)

    db.session.commit()
    return redirect(url_for("estoque_view"))


@app.route('/relatorio', methods=["GET", "POST"])
def gerar_relatorio_csv():
    if request.method == "POST":
        data_inicio = request.form.get("data_inicio")
        data_fim = request.form.get("data_fim")

        # Convertendo as datas para objetos datetime
        data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d") if data_inicio else datetime.min
        data_fim = datetime.strptime(data_fim, "%Y-%m-%d") if data_fim else datetime.max

        # Consultar dados de Notebooks
        entradas_notebooks = Notebook.query.filter(Notebook.motivo_entrada != None, Notebook.data.between(data_inicio, data_fim)).all()
        saidas_notebooks = Notebook.query.filter(Notebook.motivo_entrada == None, Notebook.data.between(data_inicio, data_fim)).all()

        # Consultar dados de Outros Equipamentos
        entradas_outros = OutrosEquipamentos.query.filter(OutrosEquipamentos.quantidade > 0, OutrosEquipamentos.data.between(data_inicio, data_fim)).all()
        saidas_outros = []  # Registrar saídas se você criar logs específicos

        # Gerando os dados para o CSV
        dados_relatorio = [
            ["Categoria", "Modelo/Nome", "Estado", "Colaborador", "Número de Série", "Tipo de Movimentação", "Setor", "Motivo", "Data"]
        ]

        # Adicionando entradas de Notebooks
        for item in entradas_notebooks:
            dados_relatorio.append([
                "Notebook", item.modelo, item.estado, item.colaborador, item.numero_serie,
                "Entrada", item.setor, item.motivo_entrada, item.data.strftime('%d/%m/%Y')
            ])

        # Adicionando saídas de Notebooks
        for item in saidas_notebooks:
            dados_relatorio.append([
                "Notebook", item.modelo, item.estado, item.colaborador, item.numero_serie,
                "Saída", item.setor, item.motivo_entrada, item.data.strftime('%d/%m/%Y')
            ])

        # Adicionando entradas de Outros Equipamentos
        for item in entradas_outros:
            dados_relatorio.append([
                "Outros Equipamentos", item.nome, item.estado, "-", "-",  # Sem colaborador ou número de série padrão
                "Entrada", "-", "-", item.data.strftime('%d/%m/%Y')
            ])

        # Adicionando saídas de Outros Equipamentos (se necessário)
        for item in saidas_outros:
            dados_relatorio.append([
                "Outros Equipamentos", item.nome, item.estado, "-", "-",  # Sem colaborador ou número de série padrão
                "Saída", "-", "-", item.data.strftime('%d/%m/%Y')
            ])

        # Criando um objeto StringIO para gerar o CSV
        output = StringIO()
        writer = csv.writer(output)

        # Escrevendo os dados no arquivo CSV
        writer.writerows(dados_relatorio)

        # Movendo o ponteiro para o início do arquivo
        output.seek(0)

        # Retornando o CSV para download
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=relatorio_movimentacao.csv"}
        )
    return render_template("relatorio.html")

@app.route("/cadastro_outros", methods=["POST"])
def cadastro_outros():
    nome = request.form["nome"]
    quantidade = int(request.form["quantidade"])
    estado = request.form["estado"]
    data = request.form["data"]

    item = OutrosEquipamentos.query.filter_by(nome=nome, estado=estado).first()
    if item:
        item.quantidade += quantidade
    else:
        novo_item = OutrosEquipamentos(nome=nome, quantidade=quantidade,
                                       estado=estado, data=datetime.strptime(data, "%Y-%m-%d"))
        db.session.add(novo_item)

    db.session.commit()
    return redirect(url_for("estoque_view"))

@app.route("/saida_outros", methods=["POST"])
def saida_outros():
    nome = request.form["nome"]
    quantidade = int(request.form["quantidade"])
    estado = request.form["estado"]
    numero_serie = request.form["numero_serie"]
    colaborador = request.form["colaborador"]
    motivo_saida = request.form["motivo_saida"]
    setor = request.form["setor"]
    data = request.form["data"]

    item = OutrosEquipamentos.query.filter_by(nome=nome, estado=estado).first()

    if item:
        if item.quantidade >= quantidade:
            item.quantidade -= quantidade
            # Você pode registrar as informações adicionais em um log ou outro sistema, se necessário
        else:
            erro = f"Quantidade insuficiente no estoque para o item {nome} ({estado})."
            outros_itens = OutrosEquipamentos.query.all()
            notebooks = Notebook.query.all()
            return render_template("estoque.html", itens=notebooks, outros_itens=outros_itens, erro=erro)
    else:
        erro = f"Item {nome} ({estado}) não encontrado no estoque. Verifique o cadastro."
        outros_itens = OutrosEquipamentos.query.all()
        notebooks = Notebook.query.all()
        return render_template("estoque.html", itens=notebooks, outros_itens=outros_itens, erro=erro)

    db.session.commit()
    return redirect(url_for("estoque_view"))



if __name__ == "__main__":
    app.run(debug=True)
