from pathlib import Path

import fitz
import pytest
from types import SimpleNamespace

from models.application import ApplicationStatus, JobDetails
from services import application_service
from ui import new_application


def create_pdf(path: Path) -> None:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "resume")
    doc.save(path)
    doc.close()


def test_duplicate_send_is_prevented_after_success(
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
        record, ApplicationStatus.AWAITING_APPROVAL
    )
    pdf_path = tmp_path / "resume.pdf"
    create_pdf(pdf_path)
    workflow = {
        "record": record.model_dump(mode="json"),
        "send_in_progress": False,
    }
    sent = []
    monkeypatch.setattr(
        new_application,
        "send_email",
        lambda *args: (sent.append(args) or "gmail-message-id"),
    )
    new_application._send_reviewed_email(
        workflow,
        "hr@example.com",
        "Application",
        "Approved message",
        pdf_path,
    )
    new_application._send_reviewed_email(
        workflow,
        "hr@example.com",
        "Application",
        "Approved message",
        pdf_path,
    )
    assert len(sent) == 1
    persisted = application_service.list_applications()[0]
    assert persisted.email_status == ApplicationStatus.EMAIL_SENT
    assert persisted.gmail_message_id == "gmail-message-id"
