from pathlib import Path

import pytest

from services import latex_compiler
from services.latex_compiler import LatexCompilationError


def test_missing_compiler_fails_clearly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "resume.tex"
    source.write_text(r"\documentclass{article}", encoding="utf-8")
    monkeypatch.setattr(latex_compiler.shutil, "which", lambda _: None)
    with pytest.raises(LatexCompilationError, match="pdflatex is not installed"):
        latex_compiler.compile_latex(source)
