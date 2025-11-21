from database.connection import DBConnection

def run_migrations():
    conn = DBConnection().conn

    # Tabella utenti
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        ruolo TEXT DEFAULT 'user',
        data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Tabella parametri
    conn.execute("""
    CREATE TABLE IF NOT EXISTS parameters (
        nome TEXT PRIMARY KEY,
        valore TEXT NOT NULL,
        tipo TEXT DEFAULT 'string',
        descrizione TEXT,
        data_aggiornamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)


    # futuro: altre tabelle
    # e.g. indexing, logs, api_keys…

    conn.commit()
