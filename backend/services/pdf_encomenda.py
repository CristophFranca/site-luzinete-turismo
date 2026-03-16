"""
Servico de PDF — Etiqueta de Encomenda — Luzinete Turismo
Layout A4 sem QR Code, dados bem espacados.
"""
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas as rl_canvas

from backend.models.models import Encomenda

AZUL        = colors.HexColor("#1C3159")
AZUL_LIGHT  = colors.HexColor("#EEF2FA")
LARANJA     = colors.HexColor("#E8700A")
CINZA       = colors.HexColor("#4A5568")
CINZA_CLARO = colors.HexColor("#E4E8F0")
PRETO       = colors.HexColor("#1A1F2E")
BRANCO      = colors.white
AMARELO_BG  = colors.HexColor("#FFFBEB")
AMARELO_BD  = colors.HexColor("#FDE68A")
AMARELO_TX  = colors.HexColor("#92400E")


def _s(v, default="—"):
    """Valor seguro como string."""
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
    c.drawCentredString(x + size / 2, y + size * 0.27, "LZ")


def _campo(c, x, y, w, label, valor, label_size=5.5, valor_size=9):
    """Desenha label + valor + linha separadora. Retorna altura consumida."""
    c.setFillColor(CINZA)
    c.setFont("Helvetica", label_size)
    c.drawString(x, y, label.upper())
    
    # Truncar valor se muito longo para a coluna
    c.setFillColor(PRETO)
    c.setFont("Helvetica-Bold", valor_size)
    max_chars = int(w / (valor_size * 0.52))
    txt = valor if len(valor) <= max_chars else valor[:max_chars - 1] + "…"
    c.drawString(x, y - 4*mm, txt)
    
    _linha(c, x, y - 6*mm, x + w - 2*mm, y - 6*mm)
    return 8.5*mm


def _bloco_titulo(c, x, y, w, titulo):
    """Faixa azul com titulo. Retorna altura da faixa."""
    fh = 8.5*mm
    c.setFillColor(AZUL)
    c.roundRect(x, y - fh, w, fh, 2, fill=1, stroke=0)
    c.rect(x, y - fh, w, 3, fill=1, stroke=0)
    c.setFillColor(BRANCO)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(x + 4*mm, y - 5.5*mm, titulo)
    return fh


def _bloco_pessoa(c, x, y, w, titulo, nome, cpf, tel, cidade):
    """Bloco completo de remetente/destinatario. Retorna altura total usada."""
    cur = y
    fh = _bloco_titulo(c, x, cur, w, titulo)
    cur -= fh

    # Borda ao redor dos campos
    campos_h = 38*mm
    c.setStrokeColor(CINZA_CLARO)
    c.setLineWidth(0.4)
    c.roundRect(x, cur - campos_h, w, campos_h, 2, fill=0, stroke=1)

    cur -= 4*mm
    dx = x + 4*mm
    dw = w - 8*mm

    cur -= _campo(c, dx, cur, dw, "Nome", _s(nome))
    cur -= 2*mm
    # CPF e Telefone lado a lado
    half = dw / 2 - 2*mm
    _campo(c, dx,          cur, half, "CPF",      _s(cpf))
    _campo(c, dx + half + 4*mm, cur, half, "Telefone", _s(tel))
    cur -= 8.5*mm + 2*mm
    cur -= _campo(c, dx, cur, dw, "Cidade", _s(cidade))

    return y - (cur - 2*mm)


