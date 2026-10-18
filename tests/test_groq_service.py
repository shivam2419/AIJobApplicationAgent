from types import SimpleNamespace

import httpx
import pytest
from openai import NotFoundError

from services import llm_service
from services.llm_service import LLMConfigurationError


def test_groq_client_uses_configured_api_key_and_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_openai(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(llm_service, "OpenAI", fake_openai)
    monkeypatch.setattr(
        llm_service,
        "settings",
        SimpleNamespace(groq_api_key="groq-test-key"),
    )
    llm_service.get_client()
    assert captured == {
        "api_key": "groq-test-key",
        "base_url": "https://api.groq.com/openai/v1",
        "timeout": 60.0,
        "max_retries": 2,
    }


def test_groq_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_service,
        "settings",
        SimpleNamespace(groq_api_key=""),
    )
    with pytest.raises(LLMConfigurationError, match="GROQ_API_KEY"):
        llm_service.get_client()


def test_retired_model_404_is_explained(monkeypatch: pytest.MonkeyPatch) -> None:
    response = httpx.Response(
        404, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    )
    not_found = NotFoundError(
        "model not found",
        response=response,
        body={"error": {"message": "model not found"}},
    )

    class Completions:
        @staticmethod
        def create(**_: object) -> object:
            raise not_found

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=Completions())
    )
    monkeypatch.setattr(llm_service, "get_client", lambda: fake_client)
    monkeypatch.setattr(
        llm_service,
        "settings",
        SimpleNamespace(groq_model="retired-model"),
    )
    with pytest.raises(LLMConfigurationError, match="retired or unavailable"):
        llm_service.request_json("system", "user")
