import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "trocar-esta-chave")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///recibos.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

PORTAL_URL = "https://irs.portaldasfinancas.gov.pt/recibos/portal/consultar"

class User(UserMixin):
    id = "admin"

@login_manager.user_loader
def load_user(user_id):
    if user_id == "admin":
        return User()
    return None

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    nif = db.Column(db.String(20), unique=True, nullable=False)
    morada = db.Column(db.String(300), default="")
    link_recibo = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Recibo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=False)
    cliente = db.relationship("Cliente")
    descricao = db.Column(db.String(300), nullable=False)
    unidade = db.Column(db.String(50), default="mês")
    quantidade = db.Column(db.Numeric(10, 2), nullable=False)
    preco_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    iva = db.Column(db.Numeric(5, 2), default=0)
    motivo_iva = db.Column(db.String(200), default="Outras isenções")
    retencao = db.Column(db.Numeric(5, 2), default=0)
    desconto = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    resumo = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def admin_password_hash():
    raw = os.getenv("ADMIN_PASSWORD", "1234")
    return generate_password_hash(raw)

def money(value):
    return f"{Decimal(value):.2f} €".replace(".", ",")

@app.template_filter("money")
def money_filter(value):
    return money(value or 0)

def dec(value, default="0"):
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, TypeError):
        return Decimal(default)

def gerar_resumo(cliente, descricao, qtd, unidade, preco, iva, motivo, retencao, desconto, total):
    return f"""Cliente: {cliente.nome}
NIF: {cliente.nif}
Morada: {cliente.morada or '-'}

Serviço: {descricao}
Quantidade: {qtd} {unidade}
Preço unitário: {money(preco)}
Desconto: {money(desconto)}
IVA: {iva}% - {motivo}
Retenção IRS: {retencao}%

TOTAL A PAGAR: {money(total)}

Portal das Finanças:
{PORTAL_URL}
"""

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username", "")
        password = request.form.get("password", "")
        expected_user = os.getenv("ADMIN_USER", "mae")
        expected_password = os.getenv("ADMIN_PASSWORD", "1234")
        if user == expected_user and check_password_hash(generate_password_hash(expected_password), password):
            login_user(User())
            return redirect(url_for("index"))
        flash("Utilizador ou password incorretos.")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    clientes = Cliente.query.order_by(Cliente.nome.asc()).all()
    recibos = Recibo.query.order_by(Recibo.created_at.desc()).limit(8).all()
    return render_template("index.html", clientes=clientes, recibos=recibos, portal_url=PORTAL_URL)

@app.route("/clientes", methods=["GET", "POST"])
@login_required
def clientes():
    if request.method == "POST":
        nif = request.form.get("nif", "").strip()
        cliente = Cliente.query.filter_by(nif=nif).first() or Cliente(nif=nif)
        cliente.nome = request.form.get("nome", "").strip() or "Cliente sem nome"
        cliente.morada = request.form.get("morada", "").strip()
        cliente.link_recibo = request.form.get("link_recibo", "").strip()
        db.session.add(cliente)
        db.session.commit()
        flash("Cliente guardado.")
        return redirect(url_for("clientes"))
    return render_template("clientes.html", clientes=Cliente.query.order_by(Cliente.nome.asc()).all())

@app.route("/cliente/<int:cliente_id>/eliminar", methods=["POST"])
@login_required
def eliminar_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    Recibo.query.filter_by(cliente_id=cliente.id).delete()
    db.session.delete(cliente)
    db.session.commit()
    flash("Cliente eliminado.")
    return redirect(url_for("clientes"))

@app.route("/novo", methods=["GET", "POST"])
@login_required
def novo_recibo():
    clientes = Cliente.query.order_by(Cliente.nome.asc()).all()
    cliente_id = request.args.get("cliente_id") or request.form.get("cliente_id")
    cliente = Cliente.query.get(cliente_id) if cliente_id else None
    ultimo = Recibo.query.filter_by(cliente_id=cliente.id).order_by(Recibo.created_at.desc()).first() if cliente else None

    defaults = {
        "descricao": ultimo.descricao if ultimo else "LIMPEZAS",
        "unidade": ultimo.unidade if ultimo else "mês",
        "quantidade": ultimo.quantidade if ultimo else "1",
        "preco_unitario": ultimo.preco_unitario if ultimo else "12",
        "iva": ultimo.iva if ultimo else "0",
        "motivo_iva": ultimo.motivo_iva if ultimo else "Outras isenções",
        "retencao": ultimo.retencao if ultimo else "0",
        "desconto": ultimo.desconto if ultimo else "0",
    }

    if request.method == "POST":
        cliente = Cliente.query.get_or_404(request.form.get("cliente_id"))
        descricao = request.form.get("descricao", "LIMPEZAS").strip()
        unidade = request.form.get("unidade", "mês").strip()
        qtd = dec(request.form.get("quantidade"), "1")
        preco = dec(request.form.get("preco_unitario"), "0")
        iva = dec(request.form.get("iva"), "0")
        motivo = request.form.get("motivo_iva", "Outras isenções").strip()
        retencao = dec(request.form.get("retencao"), "0")
        desconto = dec(request.form.get("desconto"), "0")
        base = (qtd * preco) - desconto
        total_iva = base * iva / Decimal("100")
        total_retencao = base * retencao / Decimal("100")
        total = base + total_iva - total_retencao
        resumo = gerar_resumo(cliente, descricao, qtd, unidade, preco, iva, motivo, retencao, desconto, total)
        recibo = Recibo(cliente=cliente, descricao=descricao, unidade=unidade, quantidade=qtd,
                        preco_unitario=preco, iva=iva, motivo_iva=motivo, retencao=retencao,
                        desconto=desconto, total=total, resumo=resumo)
        db.session.add(recibo)
        db.session.commit()
        return redirect(url_for("ver_recibo", recibo_id=recibo.id))

    return render_template("novo.html", clientes=clientes, cliente=cliente, ultimo=ultimo, defaults=defaults)

@app.route("/recibo/<int:recibo_id>")
@login_required
def ver_recibo(recibo_id):
    recibo = Recibo.query.get_or_404(recibo_id)
    return render_template("recibo.html", recibo=recibo, portal_url=PORTAL_URL)

@app.route("/recibo/<int:recibo_id>/pdf")
@login_required
def recibo_pdf(recibo_id):
    recibo = Recibo.query.get_or_404(recibo_id)
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 2*cm
    p.setFont("Helvetica-Bold", 16)
    p.drawString(2*cm, y, "Resumo para Recibo")
    y -= 1*cm
    p.setFont("Helvetica", 11)
    for line in recibo.resumo.splitlines():
        if y < 2*cm:
            p.showPage(); y = height - 2*cm; p.setFont("Helvetica", 11)
        p.drawString(2*cm, y, line[:95])
        y -= 0.55*cm
    p.showPage()
    p.save()
    buffer.seek(0)
    filename = f"resumo_recibo_{recibo.cliente.nif}_{recibo.id}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")

@app.route("/historico")
@login_required
def historico():
    recibos = Recibo.query.order_by(Recibo.created_at.desc()).all()
    return render_template("historico.html", recibos=recibos)

@app.route("/recibo/<int:recibo_id>/eliminar", methods=["POST"])
@login_required
def eliminar_recibo(recibo_id):
    recibo = Recibo.query.get_or_404(recibo_id)
    db.session.delete(recibo)
    db.session.commit()
    flash("Resumo eliminado.")
    return redirect(url_for("historico"))

@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    print("Base de dados criada.")

with app.app_context():
    db.create_all()

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)