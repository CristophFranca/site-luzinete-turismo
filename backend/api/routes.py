"""
Rotas REST — Luzinete Turismo
Blueprints: auth · passagens · onibus · viagens · admin · encomendas
"""
from datetime import datetime, timedelta, date
from functools import wraps

from flask import Blueprint, jsonify, request, send_file, current_app
from flask_login import current_user, login_required, login_user, logout_user

from backend.models.models import db, Usuario, Onibus, Viagem, Passagem, Encomenda
from backend.services import passagens as svc_p
from backend.services import whatsapp as svc_w
from backend.services import backup as svc_b
from backend.services import feature_flags as svc_f
from backend.services import encomendas as svc_e
from backend.services import pdf_encomenda as svc_pdf
from backend.services import pdf_passagem as svc_pdf_p
from backend.services import update        as svc_upd

auth_bp   = Blueprint("auth",       __name__, url_prefix="/api/auth")
pass_bp   = Blueprint("pass",       __name__, url_prefix="/api/passagens")
bus_bp    = Blueprint("bus",        __name__, url_prefix="/api/onibus")
viagem_bp = Blueprint("viagem",     __name__, url_prefix="/api/viagens")
admin_bp  = Blueprint("admin",      __name__, url_prefix="/api/admin")
enc_bp    = Blueprint("encomendas", __name__, url_prefix="/api/encomendas")
relat_bp  = Blueprint("relatorio",  __name__, url_prefix="/api/relatorio")
busca_bp  = Blueprint("busca",      __name__, url_prefix="/api/busca")


def admin_only(f):
    @wraps(f)
    def inner(*a, **kw):
        if not current_user.is_authenticated or current_user.perfil != "admin":
            return jsonify({"erro": "Acesso restrito a administradores."}), 403
        return f(*a, **kw)
    return inner


# AUTH
@auth_bp.post("/login")
def login():
    d = request.json or {}
    u = Usuario.query.filter_by(email=d.get("email",""), ativo=True).first()
    if not u or not u.check_senha(d.get("senha","")):
        return jsonify({"erro": "E-mail ou senha incorretos."}), 401
    u.ultimo_acesso = datetime.utcnow()
    db.session.commit()
    login_user(u, remember=d.get("lembrar", False))
    return jsonify({"nome": u.nome, "perfil": u.perfil})

@auth_bp.post("/logout")
@login_required
def logout():
    logout_user()
    return jsonify({"ok": True})

@auth_bp.get("/me")
@login_required
def me():
    return jsonify({"id": current_user.id, "nome": current_user.nome, "perfil": current_user.perfil})


# ONIBUS
@bus_bp.get("/")
@login_required
def listar_onibus():
    lista = Onibus.query.filter_by(ativo=True).order_by(Onibus.identificador).all()
    return jsonify([{"id":o.id,"identificador":o.identificador,"placa":o.placa,
                     "modelo":o.modelo,"total_poltronas":o.total_poltronas,
                     "rastreio_url":o.rastreio_url,"ativo":o.ativo} for o in lista])

@bus_bp.get("/todos")
@login_required
@admin_only
def todos_onibus():
    lista = Onibus.query.order_by(Onibus.identificador).all()
    return jsonify([{"id":o.id,"identificador":o.identificador,"placa":o.placa,
                     "modelo":o.modelo,"total_poltronas":o.total_poltronas,
                     "rastreio_url":o.rastreio_url,"ativo":o.ativo} for o in lista])

@bus_bp.post("/")
@login_required
@admin_only
def cadastrar_onibus():
    if not svc_f.is_enabled("cadastro_onibus"):
        return jsonify({"erro": "Desativado."}), 403
    d = request.json or {}
    if not d.get("identificador") or not d.get("placa"):
        return jsonify({"erro": "Identificador e placa obrigatórios."}), 400
    o = Onibus(identificador=d["identificador"].upper(), placa=d["placa"].upper(),
               modelo=d.get("modelo",""), total_poltronas=int(d.get("total_poltronas",44)),
               rastreio_url=d.get("rastreio_url",""))
    db.session.add(o); db.session.commit()
    return jsonify({"id":o.id,"mensagem":"Ônibus cadastrado."}), 201

