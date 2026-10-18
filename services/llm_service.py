from openai import NotFoundError, OpenAI

from config.settings import PROJECT_ROOT, settings


class LLMConfigurationError(RuntimeError):
    """LLM integration is unavailable until configured."""


def get_client() -> OpenAI:
    if not settings.groq_api_key:
        raise LLMConfigurationError(
            "GROQ_API_KEY is missing. Add your rotated key to "
            f"{PROJECT_ROOT / '.env'} (not .env.example), then restart Streamlit."
        )
    return OpenAI(
        api_key=settings.groq_api_key,
        base_url="https://api.groq.com/openai/v1",
        timeout=60.0,
        max_retries=2,
    )


def request_json(system_prompt: str, user_prompt: str) -> str:
    client = get_client()
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except NotFoundError as exc:
        raise LLMConfigurationError(
            f"Groq returned 404 for model '{settings.groq_model}'. The model may be "
            "retired or unavailable to this account. Update GROQ_MODEL in the project "
            ".env file to an active model listed in Groq Console, then restart Streamlit."
        ) from exc
    content = response.choices[0].message.content
    if not content:
        raise ValueError("The AI service returned an empty response.")
    return content
