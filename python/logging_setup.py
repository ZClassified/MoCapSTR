"""
Log file for MoCapSTR.

The EXE has no console, so every print() and every uncaught exception used to
vanish. setup_logging() writes them to a rotating log file
(%LOCALAPPDATA%\\MoCapSTR\\logs\\mocapstr.log) and, when a console exists,
also to the console.
"""
import logging
import logging.handlers
import os
import sys
import threading

from app_paths import logs_dir

LOG_FILENAME = "mocapstr.log"


class _StreamToLogger:
    """File-like object that forwards print() output line by line to a logger."""
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
        self._buffer = ""
        self._local = threading.local()

    def write(self, text):
        if getattr(self._local, "busy", False):  # logging error while logging: drop, don't recurse
            return len(text)
        self._local.busy = True
        try:
            self._buffer += text
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                if line.strip():
                    self.logger.log(self.level, line.rstrip())
        finally:
            self._local.busy = False
        return len(text)

    def flush(self):
        pass

    def isatty(self):
        return False


def log_file_path():
    return os.path.join(logs_dir(), LOG_FILENAME)


def setup_logging():
    """Configures file (+ console) logging and captures print(), stderr and crashes."""
    console = sys.__stdout__ or sys.stdout  # None in the windowed EXE

    formatter = logging.Formatter("%(asctime)s %(levelname)-7s [%(threadName)s] %(name)s: %(message)s")
    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path(), maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    if console is not None:
        console_handler = logging.StreamHandler(console)
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(console_handler)

    sys.stdout = _StreamToLogger(logging.getLogger("stdout"), logging.INFO)
    sys.stderr = _StreamToLogger(logging.getLogger("stderr"), logging.ERROR)

    def excepthook(exc_type, exc, tb):
        logging.getLogger("crash").critical("Uncaught exception", exc_info=(exc_type, exc, tb))

    def thread_excepthook(args):
        logging.getLogger("crash").error(f"Uncaught exception in thread {args.thread.name if args.thread else '?'}",
                                         exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = excepthook
    threading.excepthook = thread_excepthook
    return log_file_path()
