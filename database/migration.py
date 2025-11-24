from database.connection import DBConnection
from auth import hash_password

def run_migrations():
    conn = DBConnection().conn

    # Crea tabella utenti se manca
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        ruolo TEXT DEFAULT 'user',
        data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Crea tabella parametri se manca
    conn.execute("""
    CREATE TABLE IF NOT EXISTS parameters (
        nome TEXT PRIMARY KEY,
        valore TEXT NOT NULL,
        tipo TEXT DEFAULT 'string',
        descrizione TEXT,
        data_aggiornamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # futuro: altre tabelle (indexing, logs, api_keys…)

    conn.commit()

    # Inserisce utente di default 'admin' con password sicura se non esiste
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", ("admin",))
    row = cur.fetchone()
    if not row:
        # Hash della password di default (password sicura per testing)
        default_password = "Ragis@2025Admin"
        hashed = hash_password(default_password)
        conn.execute(
            "INSERT INTO users (username, password_hash, ruolo) VALUES (?, ?, ?)",
            ("admin", hashed, "admin"),
        )
        conn.commit()