def _bloco_dados(c, x, y, w, enc):
    """Bloco de dados da encomenda. Retorna altura total usada."""
    cur = y
    fh = _bloco_titulo(c, x, cur, w, "\u2726  DADOS DA ENCOMENDA")
    cur -= fh

    try:
        dt_str = enc.viagem.data_partida.strftime("%d/%m/%Y %H:%M")
    except Exception:
        dt_str = "—"

    campos_h = 62*mm
    c.setStrokeColor(CINZA_CLARO)
    c.setLineWidth(0.4)
    c.roundRect(x, cur - campos_h, w, campos_h, 2, fill=0, stroke=1)

    cur -= 4*mm
    dx = x + 4*mm
    dw = w - 8*mm

    _onibus_id  = enc.onibus.identificador if enc.onibus else (enc.viagem.empresa or "")
    onibus_data = "{} · {}".format(_s(_onibus_id), dt_str)
    cur -= _campo(c, dx, cur, dw, "Onibus / Data", onibus_data)
    cur -= 2*mm

    desc = _s(enc.descricao)
    cur -= _campo(c, dx, cur, dw, "Descricao", desc, valor_size=8.5)
    cur -= 2*mm

    peso_str = "{:.1f} kg".format(float(enc.peso_kg)).replace(".", ",") if enc.peso_kg else "—"
    cur -= _campo(c, dx, cur, dw, "Peso", peso_str)
    cur -= 2*mm

    frete_str = "{} ({})".format(_moeda(enc.valor_frete), _s(enc.forma_pagamento))
    cur -= _campo(c, dx, cur, dw, "Frete", frete_str)
    cur -= 2*mm

    decl_str = _moeda(enc.valor_declarado) if enc.valor_declarado else "—"
    cur -= _campo(c, dx, cur, dw, "Valor Declarado", decl_str)
    cur -= 2*mm

    cur -= _campo(c, dx, cur, dw, "Operador", _s(enc.operador.nome))

    return y - (cur - 2*mm)


