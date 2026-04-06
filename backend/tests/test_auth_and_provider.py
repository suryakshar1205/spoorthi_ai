from __future__ import annotations

from app.config import Settings
from app.services.auth_service import AuthService
from app.services.llm_service import LLMService, LocalProvider


def test_auth_service_validates_credentials() -> None:
    settings = Settings(admin_username="spoorthi", admin_password="secure-pass")
    service = AuthService(settings)

    assert service.verify_credentials("spoorthi", "secure-pass") is True
    assert service.verify_credentials("spoorthi", "wrong-pass") is False
    assert service.verify_credentials("unknown", "secure-pass") is False


def test_llm_service_always_uses_local_provider() -> None:
    default_service = LLMService(Settings())
    overridden_service = LLMService(Settings(llm_provider="remote"))
    local_service = LLMService(Settings(llm_provider="local"))

    assert isinstance(default_service.local_provider, LocalProvider)
    assert isinstance(overridden_service.local_provider, LocalProvider)
    assert isinstance(local_service.local_provider, LocalProvider)
    assert default_service.settings.llm_provider == "local"
    assert overridden_service.settings.llm_provider == "local"