@bus_bp.put("/<int:oid>")
@login_required
@admin_only
def atualizar_onibus(oid):
    o = db.session.get(Onibus, oid)
    if not o: return jsonify({"erro":"Não encontrado."}), 404
    d = request.json or {}
    for c in ("identificador","placa","modelo","total_poltronas","rastreio_url","ativo"):
        if c in d: setattr(o, c, d[c])
    db.session.commit()
    return jsonify({"mensagem":"Ônibus atualizado."})

@bus_bp.delete("/<int:oid>")
@login_required
@admin_only
def desativar_onibus(oid):
    o = db.session.get(Onibus, oid)
    if not o: return jsonify({"erro":"Nao encontrado."}), 404
    o.ativo = False; db.session.commit()
    return jsonify({"mensagem":"Onibus desativado."})

@bus_bp.delete("/<int:oid>/excluir")
@login_required
@admin_only
def excluir_onibus(oid):
    o = db.session.get(Onibus, oid)
    if not o: return jsonify({"erro":"Nao encontrado."}), 404
    # Proteger se tiver viagens com passagens ou encomendas (lazy=dynamic, usar .all())
    viagens = o.viagens.all()
    for v in viagens:
        if v.passagens.filter_by(cancelada=False).count() > 0:
            return jsonify({"erro": "Nao e possivel excluir: ha passagens ativas neste onibus. Desative-o em vez de excluir."}), 400
        if v.encomendas.filter_by(cancelada=False).count() > 0:
            return jsonify({"erro": "Nao e possivel excluir: ha encomendas ativas neste onibus. Desative-o em vez de excluir."}), 400
    # Excluir cascata
    for v in viagens:
        for p in v.passagens.all(): db.session.delete(p)
        for e in v.encomendas.all(): db.session.delete(e)
        db.session.delete(v)
    db.session.delete(o)
    db.session.commit()
    return jsonify({"mensagem": "Onibus excluido com sucesso."})


# VIAGENS
@viagem_bp.get("/")
@login_required
def listar_viagens():
    status = request.args.get("status","aberta")
    oid = request.args.get("onibus_id", type=int)
    q = Viagem.query
    if status: q = q.filter_by(status=status)
    if oid: q = q.filter_by(onibus_id=oid)
    return jsonify([v.to_dict() for v in q.order_by(Viagem.data_partida.desc()).all()])

@viagem_bp.post("/")
@login_required
@admin_only
def criar_viagem():
    d = request.json or {}
    # Validacoes
    if not d.get("origem"):
        return jsonify({"erro": "Origem e obrigatoria."}), 400
    if not d.get("destino"):
        return jsonify({"erro": "Destino e obrigatorio."}), 400
    if not d.get("data_partida"):
        return jsonify({"erro": "Data de partida e obrigatoria."}), 400
    if not d.get("empresa"):
        return jsonify({"erro": "Nome da empresa/onibus e obrigatorio."}), 400
    try:
        partida = datetime.fromisoformat(d["data_partida"])
        retorno = datetime.fromisoformat(d["data_retorno"]) if d.get("data_retorno") else None
    except ValueError as e:
        return jsonify({"erro": f"Data invalida: {e}"}), 400
    v = Viagem(
        onibus_id      = d.get("onibus_id") or None,   # opcional
        empresa        = d["empresa"].strip(),
        total_poltronas= int(d.get("total_poltronas") or 44),
        origem         = d["origem"].strip(),
        destino        = d["destino"].strip(),
        data_partida   = partida,
        data_retorno   = retorno,
        tipo           = "ida_volta" if retorno else "ida",
        valor_inteiro  = float(d.get("valor_inteiro") or 0),
        valor_meia     = float(d["valor_meia"]) if d.get("valor_meia") else None,
    )
    db.session.add(v)
    db.session.commit()
    return jsonify({"id": v.id, "mensagem": "Viagem criada."}), 201

@viagem_bp.put("/<int:vid>")
@login_required
@admin_only
def atualizar_viagem(vid):
    v = db.session.get(Viagem, vid)
    if not v: return jsonify({"erro":"Não encontrada."}), 404
    d = request.json or {}
    for c in ("origem","destino","status","valor_inteiro","valor_meia"):
        if c in d: setattr(v, c, d[c])
    db.session.commit()
    return jsonify({"mensagem":"Viagem atualizada."})


