"""
Servico WhatsApp — Z-API, Twilio ou link wa.me (sem API).
"""
import requests
from flask import current_app
from backend.models.models import db, Passagem
from backend.services.feature_flags import is_enabled


def _mensagem(p: Passagem) -> str:
    v = p.viagem
    data = v.data_partida.strftime("%d/%m/%Y as %H:%M")
    msg = (
        f"Luzinete Turismo\n\n"
        f"Ola, {p.passageiro_nome}! Sua passagem foi emitida.\n\n"
        f"Codigo: {p.codigo}\n"
        f"Poltrona: {p.numero_poltrona}\n"
        f"Trecho: {v.origem} -> {v.destino}\n"
        f"Data: {data}\n"
        f"Empresa: {v.empresa or (v.onibus.identificador if v.onibus else "")}\n"
    )
    if v.data_retorno:
        msg += f"Retorno: {v.data_retorno.strftime('%d/%m/%Y as %H:%M')}\n"
    msg += f"Valor: R$ {p.valor_pago:.2f} ({p.forma_pagamento})\n\nBoa viagem!"
    return msg


def _normalizar_tel(telefone: str) -> str:
    """Remove tudo que nao e digito e garante DDI 55 do Brasil."""
    numero = "".join(filter(str.isdigit, telefone))
    if not numero.startswith("55"):
        numero = "55" + numero
    return numero


def _wame(telefone: str, mensagem: str) -> tuple[bool, str]:
    """
    Gera link wa.me e retorna como 'info' para o frontend abrir.
    Nao envia automaticamente — o operador clica e confirma no WhatsApp.
    """
    import urllib.parse
    numero = _normalizar_tel(telefone)
    link = f"https://wa.me/{numero}?text={urllib.parse.quote(mensagem)}"
    # Retorna o link como info para o frontend redirecionar
    return True, link


def _zapi(telefone: str, mensagem: str) -> tuple[bool, str]:
    cfg = current_app.config
    numero = _normalizar_tel(telefone)
    url = (
        f"https://api.z-api.io/instances/{cfg['ZAPI_INSTANCE']}"
        f"/token/{cfg['ZAPI_TOKEN']}/send-text"
    )
    try:
        r = requests.post(url, json={"phone": numero, "message": mensagem}, timeout=10)
        r.raise_for_status()
        return True, "Enviado via Z-API"
    except Exception as e:
        return False, str(e)


def _twilio(telefone: str, mensagem: str) -> tuple[bool, str]:
    from twilio.rest import Client
    cfg = current_app.config
    try:
        c = Client(cfg["TWILIO_SID"], cfg["TWILIO_TOKEN"])
        c.messages.create(
            body=mensagem,
            from_=f"whatsapp:{cfg['TWILIO_PHONE']}",
            to=f"whatsapp:{telefone}"
        )
        return True, "Enviado via Twilio"
    except Exception as e:
        return False, str(e)


def enviar(passagem_id: int) -> tuple[bool, str]:
    if not is_enabled("whatsapp"):
        return False, "WhatsApp desativado."
    p = db.session.get(Passagem, passagem_id)
    if not p:
        return False, "Passagem nao encontrada."
    tel = p.passageiro_whatsapp or p.passageiro_telefone
    if not tel:
        return False, "Sem numero de WhatsApp."

    msg = _mensagem(p)
    provider = current_app.config.get("WHATSAPP_PROVIDER", "wame")

    if provider == "twilio":
        ok, info = _twilio(tel, msg)
    elif provider == "zapi":
        ok, info = _zapi(tel, msg)
    else:  # wame — padrao, sem configuracao necessaria
        ok, info = _wame(tel, msg)

    if ok and provider != "wame":
        p.whatsapp_enviado = True
        db.session.commit()

    return ok, info


def gerar_link_wame(passagem_id: int) -> tuple[bool, str]:
    """Gera link wa.me diretamente, independente do provider configurado."""
    import urllib.parse
    p = db.session.get(Passagem, passagem_id)
    if not p:
        return False, "Passagem nao encontrada."
    tel = p.passageiro_whatsapp or p.passageiro_telefone
    if not tel:
        return False, "Sem numero de WhatsApp."
    msg = _mensagem(p)
    numero = _normalizar_tel(tel)
    link = f"https://wa.me/{numero}?text={urllib.parse.quote(msg)}"
    return True, link
