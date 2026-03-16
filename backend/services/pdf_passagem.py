"""
Servico de PDF — Comprovante de Passagem — Luzinete Turismo
Gera PDF A4 com comprovante da passagem para o passageiro.
"""
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas as rl_canvas

from backend.models.models import Passagem

AZUL        = colors.HexColor("#1C3159")
AZUL_LIGHT  = colors.HexColor("#EEF2FA")
AZUL2       = colors.HexColor("#2A4A82")
LARANJA     = colors.HexColor("#E8700A")
CINZA       = colors.HexColor("#4A5568")
CINZA_CLARO = colors.HexColor("#E4E8F0")
PRETO       = colors.HexColor("#1A1F2E")
BRANCO      = colors.white
VERDE       = colors.HexColor("#059669")
VERDE_LIGHT = colors.HexColor("#D1FAE5")


def _s(v, default="—"):
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip()


def _moeda(v):
    try:
        return "R$ {:.2f}".format(float(v)).replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def _linha(c, x1, y1, x2, y2, cor=None, esp=0.4):
    c.setStrokeColor(cor or CINZA_CLARO)
    c.setLineWidth(esp)
    c.line(x1, y1, x2, y2)


def _logo_lz(c, x, y, size=12*mm):
    c.setFillColor(LARANJA)
    c.roundRect(x, y, size, size, 3, fill=1, stroke=0)
    c.setFillColor(BRANCO)
    c.setFont("Helvetica-Bold", size * 0.42)
    c.drawCentredString(x + size/2, y + size * 0.27, "LZ")


def _campo(c, x, y, w, label, valor, label_size=5.5, valor_size=9):
    c.setFillColor(CINZA)
    c.setFont("Helvetica", label_size)
    c.drawString(x, y, label.upper())
    c.setFillColor(PRETO)
    c.setFont("Helvetica-Bold", valor_size)
    max_chars = max(8, int(w / (valor_size * 0.52)))
    txt = valor if len(valor) <= max_chars else valor[:max_chars - 1] + "…"
    c.drawString(x, y - 4*mm, txt)
    _linha(c, x, y - 6*mm, x + w - 2*mm, y - 6*mm)
    return 8.5*mm


