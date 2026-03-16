"""
Serviço de Passagens — emissão, cancelamento, histórico e validação de poltrona.
"""
from datetime import datetime
from backend.models.models import db, Passagem, Viagem


def gerar_codigo() -> str:
    """Gera codigo unico. Usa FOR UPDATE para evitar duplicatas em concorrencia."""
    ano = datetime.utcnow().year
    ultima = (
        Passagem.query
        .filter(Passagem.codigo.like(f"LZ-{ano}-%"))
        .order_by(Passagem.id.desc())
        .with_for_update()
        .first()
    )
    numero = int(ultima.codigo.split("-")[-1]) + 1 if ultima else 1
    return f"LZ-{ano}-{numero:05d}"


def poltrona_disponivel(viagem_id: int, numero: int) -> bool:
    return not Passagem.query.filter_by(
        viagem_id=viagem_id, numero_poltrona=numero, cancelada=False
    ).first()


def poltronas_ocupadas(viagem_id: int) -> list[int]:
    rows = (
        Passagem.query
        .filter_by(viagem_id=viagem_id, cancelada=False)
        .with_entities(Passagem.numero_poltrona)
        .all()
    )
    return [r.numero_poltrona for r in rows]


def emitir(
    viagem_id: int, operador_id: int, numero_poltrona: int | None,
    passageiro_nome: str, passageiro_cpf: str,
    passageiro_telefone: str, passageiro_whatsapp: str,
    tipo_passagem: str, valor_pago: float, forma_pagamento: str,
    valor_original: float | None = None,
) -> tuple[bool, str, Passagem | None]:

    # Verifica disponibilidade apenas se poltrona foi definida
    if numero_poltrona is not None and not poltrona_disponivel(viagem_id, numero_poltrona):
        return False, f"Poltrona {numero_poltrona} ja esta ocupada.", None

    viagem = db.session.get(Viagem, viagem_id)
    if not viagem or viagem.status != "aberta":
        return False, "Viagem não encontrada ou encerrada.", None

    p = Passagem(
        codigo=gerar_codigo(),
        viagem_id=viagem_id,
        operador_id=operador_id,
        numero_poltrona=numero_poltrona,
        passageiro_nome=passageiro_nome,
        passageiro_cpf=passageiro_cpf,
        passageiro_telefone=passageiro_telefone,
        passageiro_whatsapp=passageiro_whatsapp,
        tipo_passagem=tipo_passagem,
        valor_pago=valor_pago,
        valor_original=valor_original if valor_original is not None else valor_pago,
        forma_pagamento=forma_pagamento,
    )
    db.session.add(p)
    db.session.commit()
    return True, "Passagem emitida com sucesso.", p


def cancelar(passagem_id: int) -> tuple[bool, str]:
    p = db.session.get(Passagem, passagem_id)
    if not p:
        return False, "Passagem não encontrada."
    if p.cancelada:
        return False, "Passagem já cancelada."
    p.cancelada = True
    p.cancelada_em = datetime.utcnow()
    db.session.commit()
    return True, "Passagem cancelada."


def historico_viagem(viagem_id: int) -> list[Passagem]:
    return (
        Passagem.query
        .filter_by(viagem_id=viagem_id)
        .order_by(Passagem.numero_poltrona)
        .all()
    )


def historico_onibus(onibus_id: int) -> list[dict]:
    viagens = (
        Viagem.query
        .filter_by(onibus_id=onibus_id)
        .order_by(Viagem.data_partida.desc())
        .all()
    )
    resultado = []
    for v in viagens:
        passagens = historico_viagem(v.id)
        ativas = [p for p in passagens if not p.cancelada]
        resultado.append({
            "viagem": v.to_dict(),
            "passagens": [p.to_dict() for p in passagens],
            "total_ativas": len(ativas),
            "receita": sum(p.valor_pago for p in ativas),
        })
    return resultado