# PASSAGENS
@pass_bp.get("/poltronas/<int:viagem_id>")
@login_required
def poltronas(viagem_id):
    v = db.session.get(Viagem, viagem_id)
    if not v: return jsonify({"erro": "Viagem nao encontrada."}), 404
    total = v.total_poltronas or (v.onibus.total_poltronas if v.onibus else 44)
    return jsonify({"total": total, "ocupadas": svc_p.poltronas_ocupadas(viagem_id)})

@pass_bp.post("/emitir")
@login_required
def emitir():
    d = request.json or {}
    valor_pago     = float(d.get("valor_pago", 0))
    valor_original = float(d.get("valor_original", valor_pago))
    _poltrona = d.get("numero_poltrona")
    _poltrona = int(_poltrona) if _poltrona not in (None, "", 0, "0") else None
    ok, msg, p = svc_p.emitir(
        viagem_id=d.get("viagem_id"), operador_id=current_user.id,
        numero_poltrona=_poltrona,
        passageiro_nome=d.get("passageiro_nome",""),
        passageiro_cpf=d.get("passageiro_cpf",""),
        passageiro_telefone=d.get("passageiro_telefone",""),
        passageiro_whatsapp=d.get("passageiro_whatsapp",""),
        tipo_passagem=d.get("tipo_passagem","inteiro"),
        valor_pago=valor_pago,
        forma_pagamento=d.get("forma_pagamento","dinheiro"),
        valor_original=valor_original,
    )
    if not ok: return jsonify({"erro":msg}), 400
    if svc_f.is_enabled("whatsapp") and p.passageiro_whatsapp:
        try:
            svc_w.enviar(p.id)
        except Exception:
            pass
    return jsonify({"mensagem":msg,"codigo":p.codigo,"id":p.id}), 201

@pass_bp.post("/<int:pid>/cancelar")
@login_required
def cancelar(pid):
    ok, msg = svc_p.cancelar(pid)
    return (jsonify({"mensagem":msg}) if ok else jsonify({"erro":msg})), (200 if ok else 400)

@pass_bp.post("/<int:pid>/whatsapp")
@login_required
def reenviar_wpp(pid):
    ok, info = svc_w.enviar(pid)
    if not ok:
        return jsonify({"erro": info}), 400
    provider = current_app.config.get("WHATSAPP_PROVIDER", "wame")
    if provider == "wame":
        # Retorna link para o frontend abrir
        return jsonify({"link": info, "wame": True}), 200
    return jsonify({"mensagem": info}), 200

@pass_bp.get("/<int:pid>/whatsapp/link")
@login_required
def link_wame(pid):
    ok, link = svc_w.gerar_link_wame(pid)
    if not ok:
        return jsonify({"erro": link}), 400
    return jsonify({"link": link}), 200

@pass_bp.get("/historico/onibus/<int:oid>")
@login_required
def historico_onibus(oid):
    return jsonify(svc_p.historico_onibus(oid))

@pass_bp.get("/historico/viagem/<int:vid>")
@login_required
def historico_viagem(vid):
    v = db.session.get(Viagem, vid)
    if not v: return jsonify({"erro": "Viagem nao encontrada."}), 404
    passagens = svc_p.historico_viagem(vid)
    ativas = [p for p in passagens if not p.cancelada]
    return jsonify({
        "viagem":       v.to_dict(),
        "passagens":    [p.to_dict() for p in passagens],
        "total_ativas": len(ativas),
        "receita":      sum(p.valor_pago for p in ativas),
    })

@pass_bp.get("/viagem/<int:vid>")
@login_required
def passagens_viagem(vid):
    return jsonify([p.to_dict() for p in svc_p.historico_viagem(vid)])

@pass_bp.get("/buscar")
@login_required
def buscar():
    q = request.args.get("q","").strip()
    if not q: return jsonify([])
    res = (Passagem.query
           .filter((Passagem.passageiro_nome.ilike(f"%{q}%")) |
                   (Passagem.codigo.ilike(f"%{q}%")) |
                   (Passagem.passageiro_cpf.ilike(f"%{q}%")))
           .order_by(Passagem.emitida_em.desc()).limit(20).all())
    return jsonify([p.to_dict() for p in res])


