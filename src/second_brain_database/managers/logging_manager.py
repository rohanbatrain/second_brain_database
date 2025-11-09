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

from datetime import datetime, timezone
import logging
import os
import sys
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


def _ensure_console_handler(logger: logging.Logger, formatter: logging.Formatter) -> bool:
    """
    Ensure logger has a StreamHandler for console output.

    Args:
        logger: The logger instance to check and modify
        formatter: The formatter to apply to the StreamHandler

    Returns:
        bool: True if a new StreamHandler was added, False if one already existed
    """
    # Check if StreamHandler already exists for stdout
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream is sys.stdout:
            return False  # Already has console handler

    # Add StreamHandler for console output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logger.level)
    logger.addHandler(console_handler)
    return True


import threading
import time

import requests

LOKI_HEALTH_URL = os.getenv("LOKI_HEALTH_URL", LOKI_URL.replace("/loki/api/v1/push", "/ready"))
LOKI_PING_INTERVAL_SECONDS = 24 * 60 * 60  # Once per day

LOKI_BUFFER_FLUSH_ENABLED = True  # Global admin toggle


def set_loki_buffer_flush_enabled(enabled: bool):
    global LOKI_BUFFER_FLUSH_ENABLED
    LOKI_BUFFER_FLUSH_ENABLED = enabled


def ping_loki_and_flush_if_available():
    """
    Ping Loki's health endpoint. If available, flush buffer and switch to Loki logging.
    Schedules itself to run again in 24 hours.
    """
    logger = get_logger()
    try:
        # Use shorter timeout and more aggressive connection settings
        resp = requests.get(
            LOKI_HEALTH_URL,
            timeout=(2, 3),  # (connect_timeout, read_timeout)
            headers={"Connection": "close"},  # Don't keep connection alive
        )
        if resp.status_code == 200:
            logger.info("[LoggingManager] Loki is available. Flushing buffer and switching to Loki logging.")
            if LOKI_BUFFER_FLUSH_ENABLED:
                # Attach Loki handler if not present
                if _loki_available and LokiLoggerHandler:
                    handler_types = [type(h) for h in logger.handlers]
                    if LokiLoggerHandler not in handler_types:
                        loki_handler = LokiLoggerHandler(
                            url=LOKI_URL,
                            labels=LOKI_TAGS,
                            auth=None,
                            compressed=LOKI_COMPRESS,
                        )
                        logger.addHandler(loki_handler)
                    else:
                        loki_handler = [h for h in logger.handlers if isinstance(h, LokiLoggerHandler)][0]
                    _flush_buffer_to_loki(loki_handler, logger)
                    archive_worker_logs(logger)
            else:
                logger.info("[LoggingManager] Buffer flush is disabled by admin toggle.")
        else:
            logger.warning(f"[LoggingManager] Loki health check failed: status {resp.status_code}")
    except (
        requests.exceptions.RequestException,
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
    ) as e:
        logger.warning(f"[LoggingManager] Loki health check connection failed: {e}")
    except Exception as e:
        logger.warning(f"[LoggingManager] Loki health check exception: {e}")
    finally:
        # Always schedule next ping, even if this one failed
        try:
            timer = threading.Timer(LOKI_PING_INTERVAL_SECONDS, ping_loki_and_flush_if_available)
            timer.daemon = True  # Make it a daemon thread so it doesn't prevent process exit
            timer.start()
        except Exception as timer_e:
            logger.error(f"[LoggingManager] Failed to schedule next Loki ping: {timer_e}")


# Start the daily ping/flush scheduler at import with error handling
try:
    timer = threading.Timer(10, ping_loki_and_flush_if_available)
    timer.daemon = True  # Make it a daemon thread so it doesn't prevent process exit
    timer.start()  # Delay 10s to avoid race at startup
except Exception as e:
    # If we can't start the timer, log it but don't crash the application
    logging.getLogger("Second_Brain_Database").warning(
        f"[LoggingManager] Failed to start Loki ping scheduler: {e}. Loki integration disabled."
    )


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
                archive_worker_logs(logger)

        except (OSError, ValueError) as flush_exc:
            logger.error("[LoggingManager] Failed to flush buffer to Loki: %s", flush_exc, exc_info=True)


def archive_worker_logs(logger: logging.Logger = None):
    """
    Move all per-worker log files from logs/ to logs/archive/ after successful Loki delivery.
    """
    import shutil

    logs_dir = os.path.join("logs")
    archive_dir = os.path.join(logs_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    for fname in os.listdir(logs_dir):
        if fname.startswith("worker_") and fname.endswith(".log"):
            src = os.path.join(logs_dir, fname)
            dst = os.path.join(archive_dir, fname)
            try:
                shutil.move(src, dst)
                if logger:
                    logger.info(f"[LoggingManager] Archived worker log file: {fname}")
            except Exception as e:
                if logger:
                    logger.warning(f"[LoggingManager] Failed to archive worker log file {fname}: {e}")


def get_worker_log_filename():
    import os

    pid = os.getpid()
    return os.path.join("logs", f"worker_{pid}.log")


def get_worker_registry_filename():
    return os.path.join("logs", "worker_registry.json")


def get_logger(name: str = "Second_Brain_Database", add_loki: bool = True, prefix: str = "") -> logging.Logger:
    import json

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Create standard formatter for all handlers
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s in %(name)s: %(message)s")

    # Always ensure console handler is present first (early in setup process)
    console_added = _ensure_console_handler(logger, formatter)
    if console_added:
        logger.info("[LoggingManager] Console StreamHandler attached to logger '%s'", name)

    # Per-worker log file in logs/
    log_filename = get_worker_log_filename()
    os.makedirs(os.path.dirname(log_filename), exist_ok=True)
    if not any(
        isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == os.path.abspath(log_filename)
        for h in logger.handlers
    ):
        file_handler = logging.FileHandler(log_filename)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        # Register worker in registry
        reg_file = get_worker_registry_filename()
        worker_info = {
            "pid": os.getpid(),
            "log_file": log_filename,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "hostname": os.getenv("HOSTNAME", os.uname().nodename),
        }
        try:
            if os.path.exists(reg_file):
                with open(reg_file, "r", encoding="utf-8") as f:
                    reg = json.load(f)
            else:
                reg = {}
            reg[str(os.getpid())] = worker_info
            with open(reg_file, "w", encoding="utf-8") as f:
                json.dump(reg, f, indent=2)
        except Exception as e:
            logger.warning("[LoggingManager] Could not update worker registry: %s", e)

    # Shared Loki buffer file in logs/
    global BUFFER_FILE
    BUFFER_FILE = os.path.join("logs", "loki_buffer.log")

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
