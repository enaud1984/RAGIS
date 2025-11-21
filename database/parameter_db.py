from .connection import DBConnection

class ParameterDB:
    def __init__(self):
        self.conn = DBConnection().conn

    def get(self, name, default=None):
        cur = self.conn.execute("SELECT valore FROM parameters WHERE nome=?", (name,))
        row = cur.fetchone()
        return row[0] if row else default

    def set(self, nome, valore, tipo="stringa", descrizione=None):
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