# ENCOMENDAS
@enc_bp.post("/registrar")
@login_required
def registrar_encomenda():
    d = request.json or {}
    ok, msg, enc = svc_e.registrar(
        viagem_id=d.get("viagem_id"),
        onibus_id=d.get("onibus_id"),
        operador_id=current_user.id,
        remetente_nome=d.get("remetente_nome",""),
        remetente_cpf=d.get("remetente_cpf",""),
        remetente_telefone=d.get("remetente_telefone",""),
        remetente_cidade=d.get("remetente_cidade",""),
        destinatario_nome=d.get("destinatario_nome",""),
        destinatario_cpf=d.get("destinatario_cpf",""),
        destinatario_telefone=d.get("destinatario_telefone",""),
        destinatario_cidade=d.get("destinatario_cidade",""),
        descricao=d.get("descricao",""),
        peso_kg=float(d["peso_kg"]) if d.get("peso_kg") else None,
        valor_frete=float(d.get("valor_frete",0)),
        valor_declarado=float(d["valor_declarado"]) if d.get("valor_declarado") else None,
        forma_pagamento=d.get("forma_pagamento","dinheiro"),
        observacoes=d.get("observacoes",""),
    )
    if not ok: return jsonify({"erro":msg}), 400
    return jsonify({"mensagem":msg,"codigo":enc.codigo,"id":enc.id}), 201

@enc_bp.get("/<int:enc_id>")
@login_required
def detalhe(enc_id):
    enc = db.session.get(Encomenda, enc_id)
    if not enc: return jsonify({"erro":"Não encontrada."}), 404
    return jsonify(enc.to_dict())

@enc_bp.put("/<int:enc_id>/status")
@login_required
def atualizar_status(enc_id):
    d = request.json or {}
    ok, msg = svc_e.atualizar_status(enc_id, d.get("status",""))
    return (jsonify({"mensagem":msg}) if ok else jsonify({"erro":msg})), (200 if ok else 400)

@enc_bp.post("/<int:enc_id>/cancelar")
@login_required
def cancelar_enc(enc_id):
    ok, msg = svc_e.cancelar(enc_id)
    return (jsonify({"mensagem":msg}) if ok else jsonify({"erro":msg})), (200 if ok else 400)

@enc_bp.get("/<int:enc_id>/pdf")
@login_required
def gerar_pdf(enc_id):
    """Gera etiqueta PDF para impressão."""
    enc = db.session.get(Encomenda, enc_id)
    if not enc: return jsonify({"erro":"Não encontrada."}), 404
    buf = svc_pdf.gerar_etiqueta_pdf(enc)
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=False,
                     download_name=f"encomenda_{enc.codigo}.pdf")

@enc_bp.get("/historico/onibus/<int:oid>")
@login_required
def historico_onibus_enc(oid):
    return jsonify(svc_e.historico_onibus(oid))

@enc_bp.get("/historico/viagem/<int:vid>")
@login_required
def historico_viagem_enc(vid):
    v = db.session.get(Viagem, vid)
    if not v: return jsonify({"erro": "Viagem nao encontrada."}), 404
    encs = svc_e.historico_viagem(vid)
    ativas = [e for e in encs if not e.cancelada]
    return jsonify({
        "viagem":        v.to_dict(),
        "encomendas":    [e.to_dict() for e in encs],
        "total_ativas":  len(ativas),
        "receita_frete": sum(e.valor_frete for e in ativas),
    })

@enc_bp.get("/viagem/<int:vid>")
@login_required
def encomendas_viagem(vid):
    return jsonify([e.to_dict() for e in svc_e.historico_viagem(vid)])

@enc_bp.get("/buscar")
@login_required
def buscar_enc():
    q = request.args.get("q","").strip()
    if not q: return jsonify([])
    return jsonify([e.to_dict() for e in svc_e.buscar(q)])


# ADMIN
@admin_bp.get("/features")
@login_required
@admin_only
def features(): return jsonify(svc_f.get_all())

