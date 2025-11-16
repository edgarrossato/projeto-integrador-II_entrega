from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


db = SQLAlchemy()

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    senha = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)

class Cupcake(db.Model):
    __tablename__ = 'cupcakes'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    preco = db.Column(db.Float, nullable=False)
    imagem_url = db.Column(db.String(255), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

class Pedido(db.Model):
    __tablename__ = 'pedidos'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    finalizado = db.Column(db.Boolean, default=False)
    usuario = db.relationship('Usuario', backref=db.backref('pedidos', lazy=True))
    status = db.Column(db.String(30), default="Recebido")
    data_pedido = db.Column(db.DateTime, default=datetime.utcnow) 
    avaliacao = db.Column(db.Integer, nullable=True)  # ★ Avaliação 1–5


class PedidoCupcake(db.Model):
    __tablename__ = 'pedido_cupcake'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    cupcake_id = db.Column(db.Integer, db.ForeignKey('cupcakes.id'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)

    pedido = db.relationship('Pedido', backref=db.backref('itens', lazy=True))
    cupcake = db.relationship('Cupcake')

class PedidoStatusLog(db.Model):
    __tablename__ = "pedido_status_log"

    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey("pedidos.id"), nullable=False)
    status = db.Column(db.String(30), nullable=False)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)

    pedido = db.relationship("Pedido", backref=db.backref("status_log", order_by="PedidoStatusLog.data_hora"))