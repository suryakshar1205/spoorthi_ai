from __future__ import annotations

from app.config import Settings
from app.services.auth_service import AuthService
from app.services.llm_service import LLMService, LocalProvider, OllamaProvider, OpenAIProvider


def test_auth_service_validates_credentials() -> None:
    settings = Settings(admin_username="spoorthi", admin_password="secure-pass")
    service = AuthService(settings)

    assert service.verify_credentials("spoorthi", "secure-pass") is True
    assert service.verify_credentials("spoorthi", "wrong-pass") is False
    assert service.verify_credentials("unknown", "secure-pass") is False


def test_llm_service_switches_provider_from_config() -> None:
    openai_service = LLMService(Settings(llm_provider="openai"))
    ollama_service = LLMService(Settings(llm_provider="ollama"))
    local_service = LLMService(Settings(llm_provider="local"))

    assert isinstance(openai_service.provider, OpenAIProvider)
    assert isinstance(ollama_service.provider, OllamaProvider)
    assert isinstance(local_service.provider, LocalProvider)