@admin_bp.put("/features/<chave>")
@login_required
@admin_only
def toggle_feature(chave):
    d = request.json or {}
    ok = svc_f.toggle(chave, d.get("ativo",False))
    if not ok: return jsonify({"erro":"Não encontrada."}), 404
    return jsonify({"mensagem":f"Feature '{chave}' atualizada."})

@admin_bp.post("/backup")
@login_required
@admin_only
def fazer_backup():
    ok, info = svc_b.realizar()
    return (jsonify({"mensagem":info}) if ok else jsonify({"erro":info})), (200 if ok else 500)

@admin_bp.get("/backups")
@login_required
@admin_only
def listar_backups(): return jsonify(svc_b.listar())

@admin_bp.get("/dashboard-stats")
@login_required
def dashboard_stats():
    hoje = datetime.utcnow().date()
    passagens_hoje = Passagem.query.filter(
        Passagem.cancelada==False, db.func.date(Passagem.emitida_em)==hoje).count()
    receita_hoje = db.session.query(db.func.sum(Passagem.valor_pago)).filter(
        Passagem.cancelada==False, db.func.date(Passagem.emitida_em)==hoje).scalar() or 0
    encomendas_hoje = Encomenda.query.filter(
        Encomenda.cancelada==False, db.func.date(Encomenda.registrada_em)==hoje).count()
    frete_hoje = db.session.query(db.func.sum(Encomenda.valor_frete)).filter(
        Encomenda.cancelada==False, db.func.date(Encomenda.registrada_em)==hoje).scalar() or 0
    return jsonify({
        "viagens_abertas": Viagem.query.filter_by(status="aberta").count(),
        "passagens_hoje": passagens_hoje,
        "receita_hoje": float(receita_hoje),
        "encomendas_hoje": encomendas_hoje,
        "frete_hoje": float(frete_hoje),
        "onibus_ativos": Onibus.query.filter_by(ativo=True).count(),
    })





# ══════════════════════════════════════════════════════════════
# PDF PASSAGEM
# ══════════════════════════════════════════════════════════════
@pass_bp.get("/<int:pid>/pdf")
@login_required
def pdf_passagem(pid):
    p = db.session.get(Passagem, pid)
    if not p:
        return jsonify({"erro": "Passagem nao encontrada."}), 404
    buf = svc_pdf_p.gerar_comprovante_pdf(p)
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=False,
                     download_name=f"passagem_{p.codigo}.pdf")


# ══════════════════════════════════════════════════════════════
# BUSCA GLOBAL
# ══════════════════════════════════════════════════════════════
@busca_bp.get("/")
@login_required
def busca_global():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"passagens": [], "encomendas": []})

    passagens = (
        Passagem.query
        .filter(
            (Passagem.passageiro_nome.ilike(f"%{q}%")) |
            (Passagem.codigo.ilike(f"%{q}%")) |
            (Passagem.passageiro_cpf.ilike(f"%{q}%")) |
            (Passagem.passageiro_telefone.ilike(f"%{q}%"))
        )
        .order_by(Passagem.emitida_em.desc()).limit(8).all()
    )

    encomendas = (
        Encomenda.query
        .filter(
            (Encomenda.codigo.ilike(f"%{q}%")) |
            (Encomenda.remetente_nome.ilike(f"%{q}%")) |
            (Encomenda.destinatario_nome.ilike(f"%{q}%")) |
            (Encomenda.remetente_cpf.ilike(f"%{q}%")) |
            (Encomenda.destinatario_cpf.ilike(f"%{q}%"))
        )
        .order_by(Encomenda.registrada_em.desc()).limit(8).all()
    )

    return jsonify({
        "passagens": [
            {
                "id": p.id,
                "codigo": p.codigo,
                "nome": p.passageiro_nome,
                "poltrona": p.numero_poltrona,
                "origem": p.viagem.origem,
                "destino": p.viagem.destino,
                "data": p.viagem.data_partida.strftime("%d/%m/%Y"),
                "cancelada": p.cancelada,
            }
            for p in passagens
        ],
        "encomendas": [
            {
                "id": e.id,
                "codigo": e.codigo,
                "remetente": e.remetente_nome,
                "destinatario": e.destinatario_nome,
                "origem": e.viagem.origem,
                "destino": e.viagem.destino,
                "status": e.status,
            }
            for e in encomendas
        ],
    })


