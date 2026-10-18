import fitz
import re

from utils.file_validation import validate_pdf


def extract_pdf_text(data: bytes, filename: str = "resume.pdf") -> str:
    validate_pdf(data, filename)
    with fitz.open(stream=data, filetype="pdf") as document:
        text = "\n".join(page.get_text("text") for page in document)
    if not text.strip():
        raise ValueError("No selectable text was found in the PDF.")
    return text


def compare_resume_sources(pdf_text: str, latex_source: str) -> float:
    def tokens(value: str) -> set[str]:
        without_commands = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?", " ", value)
        return {
            word.casefold()
            for word in re.findall(r"[A-Za-z0-9+#.-]+", without_commands)
            if len(word) > 2
        }

    pdf_tokens = tokens(pdf_text)
    source_tokens = tokens(latex_source)
    if not pdf_tokens or not source_tokens:
        return 0.0
    return len(pdf_tokens & source_tokens) / len(pdf_tokens)
