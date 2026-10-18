from pathlib import Path

import fitz
import pytest

from services.pdf_validator import validate_generated_pdf


def test_validates_output_content(tmp_path: Path) -> None:
    path = tmp_path / "resume.pdf"
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Ada ada@example.com")
    document.save(path)
    document.close()
    assert "Ada" in validate_generated_pdf(path, ["ada@example.com"])


def test_rejects_missing_expected_content(tmp_path: Path) -> None:
    path = tmp_path / "resume.pdf"
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Resume")
    document.save(path)
    document.close()
    with pytest.raises(ValueError, match="missing expected"):
        validate_generated_pdf(path, ["ada@example.com"])
