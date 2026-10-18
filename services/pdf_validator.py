from pathlib import Path

import fitz


def validate_generated_pdf(pdf_path: Path, expected_text: list[str]) -> str:
    if not pdf_path.is_file() or pdf_path.stat().st_size < 100:
        raise ValueError("LaTeX did not produce a valid non-empty PDF.")
    try:
        with fitz.open(pdf_path) as document:
            if document.is_encrypted or document.page_count < 1:
                raise ValueError("The generated PDF is encrypted or has no pages.")
            text = "\n".join(page.get_text("text") for page in document)
    except (fitz.FileDataError, fitz.PDFError) as exc:
        raise ValueError("The generated PDF cannot be read.") from exc
    if not text.strip():
        raise ValueError("The generated PDF contains no extractable text.")
    absent = [item for item in expected_text if item and item.casefold() not in text.casefold()]
    if absent:
        raise ValueError(
            "Generated PDF is missing expected content: " + ", ".join(absent[:3])
        )
    return text
