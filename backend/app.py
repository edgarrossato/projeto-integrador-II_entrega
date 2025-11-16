from flask import Flask, current_app, render_template, Response, send_file, request, redirect, session, url_for, flash, jsonify, abort, make_response

from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
from fpdf import FPDF
from sqlalchemy import func
from math import ceil
from io import BytesIO
import pandas as pd
import os
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename
import re
from flask import Response


from backend.config import Config
from backend.models import db, Usuario, Cupcake, Pedido, PedidoCupcake, PedidoStatusLog


app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static"
)


@app.context_processor
def inject_current_year():
    return {"current_year": datetime.now().year}


# =================== Funções auxiliares ===================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario_id" not in session:
            flash("Você precisa estar logado.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# ============================= Admin required =============================
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        is_admin = session.get("is_admin")

        # Aceita boolean True e string "true"
        if not is_admin or str(is_admin).lower() != "true":
            flash("Acesso restrito a administradores.", "danger")
            return redirect(url_for("vitrine"))

        return f(*args, **kwargs)
    return decorated_function

def init_cart():
    """Garante que o carrinho exista como dicionário {str(cupcake_id): quantidade}"""
    if "carrinho" not in session or not isinstance(session["carrinho"], dict):
        session["carrinho"] = {}

# Configurações
app.config.from_object(Config)
app.secret_key = 'chave_secreta'  # ⚠ Trocar por variável de AMBIENTE!
db.init_app(app)


# =================== Rotas públicas ===================

@app.route("/")
def index():
    return redirect(url_for("vitrine"))

@app.route("/vitrine")
def vitrine():
    # Só cupcakes ativos na vitrine
    cupcakes = Cupcake.query.filter_by(ativo=True).all()
    return render_template("vitrine.html", cupcakes=cupcakes)


#rota login=================


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]

        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and check_password_hash(usuario.senha, senha):

            # ✅ Dados salvos na sessão
            session["usuario_id"] = usuario.id
            session["usuario_nome"] = usuario.nome
            session["usuario_email"] = usuario.email
            session["is_admin"] = usuario.is_admin  

            init_cart()
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("home"))

        flash("Email ou senha inválidos", "danger")

    return render_template("login.html")


#rota cadastro=================

@app.route("/cadastro")
def cadastro():
    return render_template("cadastro.html")


@app.route("/cadastrar", methods=["POST"])
def cadastrar():
    nome = request.form["nome"]
    email = request.form["email"]
    senha = request.form["senha"]
    telefone = request.form.get("telefone")

    # ------- VALIDAÇÃO DO TELEFONE -------
    padrao_tel = r"^\(\d{2}\)\s?\d{4,5}-\d{4}$"
    if not re.match(padrao_tel, telefone or ""):
        flash("Telefone inválido! Use o formato (11) 98765-4321", "danger")
        return redirect(url_for("cadastro"))
    # -------------------------------------

    # verifica duplicidade de email
    if Usuario.query.filter_by(email=email).first():
        flash("Email já cadastrado!", "danger")
        return redirect(url_for("cadastro"))

    novo = Usuario(
        nome=nome,
        email=email,
        senha=generate_password_hash(senha),
        telefone=telefone
    )

    db.session.add(novo)
    db.session.commit()

    flash("Cadastro realizado com sucesso!", "success")
    return redirect(url_for("login"))



@app.route("/logout")
def logout():
    session.clear()
    flash("Logout realizado com sucesso.", "info")
    return redirect(url_for("vitrine"))


# =================== Área do usuário ===================

@app.route("/home")
@login_required
def home():
    return render_template("home.html", nome=session["usuario_nome"])

# =================== CARRINHO (session) ===================

@app.route('/adicionar_ao_carrinho/<int:cupcake_id>', methods=["POST"])
def adicionar_ao_carrinho(cupcake_id):
    """
    Espera um campo 'quantidade' no form (opcional, default 1).
    Mantém o carrinho como dict: { "1": 2, "3": 1 }
    """
    quantidade = int(request.form.get("quantidade", 1))
    if quantidade < 1:
        quantidade = 1

    init_cart()
    carrinho = session["carrinho"]  

    key = str(cupcake_id)
    carrinho[key] = carrinho.get(key, 0) + quantidade

    session["carrinho"] = carrinho
    flash(f"{quantidade} unidade(s) adicionada(s) ao carrinho!", "success")
    return redirect(url_for("vitrine"))

@app.route('/aumentar_quantidade/<int:cupcake_id>', methods=["POST"])
def aumentar_quantidade(cupcake_id):
    init_cart()
    key = str(cupcake_id)
    carrinho = session["carrinho"]
    carrinho[key] = carrinho.get(key, 0) + 1
    session["carrinho"] = carrinho
    flash("Quantidade aumentada.", "info")
    return redirect(url_for("carrinho"))

