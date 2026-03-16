"""
Servico de Atualizacao — Luzinete Turismo

Fluxo:
  1. Operador coloca update_vX.X.X.zip em /updates/
  2. Painel Admin detecta e exibe botao "Aplicar atualizacao"
  3. Clicar: faz backup do banco, extrai zip preservando .env e database/
  4. Encerra o servidor (sys.exit) — VBS detecta e reinicia automaticamente
"""
import json
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from backend.config.settings import DB_PATH
from backend.services.backup import realizar as fazer_backup

BASE_DIR    = Path(__file__).resolve().parent.parent.parent
UPDATES_DIR = BASE_DIR / "updates"
VERSION_FILE = BASE_DIR / "version.json"

# Arquivos/pastas que NUNCA sao sobrescritos na atualizacao
PROTEGIDOS = {
    ".env",
    "database",
    "updates",
    ".deps_ok",
    "version.json",  # sera sobrescrito pelo zip, mas com cuidado
}


def versao_atual() -> str:
    try:
        return json.loads(VERSION_FILE.read_text())["version"]
    except Exception:
        return "1.0.0"


def buscar_update() -> dict | None:
    """Retorna info do zip de update encontrado em /updates/, ou None."""
    UPDATES_DIR.mkdir(exist_ok=True)
    zips = sorted(UPDATES_DIR.glob("update_v*.zip"), reverse=True)
    if not zips:
        return None
    z = zips[0]
    # Extrai versao do nome: update_v1.2.3.zip -> 1.2.3
    nome = z.stem  # update_v1.2.3
    versao_nova = nome.replace("update_v", "")
    versao_atual_ = versao_atual()
    return {
        "arquivo":      z.name,
        "caminho":      str(z),
        "versao_nova":  versao_nova,
        "versao_atual": versao_atual_,
        "nova":         versao_nova != versao_atual_,
    }


def aplicar_update() -> tuple[bool, str]:
    """
    Aplica o update encontrado em /updates/.
    Retorna (sucesso, mensagem).
    """
    info = buscar_update()
    if not info:
        return False, "Nenhum arquivo de update encontrado em /updates/"

    zip_path = Path(info["caminho"])

    # 1. Backup automatico do banco antes de qualquer coisa
    ok, msg_backup = fazer_backup()
    if not ok:
        return False, f"Falha no backup pre-update: {msg_backup}"

    # 2. Valida o zip
    if not zipfile.is_zipfile(zip_path):
        return False, "Arquivo de update invalido (nao e um zip valido)."

    # 3. Extrai para pasta temporaria
    tmp = BASE_DIR / ".update_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmp)

        # 4. Detecta raiz do zip (pode ter ou nao uma pasta raiz dentro)
        conteudo = list(tmp.iterdir())
        if len(conteudo) == 1 and conteudo[0].is_dir():
            raiz_zip = conteudo[0]
        else:
            raiz_zip = tmp

        # 5. Copia arquivos novos para BASE_DIR, respeitando PROTEGIDOS
        for item in raiz_zip.rglob("*"):
            rel = item.relative_to(raiz_zip)
            partes = rel.parts
            # Ignora se a primeira pasta/arquivo e protegido
            if partes and partes[0] in PROTEGIDOS:
                continue
            destino = BASE_DIR / rel
            if item.is_dir():
                destino.mkdir(parents=True, exist_ok=True)
            else:
                destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, destino)

        # 6. Move zip para historico
        hist = UPDATES_DIR / "aplicados"
        hist.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.move(str(zip_path), str(hist / f"{zip_path.stem}_{ts}.zip"))

    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        return False, f"Erro ao extrair update: {e}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # 7. Encerra o servidor — VBS vai reiniciar automaticamente
    # Faz isso em thread separada para dar tempo de retornar a resposta HTTP
    import threading
    def encerrar():
        import time
        time.sleep(2)
        sys.exit(0)
    threading.Thread(target=encerrar, daemon=True).start()

    return True, f"Update {info['versao_nova']} aplicado! Reiniciando..."
