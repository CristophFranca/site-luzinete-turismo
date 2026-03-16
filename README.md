# 🚌 Luzinete Turismo

> Sistema web completo para gestão de passagens e encomendas em empresas de turismo rodoviário.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square)
![Flask](https://img.shields.io/badge/Flask-3.0-lightgrey?style=flat-square)
![SQLite](https://img.shields.io/badge/Banco-SQLite-003B57?style=flat-square)
![Versão](https://img.shields.io/badge/Versão-1.2.0-orange?style=flat-square)
![Licença](https://img.shields.io/badge/Licença-MIT-green?style=flat-square)

---

## ✨ Funcionalidades

- **Emissão de passagens** — mapa visual de poltronas, seleção múltipla, desconto por passageiro (R$ ou %), poltrona "a definir"
- **Gestão de encomendas** — remetente, destinatário, rastreio de status, etiqueta PDF
- **Gestão de viagens** — cadastro direto com empresa/ônibus, origem, destino, data e poltronas
- **Relatório financeiro** — receita por período, breakdown por forma de pagamento, ranking de viagens
- **PDF automático** — comprovante profissional com QR code, dados completos e via da empresa
- **WhatsApp integrado** — link `wa.me` gerado automaticamente, zero API, zero custo
- **Painel Admin** — gerenciamento de usuários, feature flags, backup manual e sistema de updates
- **Atualizações automáticas** — coloque o `.zip` em `/updates`, aplique pelo painel, reinício automático
- **Launcher invisível** — `.vbs` sobe o servidor sem janela no Windows, com monitoramento e auto-reinício

---

## 🖥️ Pré-requisitos

- Windows 10/11 (ou Linux)
- Python 3.10+
- pip

---

## 🚀 Instalação rápida

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/luzinete-turismo.git
cd luzinete-turismo

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Configure o ambiente
cp .env.example .env
# Edite o .env se necessário

# 4. Rode o sistema
python run.py
```

Acesse: **http://localhost:5000**

Login padrão: `admin@luzinete.com.br` / `admin123`

> ⚠️ **Troque a senha do admin** no painel antes de usar em produção.

---

## 🪟 Uso no Windows (modo silencioso)

Coloque o `iniciar_luzinete.vbs` na pasta raiz do projeto (ao lado do `run.py`).

Ao abrir o `.vbs`:
- Instala dependências automaticamente na primeira vez
- Sobe o servidor Flask sem janela visível
- Abre o navegador em `http://localhost:5000`
- Monitora e reinicia automaticamente se o servidor cair

Para iniciar junto com o Windows, crie um atalho do `.vbs` em:
```
Win + R → shell:startup → cole o atalho
```

---

## 🏭 Deploy em produção

```bash
# Instalar gunicorn
pip install -r requirements.txt

# Rodar com gunicorn (recomendado)
gunicorn "backend.app:create_app()" -w 2 -b 0.0.0.0:5000 --timeout 120
```

Gere uma `SECRET_KEY` segura para o `.env`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Veja o `README.md` dentro do projeto para instruções completas com Nginx e systemd.

---

## 🔄 Sistema de atualizações

1. Baixe o arquivo `update_vX.X.X.zip`
2. Coloque dentro da pasta `updates/`
3. Acesse o **Painel Admin → Atualização do sistema**
4. Clique em **"Aplicar atualização agora"**

O sistema faz backup automático do banco, extrai os arquivos e reinicia sozinho. O `.env` e a pasta `database/` nunca são sobrescritos.

---

## 🗂️ Estrutura do projeto

```
luzinete-turismo/
├── backend/
│   ├── api/routes.py          # Endpoints REST
│   ├── app.py                 # Factory Flask + migrações automáticas
│   ├── config/settings.py     # Configurações
│   ├── models/models.py       # SQLAlchemy
│   └── services/              # Lógica de negócio
│       ├── passagens.py
│       ├── encomendas.py
│       ├── pdf_passagem.py
│       ├── pdf_encomenda.py
│       ├── whatsapp.py
│       ├── backup.py
│       ├── feature_flags.py
│       └── update.py
├── frontend/
│   ├── static/                # CSS, JS, imagens
│   └── templates/             # Jinja2 HTML
├── database/                  # SQLite (criado automaticamente)
├── updates/                   # Pasta para arquivos de update
├── .env.example
├── requirements.txt
├── run.py
├── migrate.py
├── version.json
└── iniciar_luzinete.vbs
```

---

## ⚙️ Variáveis de ambiente

Copie `.env.example` para `.env` e ajuste:

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `FLASK_ENV` | `development` ou `production` | `development` |
| `SECRET_KEY` | Chave de sessão (obrigatória em produção) | gerada automaticamente |
| `DATABASE_URL` | URI do banco SQLite | `sqlite:///database/luzinete.db` |
| `WHATSAPP_PROVIDER` | `wame`, `zapi` ou `twilio` | `wame` |
| `PORT` | Porta do servidor | `5000` |
| `BACKUP_INTERVAL_HOURS` | Intervalo do backup automático | `24` |

---

## 📱 WhatsApp

| Provider | Configuração | Comportamento |
|----------|-------------|---------------|
| `wame` *(padrão)* | Nenhuma | Abre WhatsApp com mensagem pronta, operador confirma |
| `zapi` | `ZAPI_INSTANCE` + `ZAPI_TOKEN` | Envio automático |
| `twilio` | `TWILIO_SID` + `TWILIO_TOKEN` + `TWILIO_PHONE` | Envio automático |

---

## 🛡️ Segurança

- Senhas com hash bcrypt
- `SECRET_KEY` gerada dinamicamente se não definida
- Cookies com `HttpOnly` + `SameSite=Lax`
- Rotas admin protegidas por `@admin_required`
- Soft delete de usuários (flag `ativo`)
- Rollback automático em erros de banco
- Open redirect protegido no login

---

## 🔧 Stack técnica

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.10+, Flask 3.0 |
| ORM | SQLAlchemy + Flask-SQLAlchemy |
| Banco | SQLite (zero configuração) |
| Auth | Flask-Login + bcrypt |
| PDF | ReportLab |
| WhatsApp | wa.me (link nativo) |
| Servidor | Gunicorn |
| Frontend | Jinja2 + CSS/JS vanilla |
| Deploy | Windows VBS launcher / Linux systemd |

---

## 📋 Histórico de versões

| Versão | Data | Mudanças |
|--------|------|---------|
| `1.2.0` | Mar 2026 | Desconto na passagem (R$/%), poltrona "a definir" |
| `1.1.5` | Mar 2026 | Correção geral pós-migração empresa/ônibus |
| `1.1.0` | Mar 2026 | Viagem sem ônibus obrigatório, campo empresa |
| `1.0.0` | Mar 2026 | Lançamento inicial |

---

## 📄 Licença

MIT — veja [LICENSE](LICENSE) para detalhes.