@app.route('/diminuir_quantidade/<int:cupcake_id>', methods=["POST"])
def diminuir_quantidade(cupcake_id):
    init_cart()
    key = str(cupcake_id)
    carrinho = session["carrinho"]

    if key in carrinho:
        if carrinho[key] > 1:
            carrinho[key] -= 1
            flash("Quantidade reduzida.", "info")
        else:
            # se for 1, removemos o item completamente
            del carrinho[key]
            flash("Item removido do carrinho.", "warning")
        session['carrinho'] = carrinho
    else:
        flash("Item não encontrado no carrinho.", "warning")

    return redirect(url_for('carrinho'))

#route para remover item do carrinho

@app.route("/remover_do_carrinho/<int:cupcake_id>", methods=["POST"])
@login_required 
def remover_do_carrinho(cupcake_id):
    init_cart()
    key = str(cupcake_id)
    if key in session["carrinho"]:
        del session["carrinho"][key]
        flash("Item removido do carrinho.", "warning")
        session.modified = True
    return redirect(url_for("carrinho"))


@app.route("/carrinho")
def carrinho():
    init_cart()
    carrinho = session.get("carrinho", {})

    ids = [int(k) for k in carrinho.keys()] if carrinho else []
    cupcakes = Cupcake.query.filter(Cupcake.id.in_(ids)).all() if ids else []

    carrinho_itens = []
    total = 0.0
    mapa = {c.id: c for c in cupcakes}

    for key, qty in carrinho.items():
        cid = int(key)
        c = mapa.get(cid)
        if c:
            subtotal = float(c.preco) * int(qty)
            total += subtotal
            carrinho_itens.append({
                "cupcake": c,
                "quantidade": int(qty),
                "subtotal": subtotal
            })

    return render_template("carrinho.html", itens=carrinho_itens, total=total)


@app.route("/api/carrinho")
def api_carrinho():
    init_cart()
    carrinho = session.get("carrinho", {})
    ids = [int(k) for k in carrinho.keys()] if carrinho else []
    cupcakes = Cupcake.query.filter(Cupcake.id.in_(ids)).all() if ids else []

    result = []
    mapa = {c.id: c for c in cupcakes}

    for key, qty in carrinho.items():
        cid = int(key)
        c = mapa.get(cid)
        if c:
            result.append({
                "id": c.id,
                "nome": c.nome,
                "preco": float(c.preco),
                "imagem_url": c.imagem_url,
                "quantidade": int(qty)
            })
    return jsonify(result)


# =================== PEDIDOS (salvo no banco) ===================

@app.route("/finalizar_pedido", methods=["POST"])
@login_required
def finalizar_pedido():
    carrinho = session.get("carrinho", {})
    if not carrinho:
        flash("Carrinho vazio!", "warning")
        return redirect(url_for("carrinho"))

    # 1) Criar pedido
    pedido = Pedido(
        usuario_id=session["usuario_id"],
        finalizado=True,
        status="Recebido"
    )
    db.session.add(pedido)
    db.session.commit()

    total = 0

    # 2) Salvar itens
    for cupcake_id, qtd in carrinho.items():
        cid = int(cupcake_id)
        quantidade = int(qtd)

        item = PedidoCupcake(
            pedido_id=pedido.id,
            cupcake_id=cid,
            quantidade=quantidade
        )
        db.session.add(item)

        cupcake = Cupcake.query.get(cid)
        total += cupcake.preco * quantidade

    db.session.commit()

    # 3) Registrar log
    log = PedidoStatusLog(pedido_id=pedido.id, status="Recebido")
    db.session.add(log)
    db.session.commit()

    # 4) Limpar carrinho
    session["carrinho"] = {}

    # ==========================
    # 5) WHATSAPP AUTOMÁTICO
    # ==========================
    mensagem = f"Olá! Gostaria de confirmar meu pedido nº {pedido.id}:%0A%0A"

    itens = PedidoCupcake.query.filter_by(pedido_id=pedido.id).all()
    for item in itens:
        cupcake = Cupcake.query.get(item.cupcake_id)
        mensagem += f"- {cupcake.nome} (x{item.quantidade}): R$ {cupcake.preco * item.quantidade:.2f}%0A"

    mensagem += f"%0A*Total:* R$ {total:.2f}%0A"
    mensagem += "%0APor favor, me envie o endereço de entrega e a forma de pagamento."

    telefone = "5511948083862"  # coloque o número da loja
    whatsapp_url = f"https://wa.me/{telefone}?text={mensagem}"

    # salvar para ser aberto automaticamente no pedido.html
    session["whatsapp_url"] = whatsapp_url

    flash("Pedido realizado com sucesso! 🧁", "success")
    return redirect(url_for("pedido"))


