import sqlite3
from pathlib import Path

class DBConnection:

    def __init__(self, db_path="db_sql/app.db"):
        db_path = Path(db_path)

        # CREA LA CARTELLA SE NON ESISTE
        if not db_path.parent.exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)

        # ⚠️ CREO UNA NUOVA CONNESSIONE AD OGNI CHIAMATA
        self.conn = sqlite3.connect(
            db_path,
            check_same_thread=False,
            timeout=30  # importantissimo!
        )
        self.conn.row_factory = sqlite3.Row

    def cursor(self):
        return self.conn.cursor()

    def close(self):
        self.conn.close()