def gerar_etiqueta_pdf(encomenda: Encomenda) -> io.BytesIO:
    buf = io.BytesIO()
    W, H = A4
    c = rl_canvas.Canvas(buf, pagesize=A4)

    MX = 14*mm
    MY = 14*mm
    CW = W - 2*MX
    CH = H - 2*MY

    # Borda externa
    c.setStrokeColor(CINZA_CLARO)
    c.setLineWidth(0.6)
    c.roundRect(MX, MY, CW, CH, 4, fill=0, stroke=1)

    # ── CABECALHO ────────────────────────────────────────────
    hh = 26*mm
    hy = MY + CH - hh

    c.setFillColor(AZUL)
    c.roundRect(MX, hy, CW, hh, 4, fill=1, stroke=0)
    c.rect(MX, hy, CW, 4, fill=1, stroke=0)

    ls = 16*mm
    _logo_lz(c, MX + 6*mm, hy + (hh - ls) / 2, ls)

    c.setFillColor(BRANCO)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(MX + ls + 10*mm, hy + hh * 0.58, "Luzinete Turismo")
    c.setFillColor(colors.HexColor("#7A9FD4"))
    c.setFont("Helvetica", 8.5)
    c.drawString(MX + ls + 10*mm, hy + hh * 0.32, "Transporte de Encomendas")

    # Codigo no header
    cx = MX + CW - 54*mm
    cy = hy + 6*mm
    c.setFillColor(LARANJA)
    c.roundRect(cx, cy, 48*mm, 15*mm, 3, fill=1, stroke=0)
    c.setFillColor(BRANCO)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(cx + 24*mm, cy + 10.5*mm, "CODIGO DE RASTREIO")
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(cx + 24*mm, cy + 4*mm, _s(encomenda.codigo))

    # ── BARRA DE ROTA ────────────────────────────────────────
    rh = 14*mm
    ry = hy - rh

    c.setFillColor(AZUL_LIGHT)
    c.rect(MX, ry, CW, rh, fill=1, stroke=0)

    c.setFillColor(CINZA)
    c.setFont("Helvetica", 6.5)
    c.drawString(MX + 8*mm, ry + 9.5*mm, "ORIGEM")
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MX + 8*mm, ry + 3.5*mm, _s(encomenda.viagem.origem).upper())

    c.setFillColor(LARANJA)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(MX + CW / 2, ry + 3.5*mm, "\u2192")

    c.setFillColor(CINZA)
    c.setFont("Helvetica", 6.5)
    c.drawRightString(MX + CW - 8*mm, ry + 9.5*mm, "DESTINO")
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(MX + CW - 8*mm, ry + 3.5*mm, _s(encomenda.viagem.destino).upper())

    # ── CORPO: 2 colunas ────────────────────────────────────
    gap   = 5*mm
    col_w = (CW - gap) / 2
    CX_L  = MX
    CX_R  = MX + col_w + gap
    top_y = ry - 5*mm

    # Coluna esquerda: remetente
    h1 = _bloco_pessoa(c, CX_L, top_y, col_w,
                       "\u2726  REMETENTE",
                       encomenda.remetente_nome,
                       encomenda.remetente_cpf,
                       encomenda.remetente_telefone,
                       encomenda.remetente_cidade)

    # Coluna esquerda: destinatario
    h2 = _bloco_pessoa(c, CX_L, top_y - h1 - 5*mm, col_w,
                       "\u2726  DESTINATARIO",
                       encomenda.destinatario_nome,
                       encomenda.destinatario_cpf,
                       encomenda.destinatario_telefone,
                       encomenda.destinatario_cidade)

    # Coluna direita: dados da encomenda (ocupa altura de remetente + destinatario)
    _bloco_dados(c, CX_R, top_y, col_w, encomenda)

    # ── OBSERVACOES ─────────────────────────────────────────
    obs_bottom = top_y - h1 - h2 - 10*mm
    if encomenda.observacoes and encomenda.observacoes.strip():
        obs_h = 16*mm
        c.setFillColor(AMARELO_BG)
        c.setStrokeColor(AMARELO_BD)
        c.setLineWidth(0.5)
        c.roundRect(MX, obs_bottom - obs_h, CW, obs_h, 3, fill=1, stroke=1)
        c.setFillColor(AMARELO_TX)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(MX + 5*mm, obs_bottom - 5.5*mm, "OBSERVACOES")
        c.setFont("Helvetica", 8.5)
        obs_txt = encomenda.observacoes[:120]
        c.drawString(MX + 5*mm, obs_bottom - 11*mm, obs_txt)
        obs_bottom -= obs_h + 4*mm

    # ── LINHA PICOTADA ───────────────────────────────────────
    picote_y = MY + 42*mm
    c.setStrokeColor(CINZA_CLARO)
    c.setLineWidth(0.5)
    c.setDash(4, 4)
    c.line(MX + 8*mm, picote_y, MX + CW - 8*mm, picote_y)
    c.setDash()
    c.setFillColor(CINZA)
    c.setFont("Helvetica", 7)
    c.drawCentredString(MX + CW / 2, picote_y + 1.5*mm, "✂  RECIBO")

    # ── RECIBO ───────────────────────────────────────────────
    rec_y = picote_y - 2*mm

    c.setFillColor(AZUL)
    c.rect(MX, rec_y - 10*mm, CW, 10*mm, fill=1, stroke=0)
    _logo_lz(c, MX + 4*mm, rec_y - 9*mm, 7*mm)
    c.setFillColor(BRANCO)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(MX + 13*mm, rec_y - 5.5*mm, "Luzinete Turismo  —  Recibo de Encomenda")

    c.setFillColor(LARANJA)
    c.roundRect(MX + CW - 52*mm, rec_y - 9*mm, 46*mm, 8*mm, 2, fill=1, stroke=0)
    c.setFillColor(BRANCO)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(MX + CW - 29*mm, rec_y - 5.5*mm, _s(encomenda.codigo))

    campos_rec = [
        ("Remetente",    _s(encomenda.remetente_nome)),
        ("Destinatario", _s(encomenda.destinatario_nome)),
        ("Trecho",       "{} -> {}".format(_s(encomenda.viagem.origem), _s(encomenda.viagem.destino))),
        ("Data",         encomenda.viagem.data_partida.strftime("%d/%m/%Y") if encomenda.viagem.data_partida else "—"),
        ("Frete",        _moeda(encomenda.valor_frete)),
    ]
    rec_data_y = rec_y - 15*mm
    col_rec = CW / len(campos_rec)
    for i, (label, valor) in enumerate(campos_rec):
        rx = MX + i * col_rec
        c.setFillColor(CINZA)
        c.setFont("Helvetica", 6)
        c.drawString(rx + 3*mm, rec_data_y + 1*mm, label.upper())
        c.setFillColor(PRETO)
        c.setFont("Helvetica-Bold", 7.5)
        txt = valor[:20] if len(valor) > 20 else valor
        c.drawString(rx + 3*mm, rec_data_y - 3.5*mm, txt)

    ass_y = MY + 6*mm
    c.setStrokeColor(CINZA_CLARO)
    c.setLineWidth(0.5)
    c.line(MX + 8*mm, ass_y, MX + 72*mm, ass_y)
    c.setFillColor(CINZA)
    c.setFont("Helvetica", 6.5)
    c.drawString(MX + 8*mm, ass_y - 3.5*mm, "Assinatura do destinatario")
    c.drawRightString(MX + CW - 4*mm, ass_y - 3.5*mm,
                      datetime.now().strftime("Emitido em %d/%m/%Y as %H:%M"))

    c.save()
    buf.seek(0)
    return buf