# inicio rota pedido    -------------------

@app.route("/pedido")
@login_required
def pedido():
    user_id = session["usuario_id"]

    # 1) HISTÓRICO DE PEDIDOS FINALIZADOS
    pedidos = Pedido.query.filter_by(usuario_id=user_id, finalizado=True) \
        .order_by(Pedido.data_pedido.desc()).all()

    historico = []
    for p in pedidos:
        itens = []
        total = 0

        for item in p.itens:
            subtotal = item.quantidade * item.cupcake.preco
            itens.append({
                "cupcake": item.cupcake,
                "quantidade": item.quantidade,
                "subtotal": subtotal
            })
            total += subtotal

        historico.append({
            "pedido_id": p.id,
            "data": p.data_pedido,
            "status": p.status,
            "itens": itens,
            "total": total,
            "avaliacao": p.avaliacao
        })


    # 2) PEDIDO EM ABERTO (finalizado=False)

    pedido_aberto = Pedido.query.filter_by(usuario_id=user_id, finalizado=False).first()

    pedido_itens = []
    total = 0

    if pedido_aberto:
        for item in pedido_aberto.itens:
            subtotal = item.quantidade * item.cupcake.preco
            pedido_itens.append({
                "cupcake": item.cupcake,
                "quantidade": item.quantidade,
                "subtotal": subtotal
            })
            total += subtotal

    
    # 3) RENDERIZAÇÃO FINAL
  
    return render_template(
        "pedido.html",
        historico=historico,
        pedido_itens=pedido_itens,
        total=total
    )



#rota finalizar pedido

@app.route("/checkout/finalizar", methods=["POST"])
@login_required
def checkout_finalizar():

    if "carrinho" not in session or not session["carrinho"]:
        flash("Seu carrinho está vazio!", "warning")
        return redirect(url_for("carrinho"))

    carrinho = session["carrinho"]

    # criar pedido
    pedido = Pedido(
        usuario_id=session["usuario_id"],
        finalizado=False
    )
    db.session.add(pedido)
    db.session.commit()

    # adicionar itens do carrinho
    for item in carrinho:
        item_pedido = PedidoCupcake(
            pedido_id=pedido.id,
            cupcake_id=item["id"],
            quantidade=item["quantidade"]
        )
        db.session.add(item_pedido)

    pedido.finalizado = True
    db.session.commit()

    # limpar carrinho
    session.pop("carrinho", None)

    flash("Pedido realizado com sucesso! 🎉", "success")
    return redirect(url_for("checkout_sucesso", pedido_id=pedido.id))

#rota sucesso checkout

@app.route("/checkout/sucesso/<int:pedido_id>")
@login_required
def checkout_sucesso(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)

    # calcular total dinamicamente
    total = sum(item.quantidade * item.cupcake.preco for item in pedido.itens)

    return render_template("checkout_sucesso.html", pedido=pedido, total=total)


#rota remover pedido

@app.route("/remover_pedido/<int:pedido_id>")
@login_required
@admin_required  # <- só admin pode usar
def remover_pedido(pedido_id):
    pedido = Pedido.query.filter_by(id=pedido_id, usuario_id=session["usuario_id"]).first()

    if not pedido:
        flash("Pedido não encontrado.", "danger")
        return redirect(url_for("pedido"))

    # Remove também os itens ligados ao pedido
    for item in pedido.itens:
        db.session.delete(item)

    db.session.delete(pedido)
    db.session.commit()

    flash("Pedido removido com sucesso!", "info")
    return redirect(url_for("pedido"))

#rota repetir pedido    

@app.route("/repetir_pedido/<int:pedido_id>")
@login_required
def repetir_pedido(pedido_id):

    pedido = Pedido.query.filter_by(id=pedido_id, usuario_id=session["usuario_id"]).first()

    if not pedido:
        flash("Pedido não encontrado.", "danger")
        return redirect(url_for("pedido"))

    init_cart()

    for item in pedido.itens:
        cid = str(item.cupcake_id)
        if cid in session["carrinho"]:
            session["carrinho"][cid] += item.quantidade
        else:
            session["carrinho"][cid] = item.quantidade

    session.modified = True
    flash("Itens adicionados ao carrinho novamente!", "success")
    return redirect(url_for("pedido"))



# rota gerar PDF do pedido

