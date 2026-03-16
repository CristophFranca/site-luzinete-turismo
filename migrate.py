"""
migrate.py — Migracao do banco para v1.1.0
Torna viagens.onibus_id opcional e adiciona colunas empresa e total_poltronas.

Execute UMA VEZ:
    python migrate.py
"""
import sqlite3
from pathlib import Path
from backend.config.settings import DB_PATH

def migrar():
    print(f"Banco: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    cur  = conn.cursor()
    cur.execute("PRAGMA foreign_keys = OFF")

    # Verifica se ja foi migrado
    cur.execute("PRAGMA table_info(viagens)")
    colunas = {row[1]: row[3] for row in cur.fetchall()}  # nome: notnull
    print("Colunas atuais:", list(colunas.keys()))

    ja_tem_empresa    = "empresa" in colunas
    ja_tem_poltronas  = "total_poltronas" in colunas
    onibus_obrigatorio = colunas.get("onibus_id", 0) == 1  # 1 = NOT NULL

    if ja_tem_empresa and ja_tem_poltronas and not onibus_obrigatorio:
        print("Banco ja esta na versao 1.1.0 — nada a fazer.")
        conn.close()
        return

    print("Migrando tabela viagens...")

    # SQLite nao permite ALTER COLUMN — precisa recriar a tabela
    cur.execute("""
        CREATE TABLE viagens_nova (
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

    # Copia dados — preenche empresa e total_poltronas a partir do onibus
    cur.execute("""
        INSERT INTO viagens_nova
            (id, onibus_id, empresa, total_poltronas, origem, destino,
             data_partida, data_retorno, tipo, valor_inteiro, valor_meia,
             status, criado_em)
        SELECT
            v.id,
            v.onibus_id,
            COALESCE(NULLIF(%(emp)s, ''), o.identificador, ''),
            COALESCE(%(pol)s, o.total_poltronas, 44),
            v.origem,
            v.destino,
            v.data_partida,
            v.data_retorno,
            v.tipo,
            v.valor_inteiro,
            v.valor_meia,
            v.status,
            v.criado_em
        FROM viagens v
        LEFT JOIN onibus o ON o.id = v.onibus_id
    """ % {
        "emp": "v.empresa" if ja_tem_empresa else "''",
        "pol": "v.total_poltronas" if ja_tem_poltronas else "NULL",
    })

    copiadas = cur.rowcount
    print(f"  {copiadas} viagens copiadas")

    # Substitui tabela
    cur.execute("DROP TABLE viagens")
    cur.execute("ALTER TABLE viagens_nova RENAME TO viagens")
    print("  Tabela recriada com onibus_id opcional")

    cur.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    conn.close()
    print("\nMigracao concluida! Reinicie o servidor.")

if __name__ == "__main__":
    migrar()