# ══════════════════════════════════════════════════════════════
# RELATORIO FINANCEIRO
# ══════════════════════════════════════════════════════════════
@relat_bp.get("/financeiro")
@login_required
def relatorio_financeiro():
    periodo = request.args.get("periodo", "mes")   # dia | semana | mes | ano
    onibus_id = request.args.get("onibus_id", type=int)

    hoje = datetime.utcnow().date()

    if periodo == "dia":
        inicio = hoje
    elif periodo == "semana":
        from datetime import timedelta
        inicio = hoje - timedelta(days=hoje.weekday())
    elif periodo == "ano":
        inicio = hoje.replace(month=1, day=1)
    else:  # mes
        inicio = hoje.replace(day=1)

    # --- Passagens ---
    q_pass = Passagem.query.join(Viagem).filter(
        Passagem.cancelada == False,
        db.func.date(Passagem.emitida_em) >= inicio,
    )
    if onibus_id:
        q_pass = q_pass.filter(Viagem.onibus_id == onibus_id)

    passagens = q_pass.all()
    receita_passagens = sum(p.valor_pago for p in passagens)
    total_passagens   = len(passagens)
    qtd_inteiro       = sum(1 for p in passagens if p.tipo_passagem == "inteiro")
    qtd_meia          = sum(1 for p in passagens if p.tipo_passagem == "meia")

    # Por forma de pagamento
    pgto_pass = {}
    for p in passagens:
        pgto_pass[p.forma_pagamento] = pgto_pass.get(p.forma_pagamento, 0) + p.valor_pago

    # --- Encomendas ---
    q_enc = Encomenda.query.join(Viagem).filter(
        Encomenda.cancelada == False,
        db.func.date(Encomenda.registrada_em) >= inicio,
    )
    if onibus_id:
        q_enc = q_enc.filter(Viagem.onibus_id == onibus_id)

    encomendas = q_enc.all()
    receita_fretes  = sum(e.valor_frete for e in encomendas)
    total_encomendas = len(encomendas)

    pgto_enc = {}
    for e in encomendas:
        pgto_enc[e.forma_pagamento] = pgto_enc.get(e.forma_pagamento, 0) + e.valor_frete

    # --- Serie diaria (ultimos 30 dias agrupados por dia) ---
    serie = []
    dias = 30 if periodo in ("mes", "semana") else (365 if periodo == "ano" else 7)
    for i in range(min(dias, (hoje - inicio).days + 1)):
        d = inicio + timedelta(days=i)
        rec_p = sum(p.valor_pago for p in passagens
                    if p.emitida_em.date() == d)
        rec_e = sum(e.valor_frete for e in encomendas
                    if e.registrada_em.date() == d)
        if rec_p > 0 or rec_e > 0:
            serie.append({
                "data": d.strftime("%d/%m"),
                "passagens": round(rec_p, 2),
                "fretes":    round(rec_e, 2),
                "total":     round(rec_p + rec_e, 2),
            })

    # --- Top viagens/empresas ---
    por_onibus = defaultdict(lambda: {"passagens": 0, "encomendas": 0, "receita": 0.0})
    for p in passagens:
        # usa empresa da viagem ou identificador do onibus ou fallback
        v = p.viagem
        key = v.empresa or (v.onibus.identificador if v.onibus else "Sem empresa")
        por_onibus[key]["passagens"] += 1
        por_onibus[key]["receita"]   += p.valor_pago
    for e in encomendas:
        v = e.viagem
        key = v.empresa or (v.onibus.identificador if v.onibus else "Sem empresa")
        por_onibus[key]["encomendas"] += 1
        por_onibus[key]["receita"]    += e.valor_frete

    return jsonify({
        "periodo": periodo,
        "inicio": inicio.strftime("%d/%m/%Y"),
        "hoje": hoje.strftime("%d/%m/%Y"),
        "resumo": {
            "receita_total":     round(receita_passagens + receita_fretes, 2),
            "receita_passagens": round(receita_passagens, 2),
            "receita_fretes":    round(receita_fretes, 2),
            "total_passagens":   total_passagens,
            "total_encomendas":  total_encomendas,
            "qtd_inteiro":       qtd_inteiro,
            "qtd_meia":          qtd_meia,
        },
        "pagamentos_passagens": pgto_pass,
        "pagamentos_encomendas": pgto_enc,
        "serie_diaria": serie,
        "por_onibus": [
            {"onibus": k, **v} for k, v in sorted(
                por_onibus.items(), key=lambda x: -x[1]["receita"])
        ],
    })