@app.route("/pedido/pdf/<int:pedido_id>")
@login_required
def pedido_pdf(pedido_id):

    # Se for admin, pode buscar qualquer pedido
    if session.get("is_admin"):
        pedido = Pedido.query.get(pedido_id)
    else:
        # Se for cliente comum, só pode acessar o dele
        pedido = Pedido.query.filter_by(id=pedido_id, usuario_id=session.get("usuario_id")).first()

    if not pedido:
        flash("Pedido não encontrado.", "danger")
        # Admin volta pro painel, cliente volta pra tela de pedidos dele
        return redirect(url_for("admin_dashboard") if session.get("is_admin") else url_for("pedido"))

    # === GERAR PDF ===
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Pedido #{pedido.id}", ln=True, align="C")
    pdf.ln(4)

    pdf.set_font("Arial", size=12)
    pdf.cell(0, 6, f"Cliente: {pedido.usuario.nome}", ln=True)
    pdf.cell(0, 6, f"E-mail: {pedido.usuario.email}", ln=True)
    pdf.cell(0, 6, f"Data: {pedido.data_pedido.strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.cell(0, 6, f"Status: {pedido.status}", ln=True)
    pdf.ln(6)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(80, 8, "Item", 1)
    pdf.cell(25, 8, "Qtd", 1, align="C")
    pdf.cell(40, 8, "Unitário", 1, align="C")
    pdf.cell(40, 8, "Subtotal", 1, align="C", ln=True)

    pdf.set_font("Arial", size=11)
    total = 0

    for item in pedido.itens:
        subtotal = item.quantidade * item.cupcake.preco
        total += subtotal

        pdf.cell(80, 8, item.cupcake.nome, 1)
        pdf.cell(25, 8, str(item.quantidade), 1, align="C")
        pdf.cell(40, 8, f"R$ {item.cupcake.preco:.2f}", 1, align="C")
        pdf.cell(40, 8, f"R$ {subtotal:.2f}", 1, align="C", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, f"Total: R$ {total:.2f}", ln=True, align="R")

    pdf_bytes = bytes(pdf.output(dest="S"))  # ✅ força conversão para bytes

    return Response(
    pdf_bytes,
    mimetype="application/pdf",
    headers={"Content-Disposition": f'inline; filename="pedido_{pedido.id}.pdf"'}
    )

# =================== Área do ADMIN ==================



@app.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    # --- parâmetros de filtro ---
    filtro_status = request.args.get("status") or None
    filtro_cliente = request.args.get("cliente") or None
    data_inicio = request.args.get("data_inicio") or None
    data_fim = request.args.get("data_fim") or None

    # --- BASE QUERY com JOIN no usuario ---
    base_query = Pedido.query.join(Usuario)

    # filtro por status
    if filtro_status:
        base_query = base_query.filter(Pedido.status == filtro_status)

    # filtro por nome do cliente (LIKE)
    if filtro_cliente:
        base_query = base_query.filter(Usuario.nome.ilike(f"%{filtro_cliente}%"))

    # filtro por data início
    if data_inicio:
        try:
            di = datetime.strptime(data_inicio, "%Y-%m-%d")
            base_query = base_query.filter(Pedido.data_pedido >= di)
        except:
            pass

    # filtro por data fim
    if data_fim:
        try:
            df = datetime.strptime(data_fim, "%Y-%m-%d")
            df = df.replace(hour=23, minute=59, second=59)
            base_query = base_query.filter(Pedido.data_pedido <= df)
        except:
            pass

    # --- Paginação ordenada ---
    paged_query = base_query.order_by(Pedido.data_pedido.desc())

    pagina = request.args.get("page", 1, type=int)
    por_pagina = 8
    paginacao = paged_query.paginate(page=pagina, per_page=por_pagina, error_out=False)

    pedidos = paginacao.items
    total_paginas = paginacao.pages

    # calcula total individual por pedido (para o template)
    for pedido in pedidos:
        pedido.total = sum(
            item.quantidade * item.cupcake.preco
            for item in pedido.itens if item.cupcake
        )

    # --- MÉTRICAS (respeitando filtros) ---
    total_pedidos = base_query.count()

    total_clientes = base_query.with_entities(Pedido.usuario_id).distinct().count()

    total_faturado = 0
    for pedido in base_query.all():
        for item in pedido.itens:
            if item.cupcake:
                total_faturado += item.quantidade * item.cupcake.preco

    # --- gráfico por status (respeitando filtros) ---
    stats_status = {
        "Recebido":    base_query.filter(Pedido.status == "Recebido").count(),
        "Em produção": base_query.filter(Pedido.status == "Em produção").count(),
        "Pronto":      base_query.filter(Pedido.status == "Pronto").count(),
        "Entregue":    base_query.filter(Pedido.status == "Entregue").count(),
        "Cancelado":   base_query.filter(Pedido.status == "Cancelado").count(),
    }

    return render_template(
        "admin.html",
        pedidos=pedidos,
        pagina=pagina,
        total_paginas=total_paginas,
        filtro_status=filtro_status,
        filtro_cliente=filtro_cliente,
        data_inicio=data_inicio,
        data_fim=data_fim,
        total_pedidos=total_pedidos,
        total_clientes=total_clientes,
        total_faturado=total_faturado,
        stats_status=stats_status
    )

# ----------------- EXPORTAÇÃO EXCEL -----------------
@app.route("/admin/export/excel")
@login_required
@admin_required
def export_excel():
    pedidos = Pedido.query.all()
    dados = []

    for p in pedidos:
        total = sum(item.quantidade * item.cupcake.preco for item in p.itens if item.cupcake)
        dados.append([
            p.id,
            p.usuario.nome,
            p.status,
            p.data_pedido.strftime("%d/%m/%Y %H:%M"),
            total
        ])

    df = pd.DataFrame(dados, columns=["ID", "Cliente", "Status", "Data", "Total"])

    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(output, download_name="pedidos.xlsx", as_attachment=True)


# ----------------- EXPORTAÇÃO PDF -----------------

@app.route("/admin/export/pdf")
@login_required
@admin_required
def export_pdf():
    filtro_status = request.args.get("status")

    if filtro_status:
        pedidos = Pedido.query.filter_by(status=filtro_status).all()
    else:
        pedidos = Pedido.query.all()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Relatório de Pedidos", ln=True, align="C")
    pdf.ln(5)

    pdf.set_font("Arial", size=11)

    for p in pedidos:
        total = sum(it.quantidade * it.cupcake.preco for it in p.itens if it.cupcake)
        pdf.cell(0, 8, f"Pedido {p.id} - Cliente: {p.usuario.nome} - Total: R$ {total:.2f}", ln=True)
        pdf.cell(0, 6, f"Status: {p.status} | Data: {p.data_pedido.strftime('%d/%m/%Y %H:%M')}", ln=True)
        pdf.ln(2)

        for item in p.itens:
            if item.cupcake:
                pdf.cell(
                    0,
                    6,
                    f"- {item.quantidade}x {item.cupcake.nome} (R$ {(item.quantidade * item.cupcake.preco):.2f})",
                    ln=True,
                )
        pdf.ln(5)

    # ✅ CONVERSÃO OBRIGATÓRIA: bytearray → bytes
    pdf_bytes = pdf.output(dest="S")
    if isinstance(pdf_bytes, bytearray):
        pdf_bytes = bytes(pdf_bytes)

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=relatorio_pedidos.pdf"},
    )




