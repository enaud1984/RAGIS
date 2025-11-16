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

    @staticmethod
    def get_logger(name: str,
                   log_dir: str = "logs",
                   log_file: str = "app.log",
                   backup_count: int = 7
                   ) -> logging.Logger:

        level = logging.INFO  # SOLO INFO+ERROR+CRITICAL

        # Crea cartella log se non esiste
        log_dir_path = Path(log_dir)
        log_dir_path.mkdir(parents=True, exist_ok=True)
        full_log_path = log_dir_path / log_file

        logger = logging.getLogger(name)
        logger.setLevel(level)

        if not RagLog._handlers_initialized:

            # Formato base
            log_format = "%(asctime)s - %(funcName)s - %(levelname)s - %(message)s"
            formatter = logging.Formatter(log_format)

            # Rotazione giornaliera
            rotating_handler = TimedRotatingFileHandler(
                filename=str(full_log_path),
                when="midnight",
                backupCount=backup_count,
                encoding="utf-8",
            )
            rotating_handler.setLevel(level)        # SOLO INFO+
            rotating_handler.setFormatter(formatter)

            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)         # SOLO INFO+
            console_handler.setFormatter(formatter)

            # Attacco gli handler al LOG ROOT
            root = logging.getLogger()
            root.setLevel(level)
            root.addHandler(rotating_handler)
            root.addHandler(console_handler)

            RagLog._handlers_initialized = True

        return logger