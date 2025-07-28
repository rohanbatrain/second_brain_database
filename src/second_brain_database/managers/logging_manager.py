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
    Write a log record to the buffer file in a thread-safe and robust way, with file-level deduplication and rich JSON lines for Loki/enterprise compatibility.
    Args:
        record: The log record to write.
    Side-effects:
        Appends to BUFFER_FILE only if the line is not identical to the last line.
    """
    import json
    import socket
    import traceback
    log_dict = {
        "ts": record.created,  # Unix timestamp
        "iso_ts": record.asctime if hasattr(record, "asctime") else None,  # ISO8601 timestamp if available
        "level": record.levelname,
        "logger": record.name,
        "msg": record.getMessage(),
        "process": record.process,
        "processName": record.processName,
        "thread": record.thread,
        "threadName": record.threadName,
        "filename": record.filename,
        "funcName": record.funcName,
        "lineno": record.lineno,
        "pathname": record.pathname,
        "host": socket.gethostname(),
        "app": os.getenv("APP_NAME", getattr(settings, "APP_NAME", "Second_Brain_Database-app")),
        "env": os.getenv("ENV", getattr(settings, "ENV", "dev")),
        "exception": None,
        # Optional custom fields
        "request_id": getattr(record, "request_id", None),
        "user_id": getattr(record, "user_id", None),
        "operation_id": getattr(record, "operation_id", None),
    }
    if record.exc_info:
        log_dict["exception"] = "".join(traceback.format_exception(*record.exc_info))
    log_line = json.dumps(log_dict, ensure_ascii=False) + "\n"
    try:
        with BUFFER_LOCK:
            last_line = None
            if os.path.exists(BUFFER_FILE):
                with open(BUFFER_FILE, "rb") as f:
                    try:
                        f.seek(-4096, os.SEEK_END)
                    except OSError:
                        f.seek(0)
                    lines = f.readlines()
                    if lines:
                        last_line = lines[-1].decode("utf-8", errors="ignore").rstrip("\n")
            if last_line == log_line.rstrip("\n"):
                return  # Skip writing duplicate
            with open(BUFFER_FILE, "a", encoding="utf-8") as f:
                f.write(log_line)
    except OSError as e:
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
                    "[LoggingManager] Some buffered logs (%d/%d) could not be resent "
                    "to Loki and were kept in the buffer file.",
                    len(failed_lines),
                    len(lines),
                )
            else:
                os.remove(BUFFER_FILE)
                logger.info("[LoggingManager] Flushed all buffered logs to Loki and deleted buffer file.")

        except (OSError, ValueError) as flush_exc:
            logger.error("[LoggingManager] Failed to flush buffer to Loki: %s", flush_exc, exc_info=True)


class DeduplicateConsecutiveFilter(logging.Filter):
    """
    Filter that blocks consecutive duplicate log records (same msg, level, name).
    """
    def __init__(self):
        super().__init__()
        self._last = None

    def filter(self, record: logging.LogRecord) -> bool:
        key = (record.levelno, record.name, record.getMessage())
        if self._last == key:
            return False
        self._last = key
        return True


def get_logger(name: str = "Second_Brain_Database", add_loki: bool = True, prefix: str = "") -> logging.Logger:
    # Use process ID in log filename for per-worker logs
    pid = os.getpid()
    log_filename = f"second_brain_database_worker_{pid}.log"
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Attach a FileHandler for per-worker logging if not present
    if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', None) == os.path.abspath(log_filename) for h in logger.handlers):
        file_handler = logging.FileHandler(log_filename)
        formatter = logging.Formatter("[%(asctime)s] %(levelname)s in %(name)s: %(message)s")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(DeduplicateConsecutiveFilter())
        logger.addHandler(file_handler)
        logger.info(f"[LoggingManager] FileHandler attached to logger '{name}' (file={log_filename})")

    # Always attach a StreamHandler for console logging if not present
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        stream_handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(asctime)s] %(levelname)s in %(name)s: %(message)s")
        stream_handler.setFormatter(formatter)
        stream_handler.addFilter(DeduplicateConsecutiveFilter())
        logger.addHandler(stream_handler)
        logger.info("[LoggingManager] Console StreamHandler attached to logger '%s'", name)

    class PrefixFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if prefix and not getattr(record, "_prefix_applied", False):
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
            loki_handler.addFilter(DeduplicateConsecutiveFilter())
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
                def __init__(self):
                    super().__init__()
                    self.addFilter(DeduplicateConsecutiveFilter())
                def emit(self, record: logging.LogRecord) -> None:
                    _write_to_buffer(record)

            if not any(isinstance(h, BufferHandler) for h in logger.handlers):
                logger.addHandler(BufferHandler())
    elif not _loki_available:

        class BufferHandler(logging.Handler):
            def __init__(self):
                super().__init__()
                self.addFilter(DeduplicateConsecutiveFilter())
            def emit(self, record: logging.LogRecord) -> None:
                _write_to_buffer(record)

        if not any(isinstance(h, BufferHandler) for h in logger.handlers):
            logger.addHandler(BufferHandler())
    return logger
