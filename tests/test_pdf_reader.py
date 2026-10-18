import fitz

from services.pdf_reader import compare_resume_sources, extract_pdf_text


def make_pdf(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def test_extracts_pdf_text() -> None:
    text = extract_pdf_text(make_pdf("Ada Lovelace Python engineer"), "resume.pdf")
    assert "Ada Lovelace" in text


def test_compares_pdf_and_latex_content() -> None:
    assert compare_resume_sources("Python backend engineer", r"\textbf{Python backend engineer}") > 0.5
