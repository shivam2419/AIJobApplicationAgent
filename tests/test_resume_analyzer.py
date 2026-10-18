import json

import pytest

from models.application import JobDetails
from models.job_analysis import JobAnalysis
from services import resume_analyzer


SOURCE = r"""\documentclass{article}
\newcommand{\resumeItem}[1]{\item #1}
\begin{document}
\section{Projects}
\resumeItem{Built data reports with SQL.}
\end{document}
% Original trailer comment
"""


def details() -> JobDetails:
    return JobDetails(
        job_title="Data Analyst",
        company_name="Example",
        job_description="Analyze business data and communicate trends to stakeholders.",
        hr_email="hr@example.com",
    )


def test_tailoring_rewrites_body_and_preserves_template(monkeypatch: pytest.MonkeyPatch) -> None:
    tailored_body = (
        r"\section{Projects}"
        "\n"
        r"\resumeItem{Built data reports with SQL and presented trends to stakeholders.}"
    )
    monkeypatch.setattr(
        resume_analyzer,
        "request_json",
        lambda *_: json.dumps({"document_body": tailored_body}),
    )
    result = resume_analyzer.tailor_resume_latex(
        "Built data reports with SQL.", SOURCE, JobAnalysis(), details()
    )
    assert result.startswith(r"\documentclass{article}")
    assert r"\newcommand{\resumeItem}[1]{\item #1}" in result
    assert (
        r"\resumeItem{Built data reports with SQL and presented trends to stakeholders.}"
        in result
    )
    assert result.endswith("% Original trailer comment\n")


@pytest.mark.parametrize(
    "document_body",
    [
        r"\input{secret.tex}",
        r"\begin{document}Injected document wrapper",
        r"\usepackage{untrusted}",
    ],
)
def test_rejects_unsafe_or_document_level_commands(
    monkeypatch: pytest.MonkeyPatch, document_body: str
) -> None:
    monkeypatch.setattr(
        resume_analyzer,
        "request_json",
        lambda *_: json.dumps({"document_body": document_body}),
    )
    with pytest.raises(ValueError):
        resume_analyzer.tailor_resume_latex(
            "Resume evidence.", SOURCE, JobAnalysis(), details()
        )


@pytest.mark.parametrize(
    ("original_section", "tailored_section"),
    [
        (
            r"\section{Projects}\href{https://example.com}{Portfolio}",
            r"\section{Projects}",
        ),
        (
            r"\section{Projects}",
            r"\section{Projects}\href{https://example.com}{Portfolio}",
        ),
    ],
)
def test_rejects_added_or_removed_template_urls(
    monkeypatch: pytest.MonkeyPatch,
    original_section: str,
    tailored_section: str,
) -> None:
    source = SOURCE.replace(r"\section{Projects}", original_section)
    monkeypatch.setattr(
        resume_analyzer,
        "request_json",
        lambda *_: json.dumps({"document_body": tailored_section}),
    )
    with pytest.raises(ValueError, match="resume URL"):
        resume_analyzer.tailor_resume_latex(
            "Resume evidence.", source, JobAnalysis(), details()
        )


def test_rejects_malformed_template_document_boundaries() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        resume_analyzer.tailor_resume_latex(
            "Resume evidence.",
            r"\documentclass{article}\begin{document}Text",
            JobAnalysis(),
            details(),
        )
