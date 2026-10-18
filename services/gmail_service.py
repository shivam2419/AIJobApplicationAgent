from __future__ import annotations

import base64
import json
import logging
from email.message import EmailMessage
from pathlib import Path

import requests
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import fitz
import httplib2
from pydantic import EmailStr, TypeAdapter, ValidationError

from config.settings import settings

LOGGER = logging.getLogger(__name__)
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_IDENTITY_SCOPES = ("openid", "email")
GMAIL_SCOPES = [*GMAIL_IDENTITY_SCOPES, GMAIL_SEND_SCOPE]
_EMAIL_ADAPTER = TypeAdapter(EmailStr)


class GmailServiceError(RuntimeError):
    """An OAuth or Gmail API operation failed safely."""


def build_mime_message(
    recipient: str, subject: str, body: str, pdf_path: Path
) -> dict[str, str]:
    try:
        _EMAIL_ADAPTER.validate_python(recipient)
    except ValidationError as exc:
        raise GmailServiceError("Enter a valid recipient email address.") from exc
    if not subject.strip() or not body.strip():
        raise GmailServiceError("Email subject and body are required.")
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        raise GmailServiceError("The resume PDF attachment is missing or empty.")
    try:
        with fitz.open(pdf_path) as document:
            if document.is_encrypted or document.page_count < 1:
                raise GmailServiceError("The resume PDF attachment is invalid or unreadable.")
        with pdf_path.open("rb") as attachment:
            payload = attachment.read()
    except fitz.FileDataError as exc:
        raise GmailServiceError("The resume attachment is not a readable PDF.") from exc
    except OSError as exc:
        raise GmailServiceError("The resume attachment could not be read.") from exc
    try:
        message = EmailMessage()
        message["from"] = settings.gmail_expected_sender
        message["to"] = recipient
        message["subject"] = subject
        message.set_content(body)
        message.add_attachment(
            payload,
            maintype="application",
            subtype="pdf",
            filename=pdf_path.name,
        )
    except (OSError, ValueError) as exc:
        raise GmailServiceError("The resume attachment could not be encoded.") from exc
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    return {"raw": raw}


def _credentials() -> Credentials:
    if not settings.gmail_credentials_file.is_file():
        raise GmailServiceError(
            "Gmail OAuth is not configured. Add the Google OAuth client JSON at "
            f"{settings.gmail_credentials_file}."
        )
    creds = None
    if settings.gmail_token_file.is_file():
        try:
            token_info = json.loads(settings.gmail_token_file.read_text(encoding="utf-8"))
            stored_scopes = set(token_info.get("scopes", []))
            if set(GMAIL_SCOPES).issubset(stored_scopes):
                creds = Credentials.from_authorized_user_info(token_info, GMAIL_SCOPES)
        except (ValueError, OSError) as exc:
            raise GmailServiceError(
                "The saved Gmail authorization is invalid. Remove the token file and reauthorize."
            ) from exc
    try:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(settings.gmail_credentials_file), GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)
        settings.gmail_token_file.parent.mkdir(parents=True, exist_ok=True)
        settings.gmail_token_file.write_text(creds.to_json(), encoding="utf-8")
        return creds
    except (GoogleAuthError, OSError, ValueError) as exc:
        raise GmailServiceError(
            "Gmail authorization failed or was revoked. Check OAuth setup and reauthorize."
        ) from exc


def verify_sender_identity(credentials: Credentials) -> str:
    try:
        response = AuthorizedSession(credentials).get(
            "https://www.googleapis.com/oauth2/v2/userinfo", timeout=15
        )
        if response.status_code != 200:
            raise GmailServiceError(
                "Could not verify the authorized Gmail account. Reauthorize Gmail."
            )
        user_info = response.json()
    except GmailServiceError:
        raise
    except (
        GoogleAuthError,
        httplib2.HttpLib2Error,
        requests.exceptions.RequestException,
        OSError,
        TimeoutError,
    ) as exc:
        raise GmailServiceError(
            "Could not verify the authorized Gmail account because of an authorization "
            "or network error."
        ) from exc
    except ValueError as exc:
        raise GmailServiceError("Google returned invalid account identity data.") from exc
    actual_email = str(user_info.get("email", "")).strip().lower()
    if not actual_email or user_info.get("verified_email") is not True:
        raise GmailServiceError("Google did not return a verified sender email address.")
    if actual_email != settings.gmail_expected_sender:
        raise GmailServiceError(
            f"Authorized Gmail account is {actual_email}, but this app is configured "
            f"to send as {settings.gmail_expected_sender}. Authorize the correct account."
        )
    return actual_email


def send_email(
    recipient: str, subject: str, body: str, pdf_path: Path
) -> str:
    message = build_mime_message(recipient, subject, body, pdf_path)
    try:
        credentials = _credentials()
        verify_sender_identity(credentials)
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        result = service.users().messages().send(userId="me", body=message).execute()
    except GmailServiceError:
        raise
    except HttpError as exc:
        status = getattr(exc.resp, "status", None)
        try:
            error_body = json.loads(exc.content.decode("utf-8"))
            reasons = {
                item.get("reason", "")
                for item in error_body.get("error", {}).get("errors", [])
            }
        except (AttributeError, UnicodeDecodeError, ValueError):
            reasons = set()
        if status == 429 or reasons & {
            "rateLimitExceeded",
            "userRateLimitExceeded",
            "quotaExceeded",
        }:
            raise GmailServiceError(
                "Gmail quota or rate limit was reached. Wait before retrying."
            ) from exc
        if status in {401, 403}:
            raise GmailServiceError(
                "Gmail rejected authorization. Verify the OAuth consent and send permission, "
                "then reauthorize."
            ) from exc
        LOGGER.warning("Gmail API returned an HTTP error (status=%s).", status)
        raise GmailServiceError(
            "Gmail could not accept the message. Check authorization and try again."
        ) from exc
    except (
        GoogleAuthError,
        httplib2.HttpLib2Error,
        requests.exceptions.RequestException,
        OSError,
        TimeoutError,
    ) as exc:
        LOGGER.warning("Gmail operation failed: %s", type(exc).__name__)
        raise GmailServiceError(
            "Gmail authorization or network access failed. Check your connection and OAuth setup."
        ) from exc
    message_id = result.get("id")
    if not message_id:
        raise GmailServiceError("Gmail returned no message ID; send status is unconfirmed.")
    return str(message_id)
