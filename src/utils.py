"""Shared path, text splitting, and logging utilities."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable


def ensure_dir(path: Path) -> Path:
    """Create a directory and return it, with a friendly permission error."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OSError(f"无法创建输出目录 {path}：{exc}") from exc
    return path


def sanitize_filename(name: str) -> str:
    """Replace characters invalid in Windows filenames."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return cleaned or "document"


def validate_pdf_path(value: str | Path) -> Path:
    """Return a resolved PDF path or raise a clear validation error."""
    raw = str(value).strip()
    if not raw:
        raise ValueError("PDF 路径不能为空。")
    path = Path(raw).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"PDF 文件不存在：{path}")
    if not path.is_file():
        raise ValueError(f"路径不是文件：{path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"请选择 .pdf 文件：{path}")
    return path.resolve()


def format_page_header(page_number: int) -> str:
    """Build the stable page marker used throughout the pipeline."""
    return f"===== Page {page_number} ====="


def split_text_by_length(text: str, max_length: int) -> list[str]:
    """Split on paragraph/line/space boundaries without breaking words."""
    if max_length <= 0:
        raise ValueError("max_length 必须大于 0。")
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_length:
        return [text]

    pieces = re.split(r"(\n\n+|\n|(?<=\.)\s+|\s+)", text)
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if not piece:
            continue
        if len(current) + len(piece) <= max_length:
            current += piece
            continue
        if current.strip():
            chunks.append(current.strip())
            current = ""
        if len(piece) <= max_length:
            current = piece.lstrip()
        else:
            # A single OCR token can be abnormally long; this is the only safe fallback.
            for start in range(0, len(piece), max_length):
                part = piece[start : start + max_length]
                if len(part) == max_length:
                    chunks.append(part)
                else:
                    current = part
    if current.strip():
        chunks.append(current.strip())
    return chunks


def setup_logger(log_path: Path, callback=None) -> logging.Logger:
    """Create an isolated UTF-8 file logger, optionally mirrored to the GUI."""
    logger = logging.getLogger(f"pdf_translator.{id(log_path)}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if callback is not None:
        class CallbackHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                callback(self.format(record))

        callback_handler = CallbackHandler()
        callback_handler.setFormatter(formatter)
        logger.addHandler(callback_handler)
    return logger


def close_logger(logger: logging.Logger) -> None:
    """Flush and close handlers so the run log is immediately readable."""
    for handler in list(logger.handlers):
        handler.flush()
        handler.close()
        logger.removeHandler(handler)


def join_nonempty(parts: Iterable[str]) -> str:
    """Join non-empty blocks with a blank line."""
    return "\n\n".join(part.strip() for part in parts if part.strip())
