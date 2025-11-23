import sqlite3
from pathlib import Path
from threading import Lock

class DBConnection:
    _instance = None
    _lock = Lock()

    def __new__(cls, db_path="db_sql/app.db"):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DBConnection, cls).__new__(cls)
                cls._instance._init(db_path)
        return cls._instance

    def _init(self, db_path):
        db_path = Path(db_path)

        # CREA LA CARTELLA SE NON ESISTE
        if not db_path.parent.exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(db_path,check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def cursor(self):
        return self.conn.cursor()

    def commit(self):
        """Commit della transazione"""
        self.conn.commit()

    def close(self):
        """Chiude la connessione"""
        if self.conn:
            self.conn.close()