from fastapi import Security, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt
import jwt
import datetime

from database.connection import DBConnection  # usa il tuo file

SECRET_KEY = "Ragis2027"
ALGORITHM = "HS256"
security = HTTPBearer()


# ================
# HASH PASSWORD
# ================

def hash_password(password: str) -> str:
    """Restituisce hash sicuro della password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verifica password in chiaro con hash salvato."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ================
# JWT
# ================

def create_jwt(username: str, ruolo: str):
    payload = {
        "username": username,
        "ruolo": ruolo,
        "iat": datetime.datetime.now(datetime.UTC),
        "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=4)
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


# ================
# VALIDAZIONE JWT
# ================

def validate_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token scaduto")

    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token non valido")
