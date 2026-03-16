"""
Serviço de Encomendas — Luzinete Turismo
Gerencia registro, atualização de status e histórico de encomendas.
"""
from datetime import datetime
from backend.models.models import db, Encomenda, Viagem


def gerar_codigo() -> str:
    """Gera codigo unico no formato ENC-AAAA-NNNNN."""
    ano = datetime.utcnow().year
    ultima = (
        Encomenda.query
        .filter(Encomenda.codigo.like(f"ENC-{ano}-%"))
        .order_by(Encomenda.id.desc())
        .with_for_update()
        .first()
    )
    numero = int(ultima.codigo.split("-")[-1]) + 1 if ultima else 1
    return f"ENC-{ano}-{numero:05d}"


def registrar(
    viagem_id: int,
    onibus_id: int,
    operador_id: int,
    remetente_nome: str,
    remetente_cpf: str,
    remetente_telefone: str,
    remetente_cidade: str,
    destinatario_nome: str,
    destinatario_cpf: str,
    destinatario_telefone: str,
    destinatario_cidade: str,
    descricao: str,
    peso_kg: float | None,
    valor_frete: float,
    valor_declarado: float | None,
    forma_pagamento: str,
    observacoes: str,
) -> tuple[bool, str, Encomenda | None]:
    """Registra uma nova encomenda. Retorna (sucesso, mensagem, encomenda)."""

    viagem = db.session.get(Viagem, viagem_id)
    if not viagem or viagem.status != "aberta":
        return False, "Viagem não encontrada ou encerrada.", None

    if not remetente_nome.strip():
        return False, "Nome do remetente é obrigatório.", None

    if not destinatario_nome.strip():
        return False, "Nome do destinatário é obrigatório.", None

    enc = Encomenda(
        codigo=gerar_codigo(),
        viagem_id=viagem_id,
        onibus_id=onibus_id,
        operador_id=operador_id,
        remetente_nome=remetente_nome.strip(),
        remetente_cpf=remetente_cpf,
        remetente_telefone=remetente_telefone,
        remetente_cidade=remetente_cidade,
        destinatario_nome=destinatario_nome.strip(),
        destinatario_cpf=destinatario_cpf,
        destinatario_telefone=destinatario_telefone,
        destinatario_cidade=destinatario_cidade,
        descricao=descricao,
        peso_kg=peso_kg,
        valor_frete=valor_frete,
        valor_declarado=valor_declarado,
        forma_pagamento=forma_pagamento,
        observacoes=observacoes,
        status="pendente",
    )
    db.session.add(enc)
    db.session.commit()
    return True, "Encomenda registrada com sucesso.", enc


def atualizar_status(encomenda_id: int, novo_status: str) -> tuple[bool, str]:
    """Atualiza o status de uma encomenda."""
    VALIDOS = {"pendente", "em_transito", "entregue", "devolvida", "extraviada"}
    if novo_status not in VALIDOS:
        return False, f"Status inválido. Use: {', '.join(VALIDOS)}"

    enc = db.session.get(Encomenda, encomenda_id)
    if not enc:
        return False, "Encomenda não encontrada."
    if enc.cancelada:
        return False, "Encomenda cancelada."

    enc.status = novo_status
    if novo_status == "entregue":
        enc.entregue_em = datetime.utcnow()
    db.session.commit()
    return True, f"Status atualizado para '{novo_status}'."


def cancelar(encomenda_id: int) -> tuple[bool, str]:
    """Cancela uma encomenda."""
    enc = db.session.get(Encomenda, encomenda_id)
    if not enc:
        return False, "Encomenda não encontrada."
    if enc.cancelada:
        return False, "Encomenda já cancelada."
    enc.cancelada = True
    enc.status = "cancelada"
    enc.cancelada_em = datetime.utcnow()
    db.session.commit()
    return True, "Encomenda cancelada."


def historico_viagem(viagem_id: int) -> list[Encomenda]:
    return (
        Encomenda.query
        .filter_by(viagem_id=viagem_id)
        .order_by(Encomenda.registrada_em.desc())
        .all()
    )


def historico_onibus(onibus_id: int) -> list[dict]:
    from backend.models.models import Viagem
    viagens = (
        Viagem.query
        .filter_by(onibus_id=onibus_id)
        .order_by(Viagem.data_partida.desc())
        .all()
    )
    resultado = []
    for v in viagens:
        encs = historico_viagem(v.id)
        ativas = [e for e in encs if not e.cancelada]
        resultado.append({
            "viagem": v.to_dict(),
            "encomendas": [e.to_dict() for e in encs],
            "total_ativas": len(ativas),
            "receita_frete": sum(e.valor_frete for e in ativas),
        })
    return resultado


def buscar(q: str, limit: int = 20) -> list[Encomenda]:
    return (
        Encomenda.query
        .filter(
            (Encomenda.codigo.ilike(f"%{q}%")) |
            (Encomenda.remetente_nome.ilike(f"%{q}%")) |
            (Encomenda.destinatario_nome.ilike(f"%{q}%")) |
            (Encomenda.remetente_cpf.ilike(f"%{q}%")) |
            (Encomenda.destinatario_cpf.ilike(f"%{q}%"))
        )
        .order_by(Encomenda.registrada_em.desc())
        .limit(limit)
        .all()
    )
