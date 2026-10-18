import pytest

from models.application import JobDetails
from models.job_analysis import JobAnalysis
from services import email_generator


def test_generates_validated_editable_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        email_generator,
        "request_json",
        lambda *_: '{"subject":"Application for Engineer","body":"Dear team, I am Ada Lovelace, a Python developer, and my experience is a good fit. Please find my resume attached."}',
    )
    result = email_generator.generate_email(
        JobDetails(
            job_title="Engineer",
            company_name="Example",
            job_description="Build and maintain useful Python services for customers.",
            hr_email="hr@example.com",
            hr_name="Jordan",
        ),
        JobAnalysis(),
        "Python developer",
        "Ada Lovelace",
    )
    assert result.subject.startswith("Application")
    assert "attached" in result.body


def test_rejects_unsupported_skill_in_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        email_generator,
        "request_json",
        lambda *_: '{"subject":"Application","body":"I am Ada Lovelace, experienced with Kubernetes. My resume is attached."}',
    )
    details = JobDetails(
        job_title="Engineer",
        company_name="Example",
        job_description="Build useful services for customers.",
        hr_email="hr@example.com",
    )
    with pytest.raises(ValueError, match="not supported"):
        email_generator.generate_email(
            details,
            JobAnalysis(required_technical_skills=["Kubernetes"]),
            "Python developer",
            "Ada Lovelace",
        )
