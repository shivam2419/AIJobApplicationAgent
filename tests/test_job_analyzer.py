import pytest

from models.application import JobDetails
from services import job_analyzer


def test_job_analyzer_validates_structured_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        job_analyzer,
        "request_json",
        lambda *_: '{"job_title":"Engineer","required_technical_skills":["Python"]}',
    )
    result = job_analyzer.analyze_job(
        JobDetails(
            job_title="Engineer",
            company_name="Example",
            job_description="Build and maintain useful Python services for customers.",
            hr_email="hr@example.com",
        )
    )
    assert result.job_title == "Engineer"
    assert result.required_technical_skills == ["Python"]


def test_job_analyzer_rejects_invalid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(job_analyzer, "request_json", lambda *_: "not json")
    details = JobDetails(
        job_title="Engineer",
        company_name="Example",
        job_description="Build and maintain useful Python services for customers.",
        hr_email="hr@example.com",
    )
    with pytest.raises(ValueError):
        job_analyzer.analyze_job(details)