# ══════════════════════════════════════════════════════════════
# GESTAO DE USUARIOS
# ══════════════════════════════════════════════════════════════
@admin_bp.get("/usuarios")
@login_required
@admin_only
def listar_usuarios():
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    return jsonify([{
        "id":        u.id,
        "nome":      u.nome,
        "email":     u.email,
        "perfil":    u.perfil,
        "ativo":     u.ativo,
        "ultimo_acesso": u.ultimo_acesso.strftime("%d/%m/%Y %H:%M") if u.ultimo_acesso else "Nunca",
    } for u in usuarios])

@admin_bp.post("/usuarios")
@login_required
@admin_only
def criar_usuario():
    d = request.json or {}
    nome  = (d.get("nome") or "").strip()
    email = (d.get("email") or "").strip().lower()
    senha = (d.get("senha") or "").strip()
    perfil = d.get("perfil", "operador")

    if not nome or not email or not senha:
        return jsonify({"erro": "Nome, e-mail e senha sao obrigatorios."}), 400
    if len(senha) < 6:
        return jsonify({"erro": "Senha deve ter ao menos 6 caracteres."}), 400
    if perfil not in ("operador", "admin"):
        return jsonify({"erro": "Perfil invalido."}), 400
    if Usuario.query.filter_by(email=email).first():
        return jsonify({"erro": "E-mail ja cadastrado."}), 400

    u = Usuario(nome=nome, email=email, perfil=perfil, ativo=True)
    u.set_senha(senha)
    db.session.add(u)
    db.session.commit()
    return jsonify({"id": u.id, "mensagem": f"Usuario '{nome}' criado com sucesso."}), 201

@admin_bp.put("/usuarios/<int:uid>")
@login_required
@admin_only
def editar_usuario(uid):
    u = db.session.get(Usuario, uid)
    if not u:
        return jsonify({"erro": "Usuario nao encontrado."}), 404
    if u.id == current_user.id:
        return jsonify({"erro": "Nao e possivel editar o proprio usuario aqui."}), 400
    d = request.json or {}
    if "nome"  in d: u.nome  = d["nome"].strip()
    if "email" in d: u.email = d["email"].strip().lower()
    if "perfil" in d and d["perfil"] in ("operador", "admin"): u.perfil = d["perfil"]
    if "ativo"  in d: u.ativo = bool(d["ativo"])
    if d.get("senha") and len(d["senha"]) >= 6: u.set_senha(d["senha"])
    db.session.commit()
    return jsonify({"mensagem": "Usuario atualizado."})

@admin_bp.delete("/usuarios/<int:uid>")
@login_required
@admin_only
def desativar_usuario(uid):
    u = db.session.get(Usuario, uid)
    if not u:
        return jsonify({"erro": "Usuario nao encontrado."}), 404
    if u.id == current_user.id:
        return jsonify({"erro": "Nao e possivel desativar o proprio usuario."}), 400
    u.ativo = False
    db.session.commit()
    return jsonify({"mensagem": f"Usuario '{u.nome}' desativado."})

# ══════════════════════════════════════════════════════════════
# UPDATE
# ══════════════════════════════════════════════════════════════
upd_bp = Blueprint("update", __name__, url_prefix="/api/update")

@upd_bp.get("/status")
@login_required
@admin_only
def update_status():
    info = svc_upd.buscar_update()
    return jsonify({
        "versao_atual": svc_upd.versao_atual(),
        "update":       info,
    })

@upd_bp.post("/aplicar")
@login_required
@admin_only
def update_aplicar():
    ok, msg = svc_upd.aplicar_update()
    if ok:
        return jsonify({"mensagem": msg}), 200
    return jsonify({"erro": msg}), 400


def registrar(app):
    for bp in (auth_bp, pass_bp, bus_bp, viagem_bp, admin_bp, enc_bp, relat_bp, busca_bp, upd_bp):
        app.register_blueprint(bp)