def gerar_comprovante_pdf(passagem: Passagem) -> io.BytesIO:
    buf = io.BytesIO()
    W, H = A4
    c = rl_canvas.Canvas(buf, pagesize=A4)

    MX = 14*mm
    MY = 14*mm
    CW = W - 2*MX

    # ── CABECALHO ────────────────────────────────────────────
    hh = 26*mm
    hy = H - MY - hh

    c.setFillColor(AZUL)
    c.roundRect(MX, hy, CW, hh, 4, fill=1, stroke=0)
    c.rect(MX, hy, CW, 4, fill=1, stroke=0)

    ls = 16*mm
    _logo_lz(c, MX + 6*mm, hy + (hh - ls)/2, ls)

    c.setFillColor(BRANCO)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(MX + ls + 10*mm, hy + hh*0.58, "Luzinete Turismo")
    c.setFillColor(colors.HexColor("#7A9FD4"))
    c.setFont("Helvetica", 8.5)
    c.drawString(MX + ls + 10*mm, hy + hh*0.32, "Comprovante de Passagem")

    # Codigo no header
    cx = MX + CW - 54*mm
    cy = hy + 6*mm
    c.setFillColor(LARANJA)
    c.roundRect(cx, cy, 48*mm, 15*mm, 3, fill=1, stroke=0)
    c.setFillColor(BRANCO)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(cx + 24*mm, cy + 10.5*mm, "CODIGO DA PASSAGEM")
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(cx + 24*mm, cy + 4*mm, _s(passagem.codigo))

    # ── POLTRONA DESTAQUE ────────────────────────────────────
    rh = 20*mm
    ry = hy - rh

    c.setFillColor(AZUL_LIGHT)
    c.rect(MX, ry, CW, rh, fill=1, stroke=0)

    # Rota
    c.setFillColor(CINZA)
    c.setFont("Helvetica", 6.5)
    c.drawString(MX + 8*mm, ry + 15*mm, "ORIGEM")
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(MX + 8*mm, ry + 8*mm, _s(passagem.viagem.origem).upper())

    c.setFillColor(LARANJA)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(MX + CW/2, ry + 8*mm, "\u2192")

    c.setFillColor(CINZA)
    c.setFont("Helvetica", 6.5)
    c.drawRightString(MX + CW - 54*mm, ry + 15*mm, "DESTINO")
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(MX + CW - 54*mm, ry + 8*mm, _s(passagem.viagem.destino).upper())

    # Poltrona — caixa laranja grande
    pol_w = 48*mm
    pol_x = MX + CW - pol_w
    c.setFillColor(AZUL)
    c.rect(pol_x, ry, pol_w, rh, fill=1, stroke=0)
    c.setFillColor(LARANJA)
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(pol_x + pol_w/2, ry + 14*mm, "POLTRONA")
    c.setFillColor(BRANCO)
    c.setFont("Helvetica-Bold", 24)
    _pol_txt = str(passagem.numero_poltrona) if passagem.numero_poltrona is not None else "?"
    c.drawCentredString(pol_x + pol_w/2, ry + 5*mm, _pol_txt)

    # ── DADOS DO PASSAGEIRO ──────────────────────────────────
    body_y = ry - 5*mm

    # Bloco passageiro
    c.setFillColor(AZUL)
    c.roundRect(MX, body_y - 8.5*mm, CW, 8.5*mm, 2, fill=1, stroke=0)
    c.rect(MX, body_y - 8.5*mm, CW, 3, fill=1, stroke=0)
    c.setFillColor(BRANCO)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(MX + 4*mm, body_y - 5.5*mm, "\u2726  PASSAGEIRO")

    body_y -= 8.5*mm

    # Borda campos passageiro
    pax_h = 28*mm
    c.setStrokeColor(CINZA_CLARO)
    c.setLineWidth(0.4)
    c.roundRect(MX, body_y - pax_h, CW, pax_h, 2, fill=0, stroke=1)

    body_y -= 4*mm
    dx = MX + 4*mm

    # Nome (largura total)
    _campo(c, dx, body_y, CW - 8*mm, "Nome", _s(passagem.passageiro_nome), valor_size=10)
    body_y -= 10*mm

    # CPF | Telefone | Tipo | Pagamento
    col4 = (CW - 8*mm) / 4
    _campo(c, dx,                   body_y, col4, "CPF",       _s(passagem.passageiro_cpf))
    _campo(c, dx + col4,            body_y, col4, "Telefone",  _s(passagem.passageiro_telefone))
    _campo(c, dx + col4*2,          body_y, col4, "Tipo",      passagem.tipo_passagem.capitalize())
    _campo(c, dx + col4*3,          body_y, col4, "Pagamento", passagem.forma_pagamento.capitalize())
    body_y -= 9*mm + 4*mm

    # ── DADOS DA VIAGEM ──────────────────────────────────────
    c.setFillColor(AZUL)
    c.roundRect(MX, body_y - 8.5*mm, CW, 8.5*mm, 2, fill=1, stroke=0)
    c.rect(MX, body_y - 8.5*mm, CW, 3, fill=1, stroke=0)
    c.setFillColor(BRANCO)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(MX + 4*mm, body_y - 5.5*mm, "\u2726  DADOS DA VIAGEM")
    body_y -= 8.5*mm

    viag_h = 28*mm
    c.setStrokeColor(CINZA_CLARO)
    c.setLineWidth(0.4)
    c.roundRect(MX, body_y - viag_h, CW, viag_h, 2, fill=0, stroke=1)

    body_y -= 4*mm

    try:
        dt_partida = passagem.viagem.data_partida.strftime("%d/%m/%Y  %H:%M")
    except Exception:
        dt_partida = "—"
    try:
        dt_retorno = passagem.viagem.data_retorno.strftime("%d/%m/%Y  %H:%M") if passagem.viagem.data_retorno else "Somente ida"
    except Exception:
        dt_retorno = "—"

    col3 = (CW - 8*mm) / 3
    _empresa = passagem.viagem.empresa or (passagem.viagem.onibus.identificador if passagem.viagem.onibus else "")
    _placa   = passagem.viagem.onibus.placa if passagem.viagem.onibus else ""
    _campo(c, dx,           body_y, col3, "Empresa/Onibus", _s(_empresa) + (" — " + _s(_placa) if _placa else ""))
    _campo(c, dx + col3,    body_y, col3, "Data partida", dt_partida)
    _campo(c, dx + col3*2,  body_y, col3, "Retorno",      dt_retorno)
    body_y -= 9*mm + 2*mm

    col2 = (CW - 8*mm) / 2
    # Mostra desconto se houver
    _v_orig = passagem.valor_original or passagem.valor_pago
    _v_pago = passagem.valor_pago
    _desc   = _v_orig - _v_pago
    if _desc > 0.005:
        _valor_label = "Valor c/ desconto"
        # Mostra valor original riscado + desconto
        _campo(c, dx, body_y, col2 * 0.5, "Valor original", _moeda(_v_orig))
        _campo(c, dx + col2 * 0.5, body_y, col2 * 0.5, "Desconto", "- " + _moeda(_desc))
        _campo(c, dx + col2, body_y, col2, "Valor pago", _moeda(_v_pago))
    else:
        _campo(c, dx, body_y, col2, "Valor pago", _moeda(_v_pago))
    _campo(c, dx + col2 + (col2 if _desc > 0.005 else 0), body_y, col2, "Operador", _s(passagem.operador.nome))
    body_y -= 9*mm + 4*mm

    # ── VALIDADE / AVISO ─────────────────────────────────────
    av_h = 14*mm
    c.setFillColor(VERDE_LIGHT)
    c.setStrokeColor(VERDE)
    c.setLineWidth(0.5)
    c.roundRect(MX, body_y - av_h, CW, av_h, 3, fill=1, stroke=1)
    c.setFillColor(VERDE)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(MX + 5*mm, body_y - 5.5*mm, "PASSAGEM VALIDA")
    c.setFont("Helvetica", 7.5)
    c.setFillColor(colors.HexColor("#065F46"))
    c.drawString(MX + 5*mm, body_y - 10.5*mm,
        "Apresente este comprovante ao embarcar. Chegue com 30 minutos de antecedencia.")
    body_y -= av_h + 6*mm

    # ── LINHA PICOTADA ───────────────────────────────────────
    picote_y = MY + 34*mm
    c.setStrokeColor(CINZA_CLARO)
    c.setLineWidth(0.5)
    c.setDash(4, 4)
    c.line(MX + 8*mm, picote_y, MX + CW - 8*mm, picote_y)
    c.setDash()
    c.setFillColor(CINZA)
    c.setFont("Helvetica", 7)
    c.drawCentredString(MX + CW/2, picote_y + 1.5*mm, "\u2702  VIA DA EMPRESA")

    # ── VIA DA EMPRESA (mini) ────────────────────────────────
    rec_y = picote_y - 3*mm

    c.setFillColor(AZUL)
    c.rect(MX, rec_y - 10*mm, CW, 10*mm, fill=1, stroke=0)
    _logo_lz(c, MX + 4*mm, rec_y - 9*mm, 7*mm)
    c.setFillColor(BRANCO)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(MX + 13*mm, rec_y - 5.5*mm, "Luzinete Turismo  —  Via da Empresa")
    c.setFillColor(LARANJA)
    c.roundRect(MX + CW - 52*mm, rec_y - 9*mm, 46*mm, 8*mm, 2, fill=1, stroke=0)
    c.setFillColor(BRANCO)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(MX + CW - 29*mm, rec_y - 5.5*mm, _s(passagem.codigo))

    mini_y = rec_y - 13*mm
    mini_campos = [
        ("Passageiro",  _s(passagem.passageiro_nome)),
        ("Poltrona",    str(passagem.numero_poltrona) if passagem.numero_poltrona is not None else "A definir"),
        ("Trecho",      "{} -> {}".format(_s(passagem.viagem.origem), _s(passagem.viagem.destino))),
        ("Data",        passagem.viagem.data_partida.strftime("%d/%m/%Y") if passagem.viagem.data_partida else "—"),
        ("Valor",       _moeda(passagem.valor_pago)),
    ]
    col_mini = CW / len(mini_campos)
    for i, (label, valor) in enumerate(mini_campos):
        rx = MX + i * col_mini
        c.setFillColor(CINZA)
        c.setFont("Helvetica", 6)
        c.drawString(rx + 3*mm, mini_y + 1*mm, label.upper())
        c.setFillColor(PRETO)
        c.setFont("Helvetica-Bold", 7.5)
        txt = valor[:18] if len(valor) > 18 else valor
        c.drawString(rx + 3*mm, mini_y - 3.5*mm, txt)

    # Emissao
    ass_y = MY + 6*mm
    c.setStrokeColor(CINZA_CLARO)
    c.setLineWidth(0.5)
    c.line(MX + 8*mm, ass_y, MX + 72*mm, ass_y)
    c.setFillColor(CINZA)
    c.setFont("Helvetica", 6.5)
    c.drawString(MX + 8*mm, ass_y - 3.5*mm, "Assinatura do passageiro")
    c.drawRightString(MX + CW - 4*mm, ass_y - 3.5*mm,
                      datetime.now().strftime("Emitido em %d/%m/%Y as %H:%M"))

    c.save()
    buf.seek(0)
    return buf
