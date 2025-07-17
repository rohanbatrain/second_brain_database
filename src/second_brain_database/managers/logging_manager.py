"""
Centralized logging manager for the application.

This module provides a robust,
production-ready logging setup with Loki integration and file-based buffering for downtime.

Loki Downtime Handling:
----------------------
- If Loki is unavailable at import or handler setup,
  logs are sent to the console (stdout) via StreamHandler.
- If Loki becomes unavailable at runtime (e.g., network outage),
  logs sent to the Loki handler may be lost or dropped, 
  depending on the handler's internal retry/buffering logic.
- By default, logs generated during Loki downtime are NOT automatically resent to Loki
  when it comes back up.
- To guarantee delivery of all logs to Loki,
  you would need to implement a persistent queue or file-based buffer that stores logs locally and
  flushes them to Loki when it is available again. This is not implemented in this codebase.
- For critical audit/compliance use cases,
  consider using a log shipper (e.g., Promtail, Fluentd)
  or a custom handler with persistent buffering.

Usage:
- Use get_logger() to obtain a logger instance. 
Logs will go to Loki if available, otherwise to console or buffer file.
"""

import logging
import os
import threading
from second_brain_database.config import settings

try:
    from loki_logger_handler.loki_logger_handler import LokiLoggerHandler
    _loki_available: bool = True
except ImportError as e:
    LokiLoggerHandler = None  # type: ignore
    _loki_available = False
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("Second_Brain_Database").warning(
        "[LoggingManager] LokiLoggerHandler import failed: %s. Falling back to console logging.", e
    )

LOKI_URL: str = os.getenv("LOKI_URL", getattr(settings, "LOKI_URL", "http://localhost:3100/loki/api/v1/push"))
LOKI_TAGS: dict[str, str] = {
    "app": os.getenv("APP_NAME", getattr(settings, "APP_NAME", "Second_Brain_Database-app")),
    "env": os.getenv("ENV", getattr(settings, "ENV", "dev")),
}
LOG_LEVEL: str = os.getenv("LOG_LEVEL", getattr(settings, "LOG_LEVEL", "INFO")).upper()
BUFFER_FILE: str = os.getenv("LOKI_BUFFER_FILE", getattr(settings, "LOKI_BUFFER_FILE", "loki_buffer.log"))
LOKI_VERSION: str = getattr(settings, "LOKI_VERSION", "1")
LOKI_COMPRESS: bool = getattr(settings, "LOKI_COMPRESS", True)
BUFFER_LOCK = threading.Lock()


def _write_to_buffer(record: logging.LogRecord) -> None:
    """
    Write a log record to the buffer file in a thread-safe and robust way.
    Args:
        record: The log record to write.
    Side-effects:
        Appends to BUFFER_FILE.
    """
    log_line = f"{record.created}|{record.levelname}|{record.name}|{record.getMessage()}\n"
    try:
        with BUFFER_LOCK:
            with open(BUFFER_FILE, "a", encoding="utf-8") as f:
                f.write(log_line)
    except OSError as e:
        # Fallback: print to stderr if buffer file is not writable
        logging.getLogger("Second_Brain_Database").error(
            "[LoggingManager] Failed to write log to buffer file '%s': %s", BUFFER_FILE, e, exc_info=True
        )

def _flush_buffer_to_loki(loki_handler: logging.Handler, logger: logging.Logger) -> None:
    """
    Push buffered logs to Loki and delete the buffer file if successful.
    Args:
        loki_handler: The Loki handler to emit logs to.
        logger: Logger for error reporting.
    Side-effects:
        Reads and deletes BUFFER_FILE if present.
    """
    if not os.path.exists(BUFFER_FILE):
        return

    with BUFFER_LOCK:
        try:
            with open(BUFFER_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()

            failed_lines = []
            for idx, line in enumerate(lines):
                try:
                    parts = line.strip().split("|", 3)
                    if len(parts) != 4:
                        raise ValueError(f"Malformed log line at index {idx}: {line!r}")
                    created, level, name, msg = parts
                    try:
                        created_float = float(created)
                    except ValueError:
                        created_float = None
                    record = logging.LogRecord(
                        name=name,
                        level=getattr(logging, level, logging.INFO),
                        pathname="(buffered)",
                        lineno=0,
                        msg=msg,
                        args=None,
                        exc_info=None,
                    )
                    if created_float is not None:
                        record.created = created_float
                    loki_handler.emit(record)
                except (ValueError, OSError) as e:
                    logger.error(
                        "[LoggingManager] Failed to parse or send buffered log (line %d): %s",
                        idx,
                        e,
                        exc_info=True,
                    )
                    failed_lines.append(line)

            if failed_lines:
                with open(BUFFER_FILE, "w", encoding="utf-8") as f:
                    f.writelines(failed_lines)
                logger.warning(
                    "[LoggingManager] Some buffered logs (%d/%d) could not be resent " \
                    "to Loki and were kept in the buffer file.",
                    len(failed_lines),
                    len(lines),
                )
            else:
                os.remove(BUFFER_FILE)
                logger.info("[LoggingManager] Flushed all buffered logs to Loki and deleted buffer file.")

        except (OSError, ValueError) as flush_exc:
            logger.error("[LoggingManager] Failed to flush buffer to Loki: %s", flush_exc, exc_info=True)


def get_logger(name: str = "Second_Brain_Database", add_loki: bool = True, prefix: str = "") -> logging.Logger:
    # Always get the logger and ensure at least a StreamHandler is attached
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Always attach a StreamHandler for console logging if not present
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        stream_handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(name)s: %(message)s"
        )
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        logger.info(
            "[LoggingManager] Console StreamHandler attached to logger '%s'", name
        )

    class PrefixFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if prefix and not getattr(record, '_prefix_applied', False):
                record.msg = f"{prefix} {record.msg}"
                record._prefix_applied = True
            return True

    if prefix and not any(isinstance(f, PrefixFilter) for f in logger.filters):
        logger.addFilter(PrefixFilter())

    handler_types = [type(h) for h in logger.handlers]
    if add_loki and _loki_available and LokiLoggerHandler not in handler_types:
        try:
            loki_handler = LokiLoggerHandler(
                url=LOKI_URL,
                labels=LOKI_TAGS,
                auth=None,
                compressed=LOKI_COMPRESS,
            )
            logger.addHandler(loki_handler)
            logger.info(
                "[LoggingManager] LokiLoggerHandler attached to logger '%s' (url=%s, labels=%s)",
                name,
                LOKI_URL,
                LOKI_TAGS,
            )
            _flush_buffer_to_loki(loki_handler, logger)
        except (ImportError, OSError) as e:
            logger.error(
                "[LoggingManager] Failed to attach LokiLoggerHandler: %s. Falling back to file buffer.",
                e,
                exc_info=True,
            )
            class BufferHandler(logging.Handler):
                def emit(self, record: logging.LogRecord) -> None:
                    _write_to_buffer(record)
            if not any(isinstance(h, BufferHandler) for h in logger.handlers):
                logger.addHandler(BufferHandler())
    elif not _loki_available:
        class BufferHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                _write_to_buffer(record)
        if not any(isinstance(h, BufferHandler) for h in logger.handlers):
            logger.addHandler(BufferHandler())
    return logger
