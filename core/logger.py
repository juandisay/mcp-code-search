import json
import logging
import sys
from datetime import datetime


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "thread": record.threadName,
            "filename": record.filename,
            "lineno": record.lineno,
        }

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_record.update(record.extra_fields)

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)

def setup_logging(level: int = logging.INFO, mcp_mode: bool = False):
    """Setup structured logging for the application.
    
    In MCP mode, we must be EXTREMELY careful to never write to stdout.
    """
    root_logger = logging.getLogger()

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Force stderr for ALL diagnostic output (Pillar II)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())

    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Capture python warnings into the logging system
    logging.captureWarnings(True)
    warnings_logger = logging.getLogger("py.warnings")
    for handler in warnings_logger.handlers[:]:
        warnings_logger.removeHandler(handler)
    warnings_logger.addHandler(handler)

    # Silent noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)

    return root_logger
