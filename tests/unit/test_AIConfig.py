import pytest

from app import depends
from services.DeepSeekService import DEFAULT_DEEPSEEK_MAX_TOKENS


@pytest.fixture
def env_config():
    """Use the (mutable) depends config dict as a controlled environment."""
    saved = dict(depends.config)
    depends.config["init"] = True
    yield depends.config
    depends.config.clear()
    depends.config.update(saved)


class TestDefaultAIProvider:
    def test_explicit_provider_wins(self, env_config):
        env_config["AI_PROVIDER"] = "deepseek"
        env_config["GEMINI_API_KEY"] = "g"
        assert depends.get_default_ai_provider() == "deepseek"

    def test_falls_back_to_gemini_when_only_gemini_key(self, env_config):
        for key in ("AI_PROVIDER", "DEEPSEEK_API_KEY"):
            env_config.pop(key, None)
        env_config["GEMINI_API_KEY"] = "g"
        assert depends.get_default_ai_provider() == "gemini"

    def test_falls_back_to_deepseek_when_only_deepseek_key(self, env_config):
        for key in ("AI_PROVIDER", "GEMINI_API_KEY"):
            env_config.pop(key, None)
        env_config["DEEPSEEK_API_KEY"] = "d"
        assert depends.get_default_ai_provider() == "deepseek"

    def test_defaults_to_gemini_without_keys(self, env_config):
        for key in ("AI_PROVIDER", "GEMINI_API_KEY", "DEEPSEEK_API_KEY"):
            env_config.pop(key, None)
        assert depends.get_default_ai_provider() == "gemini"


class TestGetAIConfig:
    def test_reports_providers_and_default(self, env_config):
        env_config["AI_PROVIDER"] = "deepseek"
        env_config["GEMINI_API_KEY"] = "g"
        env_config["DEEPSEEK_API_KEY"] = "d"
        env_config["GEMINI_MODEL"] = "gemini-x"
        env_config["DEEPSEEK_MODEL"] = "deepseek-flash"

        config = depends.get_ai_config()
        by_id = {p["id"]: p for p in config["providers"]}

        assert config["default_provider"] == "deepseek"
        assert by_id["gemini"]["configured"] is True
        assert by_id["gemini"]["model"] == "gemini-x"
        assert by_id["deepseek"]["configured"] is True
        assert by_id["deepseek"]["model"] == "deepseek-flash"

    def test_marks_missing_keys_unconfigured(self, env_config):
        env_config.pop("GEMINI_API_KEY", None)
        env_config.pop("DEEPSEEK_API_KEY", None)

        by_id = {p["id"]: p for p in depends.get_ai_config()["providers"]}

        assert by_id["gemini"]["configured"] is False
        assert by_id["deepseek"]["configured"] is False


class TestGetDeepSeekServiceConfig:
    def test_max_tokens_and_thinking_from_config(self, env_config):
        env_config["DEEPSEEK_API_KEY"] = "d"
        env_config["DEEPSEEK_MAX_TOKENS"] = "50000"
        env_config["DEEPSEEK_THINKING"] = "enabled"

        service = depends.get_deepseek_service()

        assert service.max_tokens == 50000
        assert service.thinking == "enabled"

    def test_defaults_disable_thinking(self, env_config):
        env_config["DEEPSEEK_API_KEY"] = "d"
        env_config.pop("DEEPSEEK_MAX_TOKENS", None)
        env_config.pop("DEEPSEEK_THINKING", None)

        service = depends.get_deepseek_service()

        assert service.max_tokens == DEFAULT_DEEPSEEK_MAX_TOKENS
        assert service.thinking == "disabled"

    def test_thinking_default_keyword_uses_api_default(self, env_config):
        env_config["DEEPSEEK_API_KEY"] = "d"
        env_config["DEEPSEEK_THINKING"] = "default"

        assert depends.get_deepseek_service().thinking is None

    def test_invalid_values_fall_back(self, env_config):
        env_config["DEEPSEEK_API_KEY"] = "d"
        env_config["DEEPSEEK_MAX_TOKENS"] = "not-a-number"
        env_config["DEEPSEEK_THINKING"] = "banana"

        service = depends.get_deepseek_service()

        assert service.max_tokens == DEFAULT_DEEPSEEK_MAX_TOKENS
        assert service.thinking is None
