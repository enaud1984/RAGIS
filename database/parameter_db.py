class ParameterDB:
    def __init__(self):
        self.db = DBConnection()
        self.conn = self.db.conn

    def get(self, name, default=None):
        try:
            cur = self.conn.execute("SELECT valore FROM parameters WHERE nome=?", (name,))
            row = cur.fetchone()
            return row[0] if row else default
        finally:
            self.db.close()

    def set(self, nome, valore, tipo="stringa", descrizione=None):
        try:
            self.conn.execute("""
                INSERT INTO parameters(nome, valore, tipo, descrizione)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(nome) DO UPDATE SET 
                    valore=excluded.valore,
                    tipo=excluded.tipo,
                    descrizione=excluded.descrizione,
                    data_aggiornamento=CURRENT_TIMESTAMP
            """, (nome, str(valore), tipo, descrizione))
            self.conn.commit()
        finally:
            self.db.close()