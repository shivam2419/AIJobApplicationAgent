from pathlib import Path
from types import SimpleNamespace

import pytest

from models.application import ApplicationStatus, JobDetails
from services import application_service


def test_database_persistence_and_duplicate_send_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        application_service,
        "settings",
        SimpleNamespace(database_path=tmp_path / "applications.db", ensure_directories=lambda: None),
    )
    details = JobDetails(
        job_title="Engineer",
        company_name="Example",
        job_description="Build and maintain useful Python services for customers.",
        hr_email="hr@example.com",
    )
    record = application_service.create_application(details, "resume")
    record = application_service.update_status(
        record, ApplicationStatus.AWAITING_APPROVAL, pdf_filename="resume_tailored.pdf"
    )
    assert application_service.claim_email_send(record)
    assert not application_service.claim_email_send(record)
    persisted = application_service.list_applications()[0]
    assert persisted.application_id == record.application_id
    assert persisted.email_status == ApplicationStatus.SENDING
    assert persisted.pdf_filename == "resume_tailored.pdf"


def test_success_status_is_saved_only_as_explicit_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        application_service,
        "settings",
        SimpleNamespace(database_path=tmp_path / "applications.db", ensure_directories=lambda: None),
    )
    details = JobDetails(
        job_title="Engineer",
        company_name="Example",
        job_description="Build and maintain useful Python services for customers.",
        hr_email="hr@example.com",
    )
    record = application_service.create_application(details, "resume")
    assert application_service.list_applications()[0].email_status == ApplicationStatus.DRAFT_CREATED
    application_service.update_status(
        record, ApplicationStatus.EMAIL_SENT, gmail_message_id="message-123"
    )
    assert application_service.list_applications()[0].gmail_message_id == "message-123"
