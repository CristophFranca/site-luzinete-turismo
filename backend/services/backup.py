"""
Serviço de Backup — copia o arquivo SQLite com timestamp.
(Para MySQL, troque por subprocess + mysqldump)
"""
import shutil
from datetime import datetime
from pathlib import Path
from flask import current_app
from backend.services.feature_flags import is_enabled


def realizar() -> tuple[bool, str]:
    if not is_enabled("backup_auto"):
        return False, "Backup automatico desativado."

    backup_dir = Path(current_app.config["BACKUP_DIR"])
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Usa DB_PATH de settings diretamente — evita parsear URI
    from backend.config.settings import DB_PATH
    db_path = DB_PATH
    if not db_path.exists():
        return False, f"Arquivo de banco nao encontrado: {db_path}"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"backup_{ts}.db"
    shutil.copy2(db_path, dest)

    _limpar_antigos(backup_dir)
    return True, f"Backup salvo: {dest.name}"


def listar() -> list[dict]:
    backup_dir = Path(current_app.config["BACKUP_DIR"])
    if not backup_dir.exists():
        return []
    arquivos = sorted(backup_dir.glob("backup_*.db"), reverse=True)
    return [
        {
            "nome": f.name,
            "tamanho_kb": round(f.stat().st_size / 1024, 1),
            "criado_em": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M"),
        }
        for f in arquivos
    ]


def _limpar_antigos(backup_dir: Path, manter: int = 30):
    arquivos = sorted(backup_dir.glob("backup_*.db"), reverse=True)
    for f in arquivos[manter:]:
        f.unlink(missing_ok=True)
