from database.connection import DBConnection


class ParameterDB:

    def get(self, name, default=None):
        try:
            db = DBConnection()
            conn = db.conn
            cur = conn.execute("SELECT valore FROM parameters WHERE nome=?", (name,))
            row = cur.fetchone()
            return row[0] if row else default
        finally:
            db.close()

    def set(self, nome, valore, tipo="stringa", descrizione=None):
        try:
            db = DBConnection()
            conn = db.conn
            conn.execute("""
                INSERT INTO parameters(nome, valore, tipo, descrizione)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(nome) DO UPDATE SET 
                    valore=excluded.valore,
                    tipo=excluded.tipo,
                    descrizione=excluded.descrizione,
                    data_aggiornamento=CURRENT_TIMESTAMP
            """, (nome, str(valore), tipo, descrizione))
            conn.commit()
        finally:
            db.close()