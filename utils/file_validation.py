from __future__ import annotations

import re
from pathlib import Path

import fitz

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class FileValidationError(ValueError):
    """An uploaded file failed validation."""


def validate_pdf(data: bytes, filename: str) -> None:
    if Path(filename).suffix.lower() != ".pdf":
        raise FileValidationError("Upload a PDF file for the resume.")
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise FileValidationError("The PDF must be non-empty and no larger than 10 MB.")
    try:
        with fitz.open(stream=data, filetype="pdf") as document:
            if document.is_encrypted or document.page_count < 1:
                raise FileValidationError("The PDF is encrypted or contains no pages.")
            if document.page_count > 100:
                raise FileValidationError("The PDF cannot exceed 100 pages.")
    except fitz.FileDataError as exc:
        raise FileValidationError("The uploaded file is not a readable PDF.") from exc


def validate_latex(data: bytes, filename: str) -> str:
    if Path(filename).suffix.lower() != ".tex":
        raise FileValidationError("Upload the LaTeX source file (.tex).")
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise FileValidationError("The LaTeX file must be non-empty and no larger than 10 MB.")
    try:
        source = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FileValidationError("The LaTeX source must use UTF-8 encoding.") from exc
    if "\\documentclass" not in source or "\\begin{document}" not in source:
        raise FileValidationError("The source does not look like a complete LaTeX document.")
    return source


def safe_filename(name: str, fallback: str = "resume") -> str:
    stem = Path(name).stem
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._")
    return (cleaned or fallback)[:80]
