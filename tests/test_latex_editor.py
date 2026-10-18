import pytest

from models.resume_changes import ResumeChange
from services.latex_editor import (
    LatexEditError,
    apply_approved_changes,
    escape_latex_text,
)

SOURCE = r"""\documentclass{article}
\begin{document}
\section{Experience}
Python developer
\end{document}
"""


def change(original: str = "Python developer", proposed: str = "Python engineer") -> ResumeChange:
    return ResumeChange(
        section="Experience",
        original_text=original,
        proposed_text=proposed,
        reason="Clarifies role",
        supporting_evidence="Python developer",
    )


def test_replaces_only_approved_exact_text_and_preserves_template() -> None:
    result = apply_approved_changes(SOURCE, [change()], {0})
    assert r"\documentclass{article}" in result
    assert r"\section{Experience}" in result
    assert "Python engineer" in result


def test_unapproved_change_leaves_source_unchanged() -> None:
    assert apply_approved_changes(SOURCE, [change()], set()) == SOURCE


def test_special_characters_are_escaped() -> None:
    assert escape_latex_text("C++ & 10%") == r"C++ \& 10\%"


def test_duplicate_or_command_replacement_is_rejected() -> None:
    with pytest.raises(LatexEditError):
        apply_approved_changes(SOURCE.replace("Python developer", "Python developer\nPython developer"), [change()], {0})
    with pytest.raises(LatexEditError):
        apply_approved_changes(SOURCE, [change(r"\end{document}", "bad")], {0})


def test_replaces_simple_latex_command_argument_preserving_command() -> None:
    source = SOURCE.replace(r"\section{Experience}", r"\section{EXPERIENCE}")
    heading_change = change(r"\section{EXPERIENCE}", "Work Experience")
    result = apply_approved_changes(source, [heading_change], {0})
    assert r"\section{Work Experience}" in result
    assert r"\documentclass{article}" in result


def test_replaces_styled_latex_text_preserving_style_command() -> None:
    source = SOURCE.replace(
        "Python developer", r"\textbf{Python developer}"
    )
    styled_change = change(r"\textbf{Python developer}", "Python engineer")
    result = apply_approved_changes(source, [styled_change], {0})
    assert r"\textbf{Python engineer}" in result


def test_replaces_plain_text_inside_complex_resume_macro() -> None:
    source = SOURCE.replace(
        "Python developer",
        r"\resumeItem{Worked as a Python developer on reporting tools}",
    )
    text_change = change("Python developer", "data analyst")
    result = apply_approved_changes(source, [text_change], {0})
    assert r"\resumeItem{Worked as a data analyst on reporting tools}" in result


def test_complex_latex_syntax_is_rejected_with_manual_edit_guidance() -> None:
    original = r"\resumeItem{Python \textbf{developer}}"
    source = SOURCE.replace(r"\end{document}", original + "\n\\end{document}")
    risky = change(original, "Portfolio")
    with pytest.raises(LatexEditError, match="plain-text phrase"):
        apply_approved_changes(source, [risky], {0})


def test_link_macro_content_is_never_changed() -> None:
    source = SOURCE.replace(
        "Python developer", r"\href{https://example.com}{\texttt{Python developer}}"
    )
    with pytest.raises(LatexEditError, match="inside a link"):
        apply_approved_changes(source, [change()], {0})


def test_malformed_document_boundary_is_rejected() -> None:
    with pytest.raises(LatexEditError, match="document boundary"):
        apply_approved_changes(SOURCE.replace(r"\end{document}", ""), [], set())
