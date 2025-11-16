import logging
from logging.handlers import TimedRotatingFileHandler
import sys
from pathlib import Path


class RagLog:
    """
    Logger riutilizzabile con rotazione giornaliera.
    Formato log:
    timestamp - funzione - livello - messaggio
    """

    _handlers_initialized = False  # evita duplicazioni di handler
    _external_filtered = False     # evita di filtrare esterni più volte

    @staticmethod
    def get_logger(name: str,
                   log_dir: str = "logs",
                   log_file: str = "app.log",
                   backup_count: int = 7
                   ) -> logging.Logger:

        level = logging.INFO  # logga INFO, WARNING, ERROR, CRITICAL

        # Crea cartella log
        log_dir_path = Path(log_dir)
        log_dir_path.mkdir(parents=True, exist_ok=True)
        full_log_path = log_dir_path / log_file

        logger = logging.getLogger(name)
        logger.setLevel(level)

        # -------------- HANDLER (una sola volta) --------------
        if not RagLog._handlers_initialized:

            formatter = logging.Formatter(
                "%(asctime)s - %(funcName)s - %(levelname)s - %(message)s"
            )

            # Rotazione giornaliera
            rotating_handler = TimedRotatingFileHandler(
                filename=str(full_log_path),
                when="midnight",
                backupCount=backup_count,
                encoding="utf-8",
            )
            rotating_handler.setLevel(level)
            rotating_handler.setFormatter(formatter)

            # Console
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_handler.setFormatter(formatter)

            # Handlers al logger ROOT (centralizzato)
            root = logging.getLogger()
            root.setLevel(level)
            root.addHandler(rotating_handler)
            root.addHandler(console_handler)

            RagLog._handlers_initialized = True

        # -------------- FILTRI LOGGER ESTERNI (una sola volta) --------------
        if not RagLog._external_filtered:

            # Watchfiles spam
            logging.getLogger("watchfiles").setLevel(logging.WARNING)
            logging.getLogger("watchfiles.main").setLevel(logging.WARNING)

            # FastAPI / Uvicorn troppo verbosi
            logging.getLogger("uvicorn.error").setLevel(logging.INFO)
            logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
            logging.getLogger("fastapi").setLevel(logging.INFO)

            RagLog._external_filtered = True

        return logger