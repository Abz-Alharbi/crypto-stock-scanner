import json
import logging
import os
import sys

RESERVED_LOG_RECORD_KEYS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


def configure_logging():
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_json_formatter())
    root_logger.addHandler(handler)

    logging.getLogger("werkzeug").setLevel(log_level)


def _json_formatter():
    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
    try:
        from pythonjsonlogger import jsonlogger

        return jsonlogger.JsonFormatter(fmt)
    except ImportError:
        return FallbackJsonFormatter()


class FallbackJsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in RESERVED_LOG_RECORD_KEYS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))
