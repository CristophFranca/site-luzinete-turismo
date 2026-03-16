"""
Application Factory — Luzinete Turismo
"""
import logging
from datetime import datetime
from flask import Flask, redirect, render_template, request, session, abort
from flask_login import LoginManager, login_required, current_user, login_user

from backend.config.settings import get_config
from backend.models.models import db, Usuario
from backend.api.routes import registrar
from backend.services.feature_flags import seed_flags


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="../frontend/templates",
        static_folder="../frontend/static",
    )
    app.config.from_object(get_config())

    # Logging em producao
    if not app.debug:
        logging.basicConfig(
            level=logging.WARNING,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )

    db.init_app(app)

    lm = LoginManager(app)
    lm.login_view = "frontend.login_page"
    lm.login_message = ""

    @lm.user_loader
    def load_user(uid):
        try:
            return db.session.get(Usuario, int(uid))
        except Exception:
            return None

    registrar(app)
    _frontend(app)
    _erros(app)

    with app.app_context():
        _init_db(app)

    return app


def _init_db(app):
    # A pasta do banco e criada automaticamente pelo creator em settings.py
    db.create_all()
    _migrar_banco()   # aplica alteracoes de schema sem perder dados
    seed_flags()
    _seed_admin()


def _migrar_banco():
    """
    Migra o banco para v1.1.0:
    - Torna viagens.onibus_id opcional (nullable)
    - Adiciona viagens.empresa e viagens.total_poltronas
    Recria a tabela para contornar limitacao do SQLite com ALTER COLUMN.
    """
    import sqlite3
    import logging
    from backend.config.settings import DB_PATH
    log = logging.getLogger(__name__)

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur  = conn.cursor()
        cur.execute("PRAGMA foreign_keys = OFF")

        # Verifica estado atual
        cur.execute("PRAGMA table_info(viagens)")
        info = {r[1]: r[3] for r in cur.fetchall()}

        ja_tem_empresa   = "empresa" in info
        ja_tem_poltronas = "total_poltronas" in info
        onibus_nullable  = info.get("onibus_id", 1) == 0  # 0 = nullable

        if ja_tem_empresa and ja_tem_poltronas and onibus_nullable:
            conn.close()
            return  # ja migrado

        log.info("Aplicando migracao v1.1.0...")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS viagens_mig (
                id              INTEGER PRIMARY KEY,
                onibus_id       INTEGER REFERENCES onibus(id),
                empresa         VARCHAR(150) DEFAULT '',
                total_poltronas INTEGER DEFAULT 44,
                origem          VARCHAR(100) NOT NULL,
                destino         VARCHAR(100) NOT NULL,
                data_partida    DATETIME NOT NULL,
                data_retorno    DATETIME,
                tipo            VARCHAR(10) DEFAULT 'ida',
                valor_inteiro   FLOAT DEFAULT 0.0,
                valor_meia      FLOAT,
                status          VARCHAR(12) DEFAULT 'aberta',
                criado_em       DATETIME
            )
        """)

        emp_col = "v.empresa" if ja_tem_empresa else "''"
        pol_col = "v.total_poltronas" if ja_tem_poltronas else "NULL"

        cur.execute(f"""
            INSERT INTO viagens_mig
                (id, onibus_id, empresa, total_poltronas, origem, destino,
                 data_partida, data_retorno, tipo, valor_inteiro, valor_meia,
                 status, criado_em)
            SELECT
                v.id, v.onibus_id,
                COALESCE(NULLIF({emp_col}, ''), o.identificador, ''),
                COALESCE({pol_col}, o.total_poltronas, 44),
                v.origem, v.destino, v.data_partida, v.data_retorno,
                v.tipo, v.valor_inteiro, v.valor_meia, v.status, v.criado_em
            FROM viagens v
            LEFT JOIN onibus o ON o.id = v.onibus_id
        """)

        cur.execute("DROP TABLE viagens")
        cur.execute("ALTER TABLE viagens_mig RENAME TO viagens")
        cur.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        conn.close()
        log.info("Migracao v1.1.0 aplicada com sucesso.")
    except Exception as e:
        log.error(f"Erro na migracao: {e}")

    # v1.2.0 — valor_original em passagens (desconto)
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur  = conn.cursor()
        cur.execute("PRAGMA table_info(passagens)")
        cols = [r[1] for r in cur.fetchall()]
        if "valor_original" not in cols:
            cur.execute("ALTER TABLE passagens ADD COLUMN valor_original FLOAT")
            cur.execute("UPDATE passagens SET valor_original = valor_pago WHERE valor_original IS NULL")
            conn.commit()
            log.info("Migracao v1.2.0: valor_original adicionado.")
        conn.close()
    except Exception as e:
        log.error(f"Erro na migracao v1.2.0: {e}")

    # v1.2.1 — numero_poltrona nullable (poltrona a definir)
    # SQLite permite NULL em colunas NOT NULL se recriarmos — mas ALTER funciona para remover NOT NULL indiretamente
    # Na pratica SQLite nao enforça NOT NULL em ALTER, entao apenas garantimos que o INSERT aceita NULL
    # O modelo ja foi atualizado para nullable=True, db.create_all nao altera colunas existentes
    # Para bancos novos ja funciona. Para bancos existentes, SQLite permite NULL mesmo em colunas definidas como NOT NULL
    # desde que o valor seja inserido diretamente — nenhuma acao necessaria.


def _erros(app: Flask):
    @app.errorhandler(404)
    def nao_encontrado(e):
        if request.path.startswith("/api/"):
            from flask import jsonify
            return jsonify({"erro": "Endpoint nao encontrado."}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def proibido(e):
        if request.path.startswith("/api/"):
            from flask import jsonify
            return jsonify({"erro": "Acesso negado."}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def erro_interno(e):
        db.session.rollback()
        if request.path.startswith("/api/"):
            from flask import jsonify
            return jsonify({"erro": "Erro interno do servidor."}), 500
        return render_template("errors/500.html"), 500


def _frontend(app: Flask):
    from flask import Blueprint
    from functools import wraps

    fe = Blueprint("frontend", __name__)

    def admin_required(f):
        @wraps(f)
        @login_required
        def inner(*a, **kw):
            if current_user.perfil != "admin":
                abort(403)
            return f(*a, **kw)
        return inner

    @fe.get("/")
    def root():
        if current_user.is_authenticated:
            return redirect("/dashboard")
        return redirect("/login")

    @fe.get("/login")
    def login_page():
        if current_user.is_authenticated:
            return redirect("/dashboard")
        erro = session.pop("login_erro", None)
        return render_template("auth/login.html", erro=erro)

    @fe.post("/login")
    def login_post():
        email   = request.form.get("email", "").strip().lower()
        senha   = request.form.get("senha", "")
        lembrar = request.form.get("lembrar") == "on"
        u = Usuario.query.filter_by(email=email, ativo=True).first()
        if not u or not u.check_senha(senha):
            session["login_erro"] = "E-mail ou senha incorretos."
            return redirect("/login")
        u.ultimo_acesso = datetime.utcnow()
        db.session.commit()
        login_user(u, remember=lembrar)
        next_url = request.args.get("next") or "/dashboard"
        # Seguranca: so redirecionar para URLs relativas
        if not next_url.startswith("/") or next_url.startswith("//"):
            next_url = "/dashboard"
        return redirect(next_url)

    @fe.get("/logout")
    @fe.post("/logout")
    @login_required
    def logout():
        from flask_login import logout_user
        logout_user()
        return redirect("/login")

    @fe.get("/dashboard")
    @login_required
    def dashboard():
        return render_template("tickets/dashboard.html")

    @fe.get("/passagem/nova")
    @login_required
    def nova_passagem():
        return render_template("tickets/nova_passagem.html")

    @fe.get("/historico")
    @login_required
    def historico():
        return render_template("tickets/historico.html")

    @fe.get("/encomendas")
    @login_required
    def encomendas():
        return render_template("encomendas/nova.html")

    @fe.get("/encomendas/historico")
    @login_required
    def encomendas_historico():
        return render_template("encomendas/historico.html")

    @fe.get("/relatorio")
    @login_required
    def relatorio():
        return render_template("relatorio/financeiro.html")

    @fe.get("/onibus")
    @login_required
    def onibus():
        return render_template("bus/lista.html")

    @fe.get("/admin")
    @admin_required
    def admin():
        return render_template("admin/painel.html")

    app.register_blueprint(fe)


def _seed_admin():
    if not Usuario.query.filter_by(perfil="admin").first():
        u = Usuario(nome="Administrador", email="admin@luzinete.com.br", perfil="admin")
        u.set_senha("admin123")
        db.session.add(u)
        db.session.commit()
        print("[SETUP] Admin criado: admin@luzinete.com.br / admin123")
        print("[SETUP] TROQUE A SENHA no painel Admin antes de usar em producao!")
