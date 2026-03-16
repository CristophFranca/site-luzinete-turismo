"""
Serviço de Feature Flags — ativa/desativa funcionalidades em tempo real.
"""
from backend.models.models import db, FeatureFlag

_DEFAULTS = {
    "whatsapp":        (True,  "Envio de passagem via WhatsApp"),
    "rastreio":        (False, "Rastreio em tempo real do ônibus"),
    "impressao":       (False, "Impressão de passagem em PDF"),
    "backup_auto":     (True,  "Backup automático do banco de dados"),
    "cadastro_onibus": (True,  "Cadastro e gestão de ônibus"),
}


def seed_flags():
    for chave, (padrao, descricao) in _DEFAULTS.items():
        if not FeatureFlag.query.filter_by(chave=chave).first():
            db.session.add(FeatureFlag(chave=chave, ativo=padrao, descricao=descricao))
    db.session.commit()


def is_enabled(chave: str) -> bool:
    flag = FeatureFlag.query.filter_by(chave=chave).first()
    return flag.ativo if flag else False


def toggle(chave: str, ativo: bool) -> bool:
    flag = FeatureFlag.query.filter_by(chave=chave).first()
    if not flag:
        return False
    flag.ativo = ativo
    db.session.commit()
    return True


def get_all() -> list[dict]:
    return [
        {"chave": f.chave, "ativo": f.ativo, "descricao": f.descricao}
        for f in FeatureFlag.query.order_by(FeatureFlag.chave).all()
    ]
