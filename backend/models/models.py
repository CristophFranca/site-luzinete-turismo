"""
Modelos SQLAlchemy — Luzinete Turismo
Banco: SQLite (arquivo database/luzinete.db)
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import bcrypt

db = SQLAlchemy()


class Usuario(db.Model, UserMixin):
    __tablename__ = "usuarios"
    id            = db.Column(db.Integer, primary_key=True)
    nome          = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(150), unique=True, nullable=False)
    senha_hash    = db.Column(db.String(255), nullable=False)
    perfil        = db.Column(db.String(10), default="operador")
    ativo         = db.Column(db.Boolean, default=True)
    criado_em     = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_acesso = db.Column(db.DateTime)
    passagens     = db.relationship("Passagem",  backref="operador", lazy="dynamic")
    encomendas    = db.relationship("Encomenda", backref="operador", lazy="dynamic")

    def set_senha(self, senha):
        self.senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()

    def check_senha(self, senha):
        return bcrypt.checkpw(senha.encode(), self.senha_hash.encode())

    def __repr__(self): return f"<Usuario {self.email}>"


class Onibus(db.Model):
    __tablename__ = "onibus"
    id              = db.Column(db.Integer, primary_key=True)
    identificador   = db.Column(db.String(20), unique=True, nullable=False)
    placa           = db.Column(db.String(10), unique=True, nullable=False)
    modelo          = db.Column(db.String(100), default="")
    total_poltronas = db.Column(db.Integer, nullable=False, default=44)
    ativo           = db.Column(db.Boolean, default=True)
    rastreio_url    = db.Column(db.String(500), default="")
    criado_em       = db.Column(db.DateTime, default=datetime.utcnow)
    viagens         = db.relationship("Viagem",    backref="onibus", lazy="dynamic")
    encomendas      = db.relationship("Encomenda", backref="onibus", lazy="dynamic")

    def __repr__(self): return f"<Onibus {self.identificador}>"


class Viagem(db.Model):
    __tablename__ = "viagens"
    id            = db.Column(db.Integer, primary_key=True)
    # onibus_id agora e opcional — viagem pode existir sem onibus cadastrado
    onibus_id     = db.Column(db.Integer, db.ForeignKey("onibus.id"), nullable=True)
    empresa       = db.Column(db.String(150), default="")   # ex: "Vanda Turismo"
    total_poltronas = db.Column(db.Integer, nullable=False, default=44)
    origem        = db.Column(db.String(100), nullable=False)
    destino       = db.Column(db.String(100), nullable=False)
    data_partida  = db.Column(db.DateTime, nullable=False)
    data_retorno  = db.Column(db.DateTime, nullable=True)
    tipo          = db.Column(db.String(10), default="ida")
    valor_inteiro = db.Column(db.Float, nullable=False, default=0.0)
    valor_meia    = db.Column(db.Float, nullable=True)
    status        = db.Column(db.String(12), default="aberta")
    criado_em     = db.Column(db.DateTime, default=datetime.utcnow)
    passagens     = db.relationship("Passagem",  backref="viagem", lazy="dynamic")
    encomendas    = db.relationship("Encomenda", backref="viagem", lazy="dynamic")

    @property
    def poltronas_ocupadas_count(self):
        return self.passagens.filter_by(cancelada=False).count()

    @property
    def poltronas_livres_count(self):
        total = self.total_poltronas or (self.onibus.total_poltronas if self.onibus else 44)
        return total - self.poltronas_ocupadas_count

    def to_dict(self):
        # empresa: usa campo proprio ou fallback para identificador do onibus
        empresa = self.empresa or (self.onibus.identificador if self.onibus else "")
        # poltronas: usa campo proprio ou fallback para onibus vinculado
        total = self.total_poltronas or (self.onibus.total_poltronas if self.onibus else 44)
        return {
            "id": self.id, "onibus_id": self.onibus_id,
            "onibus": empresa,
            "empresa": empresa,
            "origem": self.origem, "destino": self.destino,
            "data_partida": self.data_partida.isoformat(),
            "data_retorno": self.data_retorno.isoformat() if self.data_retorno else None,
            "tipo": self.tipo, "valor_inteiro": self.valor_inteiro,
            "valor_meia": self.valor_meia, "status": self.status,
            "total_poltronas": total,
            "ocupadas": self.poltronas_ocupadas_count,
            "livres": self.poltronas_livres_count,
        }

    def __repr__(self): return f"<Viagem {self.origem}->{self.destino}>"


class Passagem(db.Model):
    __tablename__ = "passagens"
    id                  = db.Column(db.Integer, primary_key=True)
    codigo              = db.Column(db.String(20), unique=True, nullable=False)
    viagem_id           = db.Column(db.Integer, db.ForeignKey("viagens.id"), nullable=False)
    operador_id         = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    passageiro_nome     = db.Column(db.String(150), nullable=False)
    passageiro_cpf      = db.Column(db.String(14), default="")
    passageiro_telefone = db.Column(db.String(20), default="")
    passageiro_whatsapp = db.Column(db.String(20), default="")
    numero_poltrona     = db.Column(db.Integer, nullable=True)   # None = poltrona a definir
    tipo_passagem       = db.Column(db.String(10), default="inteiro")
    valor_original      = db.Column(db.Float, nullable=True)   # valor antes do desconto
    valor_pago          = db.Column(db.Float, nullable=False)
    forma_pagamento     = db.Column(db.String(10), default="dinheiro")
    cancelada           = db.Column(db.Boolean, default=False)
    whatsapp_enviado    = db.Column(db.Boolean, default=False)
    emitida_em          = db.Column(db.DateTime, default=datetime.utcnow)
    cancelada_em        = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id, "codigo": self.codigo,
            "viagem_id": self.viagem_id,
            "origem": self.viagem.origem, "destino": self.viagem.destino,
            "data_partida": self.viagem.data_partida.isoformat(),
            "onibus": self.viagem.empresa or (self.viagem.onibus.identificador if self.viagem.onibus else ""),
            "passageiro_nome": self.passageiro_nome,
            "passageiro_cpf": self.passageiro_cpf,
            "passageiro_telefone": self.passageiro_telefone,
            "passageiro_whatsapp": self.passageiro_whatsapp,
            "numero_poltrona": self.numero_poltrona,  # None = a definir
            "tipo_passagem": self.tipo_passagem,
            "valor_pago": self.valor_pago,
            "valor_original": self.valor_original or self.valor_pago,
            "forma_pagamento": self.forma_pagamento,
            "cancelada": self.cancelada,
            "whatsapp_enviado": self.whatsapp_enviado,
            "emitida_em": self.emitida_em.isoformat(),
        }

    def __repr__(self): return f"<Passagem {self.codigo}>"


# ══════════════════════════════════════════════════════════════
# ENCOMENDA
# ══════════════════════════════════════════════════════════════
class Encomenda(db.Model):
    __tablename__ = "encomendas"
    id          = db.Column(db.Integer, primary_key=True)
    codigo      = db.Column(db.String(25), unique=True, nullable=False)
    viagem_id   = db.Column(db.Integer, db.ForeignKey("viagens.id"), nullable=False)
    onibus_id   = db.Column(db.Integer, db.ForeignKey("onibus.id"), nullable=False)
    operador_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)

    # Remetente
    remetente_nome     = db.Column(db.String(150), nullable=False)
    remetente_cpf      = db.Column(db.String(14), default="")
    remetente_telefone = db.Column(db.String(20), default="")
    remetente_cidade   = db.Column(db.String(100), default="")

    # Destinatario
    destinatario_nome     = db.Column(db.String(150), nullable=False)
    destinatario_cpf      = db.Column(db.String(14), default="")
    destinatario_telefone = db.Column(db.String(20), default="")
    destinatario_cidade   = db.Column(db.String(100), default="")

    # Encomenda
    descricao       = db.Column(db.String(300), default="")
    peso_kg         = db.Column(db.Float, nullable=True)
    valor_frete     = db.Column(db.Float, nullable=False, default=0.0)
    valor_declarado = db.Column(db.Float, nullable=True)
    forma_pagamento = db.Column(db.String(10), default="dinheiro")
    observacoes     = db.Column(db.String(500), default="")

    # Controle
    status        = db.Column(db.String(15), default="pendente")
    cancelada     = db.Column(db.Boolean, default=False)
    registrada_em = db.Column(db.DateTime, default=datetime.utcnow)
    entregue_em   = db.Column(db.DateTime, nullable=True)
    cancelada_em  = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id, "codigo": self.codigo,
            "viagem_id": self.viagem_id,
            "onibus": (self.onibus.identificador if self.onibus else "") or self.viagem.empresa or "",
            "origem": self.viagem.origem,
            "destino": self.viagem.destino,
            "data_partida": self.viagem.data_partida.isoformat(),
            "operador": self.operador.nome,
            "remetente_nome": self.remetente_nome,
            "remetente_cpf": self.remetente_cpf,
            "remetente_telefone": self.remetente_telefone,
            "remetente_cidade": self.remetente_cidade,
            "destinatario_nome": self.destinatario_nome,
            "destinatario_cpf": self.destinatario_cpf,
            "destinatario_telefone": self.destinatario_telefone,
            "destinatario_cidade": self.destinatario_cidade,
            "descricao": self.descricao,
            "peso_kg": self.peso_kg,
            "valor_frete": self.valor_frete,
            "valor_declarado": self.valor_declarado,
            "forma_pagamento": self.forma_pagamento,
            "observacoes": self.observacoes,
            "status": self.status,
            "cancelada": self.cancelada,
            "registrada_em": self.registrada_em.isoformat(),
            "entregue_em": self.entregue_em.isoformat() if self.entregue_em else None,
        }

    def __repr__(self): return f"<Encomenda {self.codigo}>"


class FeatureFlag(db.Model):
    __tablename__ = "feature_flags"
    id            = db.Column(db.Integer, primary_key=True)
    chave         = db.Column(db.String(50), unique=True, nullable=False)
    ativo         = db.Column(db.Boolean, default=False)
    descricao     = db.Column(db.String(200), default="")
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self): return f"<Feature {self.chave}={'ON' if self.ativo else 'OFF'}>"