# ------------------ DETALHES DO PEDIDO ------------------

@app.route("/admin/pedido/<int:pedido_id>")
@admin_required
def admin_pedido_detalhes(pedido_id):
    # Carrega o pedido + os itens + cupcakes de forma explícita
    pedido = (
        Pedido.query
        .options(joinedload(Pedido.itens).joinedload(PedidoCupcake.cupcake))
        .filter_by(id=pedido_id)
        .first_or_404()
    )

    # Garante que os itens foram carregados
    total_p = 0.0
    for item in pedido.itens:
        if item.cupcake:
            preco = float(item.cupcake.preco or 0)
            quantidade = int(item.quantidade or 0)
            total_p += preco * quantidade

    pedido.total = round(total_p, 2)

    return render_template(
        "admin_pedido_detalhes.html",
        pedido=pedido,
        total=pedido.total
    )


@app.route("/admin/pedido/<int:pedido_id>/delete", methods=["POST"])
@admin_required
def admin_pedido_delete(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    # opcional: remover itens primeiro (dependendo de cascade)
    for item in list(pedido.itens):
        db.session.delete(item)
    db.session.delete(pedido)
    db.session.commit()
    flash(f"Pedido #{pedido_id} excluído com sucesso.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/status/<int:pedido_id>", methods=["GET", "POST"])
@admin_required
def alterar_status(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)

    validos = ["Recebido", "Em produção", "Pronto", "Entregue"]

    if request.method == "POST":
        novo_status = request.form.get("status")
        if novo_status and novo_status in validos:
            pedido.status = novo_status
            db.session.commit()
            flash(f"Status do pedido #{pedido.id} atualizado para: {pedido.status}", "success")
        else:
            flash("Status inválido.", "danger")
        return redirect(url_for("admin_dashboard"))

    # GET: avança status sequencialmente
    try:
        ordem = validos
        index_atual = ordem.index(pedido.status) if pedido.status in ordem else -1
        pedido.status = ordem[(index_atual + 1) % len(ordem)]
        db.session.commit()
        flash(f"Status do pedido #{pedido.id} avançado para: {pedido.status}", "info")
    except Exception as e:
        flash("Não foi possível avançar o status.", "danger")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/pedido/<int:pedido_id>/status", methods=["POST"])
@admin_required
def admin_atualiza_status(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    novo_status = request.form.get("status")

    pedido.status = novo_status
    db.session.commit()

    # Salvar log
    log = PedidoStatusLog(pedido_id=pedido.id, status=novo_status)
    db.session.add(log)
    db.session.commit()

    flash("Status atualizado com sucesso!", "success")
    return redirect(url_for("admin_pedido_detalhes", pedido_id=pedido.id))



@app.route("/admin/pedido/<int:pedido_id>/cancelar", methods=["POST"])
@admin_required
def admin_cancelar_pedido(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    pedido.status = "Cancelado"
    db.session.commit()

    log = PedidoStatusLog(pedido_id=pedido.id, status="Cancelado")
    db.session.add(log)
    db.session.commit()

    flash("Pedido cancelado!", "danger")
    return redirect(url_for("admin_pedido_detalhes", pedido_id=pedido.id))


# =================== Execução ===================

if __name__ != "__main__":
    application = app

if __name__ == "__main__":
    app.run(debug=True)


from flask import send_file
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io


#rota exportar pdf

from flask import Response
import pandas as pd

@app.route('/exportar_excel')
@admin_required
def exportar_excel():

    status = request.args.get("status")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    cliente = request.args.get("cliente")

    query = Pedido.query.join(Usuario)

    if status:
        query = query.filter(Pedido.status == status)

    if data_inicio:
        query = query.filter(Pedido.data_pedido >= data_inicio)

    if data_fim:
        query = query.filter(Pedido.data_pedido <= data_fim)

    if cliente:
        query = query.filter(Usuario.nome.ilike(f"%{cliente}%"))

    pedidos = query.order_by(Pedido.data_pedido.desc()).all()

    # ✅ Calculando total dinamicamente
    dados = []
    for p in pedidos:
        total_calculado = sum(item.quantidade * item.cupcake.preco for item in p.itens)

        dados.append({
            "ID": p.id,
            "Cliente": p.usuario.nome,
            "Status": p.status,
            "Total (R$)": round(total_calculado, 2),
            "Data": p.data_pedido.strftime("%d/%m/%Y %H:%M") if p.data_pedido else "-"
        })

    df = pd.DataFrame(dados)

    # Gerando arquivo excel em memória
    output = pd.ExcelWriter('/tmp/pedidos.xlsx', engine='xlsxwriter')
    df.to_excel(output, index=False, sheet_name='Pedidos')
    output.close()

    with open('/tmp/pedidos.xlsx', 'rb') as f:
        file_data = f.read()

    return Response(
        file_data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=pedidos.xlsx"}
    )

#rota exportar pdf

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io
from flask import send_file

@app.route('/exportar_pdf')
@admin_required
def exportar_pdf():

    status = request.args.get("status")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    cliente = request.args.get("cliente")

    query = Pedido.query.join(Usuario)

    if status:
        query = query.filter(Pedido.status == status)

    if data_inicio:
        query = query.filter(Pedido.data_pedido >= data_inicio)

    if data_fim:
        query = query.filter(Pedido.data_pedido <= data_fim)

    if cliente:
        query = query.filter(Usuario.nome.ilike(f"%{cliente}%"))

    pedidos = query.order_by(Pedido.data_pedido.desc()).all()

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    y = 800
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Relatório de Pedidos")
    y -= 30

    pdf.setFont("Helvetica", 10)

    for pedido in pedidos:
        if y < 50:
            pdf.showPage()
            y = 800

        total_calculado = sum(item.quantidade * item.cupcake.preco for item in pedido.itens)

        pdf.drawString(60, y, f"Pedido #{pedido.id} - {pedido.status} - Cliente: {pedido.usuario.nome}")
        y -= 15
        pdf.drawString(80, y, f"Total: R$ {total_calculado:.2f}   Data: {pedido.data_pedido.strftime('%d/%m/%Y %H:%M')}")
        y -= 25

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="pedidos.pdf",
        mimetype="application/pdf"
    )

# cadastro de cupcake

@app.route("/admin/cupcake/novo", methods=["GET", "POST"])
@admin_required
def admin_cadastro_cupcake():
    if request.method == "POST":
        nome = request.form["nome"]
        descricao = request.form["descricao"]

        # --- validação do preço ---
        try:
            preco = float(request.form["preco"])
        except ValueError:
            flash("Preço inválido. Digite um valor numérico.", "danger")
            return redirect(url_for("admin_cadastro_cupcake"))

        if preco <= 0:
            flash("O preço deve ser maior que zero!", "danger")
            return redirect(url_for("admin_cadastro_cupcake"))
        # -----------------------------

        imagem = request.files["imagem"]
        filename = imagem.filename

        # Diretório correto (frontend/static/img)
        upload_dir = os.path.join(current_app.root_path, "..", "frontend", "static", "img")
        upload_dir = os.path.abspath(upload_dir)

        os.makedirs(upload_dir, exist_ok=True)

        caminho_salvar = os.path.join(upload_dir, filename)

        # Salva a imagem
        imagem.save(caminho_salvar)

        # Salva cupcake no banco
        novo = Cupcake(
            nome=nome,
            descricao=descricao,
            preco=preco,
            imagem_url=filename,
            ativo=True  # se esse campo existe
        )
        db.session.add(novo)
        db.session.commit()

        flash("Cupcake cadastrado com sucesso!", "success")
        return redirect(url_for("admin_listar_cupcakes"))

    return render_template("admin_cadastro_cupcake.html")


@app.route("/admin/cupcakes")
@admin_required
def admin_listar_cupcakes():
    cupcakes = Cupcake.query.all()

    from sqlalchemy.sql import func

    medias = (
        db.session.query(
            Cupcake.id,
            func.avg(Pedido.avaliacao).label("media_avaliacao")
        )
        .join(PedidoCupcake, PedidoCupcake.cupcake_id == Cupcake.id)
        .join(Pedido, Pedido.id == PedidoCupcake.pedido_id)
        .filter(Pedido.avaliacao.isnot(None))
        .group_by(Cupcake.id)
        .all()
    )

    medias_dict = {cupcake_id: float(media) for cupcake_id, media in medias}

    # 🟪 IDs de cupcakes que já foram usados em pedidos
    vendidos_ids = [
        id for (id,) in db.session.query(PedidoCupcake.cupcake_id).distinct().all()
    ]

    return render_template(
        "admin_listar_cupcakes.html",
        cupcakes=cupcakes,
        medias=medias_dict,
        vendidos_ids=vendidos_ids
    )

@app.route("/admin/cupcake/<int:cupcake_id>/pedidos")
@admin_required
def admin_pedidos_do_cupcake(cupcake_id):
    cupcake = Cupcake.query.get_or_404(cupcake_id)

    # Busca todos os itens de pedido desse cupcake
    itens = PedidoCupcake.query.filter_by(cupcake_id=cupcake_id).all()

    # Pega os pedidos únicos
    pedidos = [item.pedido for item in itens]

    return render_template(
        "admin_pedidos_por_cupcake.html",
        cupcake=cupcake,
        pedidos=pedidos
    )


#rota deletar cupcake 
@app.route("/admin/cupcake/delete/<int:id>", methods=["POST"])
@admin_required
def admin_deletar_cupcake(id):
    cupcake = Cupcake.query.get_or_404(id)

    # Verifica se já foi vendido
    associado = PedidoCupcake.query.filter_by(cupcake_id=id).first()

    if associado:
        # Não exclui → apenas desativa
        cupcake.ativo = False
        db.session.commit()
        flash("⚠️ Este cupcake já foi vendido. Ele foi DESATIVADO ao invés de excluído.", "warning")
        return redirect(url_for("admin_listar_cupcakes"))

    # Nunca vendido → pode excluir
    db.session.delete(cupcake)
    db.session.commit()

    flash("Cupcake excluído com sucesso!", "success")
    return redirect(url_for("admin_listar_cupcakes"))


#rota editar cupcake

@app.route("/admin/cupcake/edit/<int:id>", methods=["GET","POST"])
@admin_required
def admin_editar_cupcake(id):
    cupcake = Cupcake.query.get_or_404(id)

    if request.method == "POST":
        cupcake.nome = request.form["nome"]
        cupcake.descricao = request.form["descricao"]

        # --- validação do preço ---
        try:
            preco = float(request.form["preco"])
        except ValueError:
            flash("Preço inválido. Digite um valor numérico.", "danger")
            return redirect(request.url)

        if preco <= 0:
            flash("O preço deve ser maior que zero!", "danger")
            return redirect(request.url)

        cupcake.preco = preco
        # ---------------------------

        # ✔ Atualiza status ativo/inativo
        cupcake.ativo = "ativo" in request.form  

        # ✔ Se enviou nova imagem, atualizar
        imagem = request.files.get("imagem")
        if imagem and imagem.filename:
            filename = imagem.filename
            upload_dir = os.path.join(current_app.root_path, "..", "frontend", "static", "img")
            upload_dir = os.path.abspath(upload_dir)
            os.makedirs(upload_dir, exist_ok=True)
            imagem.save(os.path.join(upload_dir, filename))
            cupcake.imagem_url = filename

        db.session.commit()
        flash("Cupcake atualizado com sucesso!", "success")
        return redirect(url_for("admin_listar_cupcakes"))

    return render_template("admin_editar_cupcake.html", cupcake=cupcake)



# Avaliar pedido

@app.route("/avaliar_pedido/<int:pedido_id>", methods=["POST"])
@login_required
def avaliar_pedido(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)

    # Pedido deve ser do usuário
    if pedido.usuario_id != session.get("usuario_id"):
        return "Acesso negado", 403

    # Só pode avaliar pedidos entregues
    if pedido.status != "Entregue":
        flash("O pedido ainda não pode ser avaliado.", "warning")
        return redirect(url_for("pedido"))

    # Se já tem avaliação, não permite avaliar novamente
    if pedido.avaliacao is not None:
        flash("Este pedido já foi avaliado.", "info")
        return redirect(url_for("pedido"))

    nota = request.form.get("avaliacao", type=int)

    if nota and 1 <= nota <= 5:
        pedido.avaliacao = nota
        db.session.commit()
        flash("Obrigado pela avaliação! 🤗", "success")

    return redirect(url_for("pedido"))


@app.route("/buscar_cupcakes")
def buscar_cupcakes():
    termo = request.args.get("q", "").strip()

    if termo:
        resultados = Cupcake.query.filter(
            Cupcake.nome.ilike(f"%{termo}%"),
            Cupcake.ativo == True
        ).all()
    else:
        resultados = Cupcake.query.filter_by(ativo=True).all()

    return render_template("partials/_lista_cupcakes.html", cupcakes=resultados)


@app.route("/admin/usuarios")
@admin_required
def admin_usuarios():
    usuarios = Usuario.query.all()
    return render_template("admin_usuarios.html", usuarios=usuarios)

@app.route("/admin/usuario/delete/<int:id>", methods=["POST"])
@admin_required
def admin_deletar_usuario(id):
    usuario = Usuario.query.get_or_404(id)

    db.session.delete(usuario)
    db.session.commit()

    flash("Usuário excluído com sucesso!", "success")
    return redirect(url_for("admin_usuarios"))



@app.route("/admin/usuario/edit/<int:user_id>", methods=["GET", "POST"])
@admin_required
def admin_editar_usuario(user_id):
    usuario = Usuario.query.get_or_404(user_id)

    if request.method == "POST":
        # Atualiza dados básicos
        usuario.nome = request.form["nome"]
        usuario.email = request.form["email"]
        usuario.telefone = request.form.get("telefone")

        # Atualiza se é admin (checkbox)
        usuario.is_admin = "is_admin" in request.form

        # Atualiza senha somente se preenchida
        nova_senha = request.form.get("senha")
        if nova_senha:
            usuario.senha = generate_password_hash(nova_senha)

        db.session.commit()
        flash("Usuário atualizado com sucesso!", "success")
        return redirect(url_for("admin_usuarios"))

    return render_template("admin_editar_usuario.html", usuario=usuario)


@app.route("/esqueci_senha")
def esqueci_senha():
    telefone = "5511948083862"  # número da loja / suporte

    mensagem = (
        "Olá!%0A"
        "Eu gostaria de redefinir minha senha no aplicativo de Cupcakes.%0A"
        "Por favor, me ajude com o procedimento.%0A"
        "Obrigado! 😊"
    )

    whatsapp_url = f"https://wa.me/{telefone}?text={mensagem}"

    return redirect(whatsapp_url)

@app.route("/perfil/editar", methods=["GET", "POST"])
@login_required
def editar_perfil():
    usuario = Usuario.query.get_or_404(session["usuario_id"])

    if request.method == "POST":
        novo_email = request.form["email"]

        # 🔎 Verificar se o e-mail já pertence a outro usuário
        email_existente = Usuario.query.filter_by(email=novo_email).first()
        if email_existente and email_existente.id != usuario.id:
            flash("Este e-mail já está sendo utilizado por outro usuário.", "danger")
            return redirect(url_for("editar_perfil"))

        # ✔ Atualiza nome e email
        usuario.nome = request.form["nome"]
        usuario.email = novo_email
        usuario.telefone = request.form.get("telefone")

        # ✔ Atualiza senha apenas se foi preenchida
        nova_senha = request.form.get("senha")
        if nova_senha:
            usuario.senha = generate_password_hash(nova_senha)

        db.session.commit()
        flash("Perfil atualizado com sucesso!", "success")
        return redirect(url_for("home"))  # ou vitrine/pedidos, como preferir

    return render_template("editar_perfil.html", usuario=usuario)


@app.route("/fale_conosco")
def fale_conosco():
    telefone = "5511948083862"  # número da loja / suporte

    mensagem = (
        "Olá!%0A"
        "Preciso de ajuda com minha compra ou tenho uma dúvida sobre os cupcakes.%0A"
        "Poderiam me atender, por favor? 😊"
    )

    whatsapp_url = f"https://wa.me/{telefone}?text={mensagem}"

    return redirect(whatsapp_url)

