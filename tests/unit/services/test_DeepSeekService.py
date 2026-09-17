import httpx
import pytest
from unittest.mock import MagicMock, patch

from services.DeepSeekService import (
    DEFAULT_DEEPSEEK_MAX_TOKENS,
    MAX_DEEPSEEK_TOKENS,
    DeepSeekService,
)


def _fake_client(json_data, raise_exc=None):
    """Build a MagicMock httpx.Client usable as a context manager."""
    response = MagicMock()
    response.json.return_value = json_data
    if raise_exc is not None:
        response.raise_for_status.side_effect = raise_exc
    else:
        response.raise_for_status.return_value = None

    client = MagicMock()
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    client.post.return_value = response
    return client


def _completion(content, finish_reason="stop"):
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ]
    }


class TestDeepSeekServiceConfiguration:
    def test_is_configured(self):
        assert DeepSeekService(api_key="sk-test").is_configured is True
        assert DeepSeekService(api_key="   ").is_configured is False
        assert DeepSeekService(api_key=None).is_configured is False

    def test_missing_api_key_raises(self):
        service = DeepSeekService(api_key=None)
        with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
            service.generate_chat(user_content="hello")


class TestDeepSeekServiceRequests:
    def test_request_structure(self):
        fake = _fake_client(_completion("Hello"))
        with patch("services.DeepSeekService.httpx.Client", return_value=fake) as client_cls:
            service = DeepSeekService(api_key="sk-test", model="deepseek-flash")
            content, truncated = service.generate_chat(user_content="User text", system_prompt="System text")

        assert content == "Hello"
        assert truncated is False
        client_cls.assert_called_once_with(timeout=180.0)

        args, post_kwargs = fake.post.call_args
        assert args[0] == "https://api.deepseek.com/chat/completions"
        assert post_kwargs["headers"]["Authorization"] == "Bearer sk-test"
        assert post_kwargs["headers"]["Content-Type"] == "application/json"
        payload = post_kwargs["json"]
        assert payload["model"] == "deepseek-flash"
        assert payload["messages"] == [
            {"role": "system", "content": "System text"},
            {"role": "user", "content": "User text"},
        ]
        assert "response_format" not in payload
        assert payload["max_tokens"] == DEFAULT_DEEPSEEK_MAX_TOKENS
        assert "thinking" not in payload

    def test_user_only_message_when_no_system_prompt(self):
        fake = _fake_client(_completion("ok"))
        with patch("services.DeepSeekService.httpx.Client", return_value=fake):
            service = DeepSeekService(api_key="sk-test")
            service.generate_chat(user_content="only user")
        assert fake.post.call_args.kwargs["json"]["messages"] == [{"role": "user", "content": "only user"}]

    def test_json_mode_sets_response_format(self):
        fake = _fake_client(_completion('{"ok": true}'))
        with patch("services.DeepSeekService.httpx.Client", return_value=fake):
            service = DeepSeekService(api_key="sk-test")
            result, _ = service.generate_chat(user_content="x", json_mode=True)
        assert result == '{"ok": true}'
        assert fake.post.call_args.kwargs["json"]["response_format"] == {"type": "json_object"}

    def test_explicit_max_tokens_honored(self):
        fake = _fake_client(_completion("ok"))
        with patch("services.DeepSeekService.httpx.Client", return_value=fake):
            service = DeepSeekService(api_key="sk-test")
            service.generate_chat(user_content="x", max_tokens=12345)
        assert fake.post.call_args.kwargs["json"]["max_tokens"] == 12345

    def test_service_level_max_tokens_used_by_default(self):
        fake = _fake_client(_completion("ok"))
        with patch("services.DeepSeekService.httpx.Client", return_value=fake):
            service = DeepSeekService(api_key="sk-test", max_tokens=20000)
            service.generate_chat(user_content="x")
        assert fake.post.call_args.kwargs["json"]["max_tokens"] == 20000

    def test_max_tokens_clamped_to_api_maximum(self):
        fake = _fake_client(_completion("ok"))
        with patch("services.DeepSeekService.httpx.Client", return_value=fake):
            service = DeepSeekService(api_key="sk-test")
            service.generate_chat(user_content="x", max_tokens=10_000_000)
        assert fake.post.call_args.kwargs["json"]["max_tokens"] == MAX_DEEPSEEK_TOKENS

    def test_custom_base_url_trailing_slash_stripped(self):
        fake = _fake_client(_completion("ok"))
        with patch("services.DeepSeekService.httpx.Client", return_value=fake):
            service = DeepSeekService(api_key="sk-test", base_url="https://custom.example.com/")
            service.generate_chat(user_content="x")
        assert fake.post.call_args.args[0] == "https://custom.example.com/chat/completions"

    def test_thinking_disabled_is_sent(self):
        fake = _fake_client(_completion("ok"))
        with patch("services.DeepSeekService.httpx.Client", return_value=fake):
            service = DeepSeekService(api_key="sk-test", thinking="disabled")
            service.generate_chat(user_content="x")
        assert fake.post.call_args.kwargs["json"]["thinking"] == {"type": "disabled"}

    def test_thinking_enabled_is_sent(self):
        fake = _fake_client(_completion("ok"))
        with patch("services.DeepSeekService.httpx.Client", return_value=fake):
            service = DeepSeekService(api_key="sk-test", thinking="enabled")
            service.generate_chat(user_content="x")
        assert fake.post.call_args.kwargs["json"]["thinking"] == {"type": "enabled"}

    def test_invalid_thinking_is_omitted(self):
        fake = _fake_client(_completion("ok"))
        with patch("services.DeepSeekService.httpx.Client", return_value=fake):
            service = DeepSeekService(api_key="sk-test", thinking="banana")
            service.generate_chat(user_content="x")
        assert "thinking" not in fake.post.call_args.kwargs["json"]
        assert service.thinking is None


class TestDeepSeekServiceResponses:
    def test_truncation_detected_on_length(self):
        fake = _fake_client(_completion('{"partial":', finish_reason="length"))
        with patch("services.DeepSeekService.httpx.Client", return_value=fake):
            service = DeepSeekService(api_key="sk-test")
            content, truncated = service.generate_chat(user_content="x", json_mode=True)
        assert truncated is True
        assert content == '{"partial":'

    def test_not_truncated_on_stop(self):
        fake = _fake_client(_completion("complete", finish_reason="stop"))
        with patch("services.DeepSeekService.httpx.Client", return_value=fake):
            service = DeepSeekService(api_key="sk-test")
            _, truncated = service.generate_chat(user_content="x")
        assert truncated is False

    def test_http_error_raises_runtime_error(self):
        request = httpx.Request("POST", "https://api.deepseek.com/chat/completions")
        response = httpx.Response(401, request=request, text="Invalid API key")
        error = httpx.HTTPStatusError("Unauthorized", request=request, response=response)
        fake = _fake_client({}, raise_exc=error)
        with patch("services.DeepSeekService.httpx.Client", return_value=fake):
            service = DeepSeekService(api_key="sk-test")
            with pytest.raises(RuntimeError, match=r"DeepSeek API error \(401\)"):
                service.generate_chat(user_content="x")

    def test_empty_choices_raises(self):
        fake = _fake_client({"choices": []})
        with patch("services.DeepSeekService.httpx.Client", return_value=fake):
            service = DeepSeekService(api_key="sk-test")
            with pytest.raises(RuntimeError, match="empty choices"):
                service.generate_chat(user_content="x")
