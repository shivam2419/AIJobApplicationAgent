import base64
import json
from email import policy
from email.parser import BytesParser
from pathlib import Path
from types import SimpleNamespace

import fitz
import httplib2
import pytest
from googleapiclient.errors import HttpError

from services.gmail_service import GmailServiceError, build_mime_message
from services import gmail_service


def create_pdf(path: Path) -> None:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "resume")
    doc.save(path)
    doc.close()


def test_message_contains_pdf_attachment(tmp_path: Path) -> None:
    pdf_path = tmp_path / "resume.pdf"
    create_pdf(pdf_path)
    mime = build_mime_message("hr@example.com", "Application", "Hello", pdf_path)
    message = BytesParser(policy=policy.default).parsebytes(
        base64.urlsafe_b64decode(mime["raw"])
    )
    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_filename() == "resume.pdf"
    assert attachments[0].get_content_type() == "application/pdf"
    assert message["From"] == "officialshivam2419@gmail.com"


def test_rejects_invalid_recipient_and_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(b"not a PDF")
    with pytest.raises(GmailServiceError):
        build_mime_message("not-an-email", "Application", "Hello", pdf_path)
    with pytest.raises(GmailServiceError):
        build_mime_message("hr@example.com", "Application", "Hello", pdf_path)


def test_send_uses_gmail_api_and_returns_confirmed_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "resume.pdf"
    create_pdf(pdf_path)
    calls = []

    class Messages:
        def send(self, userId: str, body: dict[str, str]) -> "Messages":
            calls.append((userId, body))
            return self

        def execute(self) -> dict[str, str]:
            return {"id": "gmail-message-1"}

    class Users:
        def messages(self) -> Messages:
            return Messages()

    class Service:
        def users(self) -> Users:
            return Users()

    monkeypatch.setattr(gmail_service, "_credentials", lambda: object())
    monkeypatch.setattr(gmail_service, "verify_sender_identity", lambda _: "officialshivam2419@gmail.com")
    monkeypatch.setattr(gmail_service, "build", lambda *args, **kwargs: Service())
    message_id = gmail_service.send_email(
        "hr@example.com", "Application", "Hello", pdf_path
    )
    assert message_id == "gmail-message-1"
    assert calls[0][0] == "me"
    assert "raw" in calls[0][1]


def test_missing_oauth_file_is_reported_without_sending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        gmail_service,
        "settings",
        SimpleNamespace(gmail_credentials_file=tmp_path / "credentials.json"),
    )
    with pytest.raises(GmailServiceError, match="OAuth is not configured"):
        gmail_service._credentials()


def test_gmail_quota_errors_are_actionable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "resume.pdf"
    create_pdf(pdf_path)

    class Messages:
        def send(self, **kwargs: object) -> "Messages":
            return self

        def execute(self) -> dict[str, str]:
            response = httplib2.Response({"status": "403"})
            content = json.dumps(
                {"error": {"errors": [{"reason": "userRateLimitExceeded"}]}}
            ).encode()
            raise HttpError(response, content)

    class Users:
        def messages(self) -> Messages:
            return Messages()

    class Service:
        def users(self) -> Users:
            return Users()

    monkeypatch.setattr(gmail_service, "_credentials", lambda: object())
    monkeypatch.setattr(gmail_service, "verify_sender_identity", lambda _: "officialshivam2419@gmail.com")
    monkeypatch.setattr(gmail_service, "build", lambda *args, **kwargs: Service())
    with pytest.raises(GmailServiceError, match="quota or rate limit"):
        gmail_service.send_email("hr@example.com", "Application", "Hello", pdf_path)


def test_sender_identity_must_match_configured_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {
                "email": "someone-else@gmail.com",
                "verified_email": True,
            }

    class Session:
        @staticmethod
        def get(*args: object, **kwargs: object) -> Response:
            return Response()

    monkeypatch.setattr(gmail_service, "AuthorizedSession", lambda _: Session())
    monkeypatch.setattr(
        gmail_service,
        "settings",
        SimpleNamespace(gmail_expected_sender="officialshivam2419@gmail.com"),
    )
    with pytest.raises(GmailServiceError, match="configured to send as"):
        gmail_service.verify_sender_identity(object())  # type: ignore[arg-type]


def test_sender_mismatch_prevents_gmail_api_send(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "resume.pdf"
    create_pdf(pdf_path)
    api_calls = []
    monkeypatch.setattr(gmail_service, "_credentials", lambda: object())

    def reject_sender(_: object) -> str:
        raise GmailServiceError("sender mismatch")

    monkeypatch.setattr(gmail_service, "verify_sender_identity", reject_sender)
    monkeypatch.setattr(
        gmail_service,
        "build",
        lambda *args, **kwargs: api_calls.append((args, kwargs)),
    )
    with pytest.raises(GmailServiceError, match="sender mismatch"):
        gmail_service.send_email("hr@example.com", "Application", "Hello", pdf_path)
    assert not api_calls
