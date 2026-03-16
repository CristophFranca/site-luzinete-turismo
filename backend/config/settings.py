"""
Configuracoes centrais — Luzinete Turismo
"""
import os
import sqlite3
import secrets
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH  = BASE_DIR / "database" / "luzinete.db"


def _bool(v: str) -> bool:
    return str(v).lower() in ("true", "1", "yes")


def _db_creator():
    """
    Cria a pasta e abre a conexao SQLite diretamente via sqlite3.
    Contorna qualquer problema de URI no Windows (barras, acentos, espacos).
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


class Config:
    SECRET_KEY               = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    SESSION_COOKIE_HTTPONLY  = True
    SESSION_COOKIE_SAMESITE  = "Lax"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 30
    WTF_CSRF_ENABLED         = False

    # URI qualquer — o creator abaixo substitui a conexao real
    SQLALCHEMY_DATABASE_URI      = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS    = {
        "creator":          _db_creator,
        "pool_pre_ping":    True,
    }

    BACKUP_DIR            = os.getenv("BACKUP_DIR", str(BASE_DIR / "database" / "backups"))
    BACKUP_INTERVAL_HOURS = int(os.getenv("BACKUP_INTERVAL_HOURS", 24))

    WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "wame")
    ZAPI_INSTANCE     = os.getenv("ZAPI_INSTANCE", "")
    ZAPI_TOKEN        = os.getenv("ZAPI_TOKEN", "")
    TWILIO_SID        = os.getenv("TWILIO_SID", "")
    TWILIO_TOKEN      = os.getenv("TWILIO_TOKEN", "")
    TWILIO_PHONE      = os.getenv("TWILIO_PHONE", "")

    DEFAULT_FEATURES: dict = {
        "whatsapp":        _bool(os.getenv("FEATURE_WHATSAPP",        "true")),
        "rastreio":        _bool(os.getenv("FEATURE_RASTREIO",        "false")),
        "impressao":       _bool(os.getenv("FEATURE_IMPRESSAO",       "false")),
        "backup_auto":     _bool(os.getenv("FEATURE_BACKUP_AUTO",     "true")),
        "cadastro_onibus": _bool(os.getenv("FEATURE_CADASTRO_ONIBUS", "true")),
    }


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = os.getenv("HTTPS", "false") == "true"
    PROPAGATE_EXCEPTIONS  = False


_map = {"development": DevelopmentConfig, "production": ProductionConfig}


def get_config():
    env = os.getenv("FLASK_ENV", "development")
    if env == "production" and not os.getenv("SECRET_KEY"):
        import sys
        print("AVISO: SECRET_KEY nao definida — usando chave temporaria.", file=sys.stderr)
    return _map.get(env, DevelopmentConfig)
