from unittest.mock import MagicMock, patch

from desktop.llm_adapter import LLMAdapter


def test_llm_disabled_returns_none():
    config = MagicMock()
    config.get_llm_config.return_value = {"enabled": False}
    adapter = LLMAdapter(config)
    assert adapter.enhance({}) is None


def test_llm_with_mock_response():
    config = MagicMock()
    config.get_llm_config.return_value = {
        "enabled": True,
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "test-key",
        "model": "deepseek-chat",
    }
    adapter = LLMAdapter(config)
    with patch("httpx.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "增强解读"}}]
        }
        result = adapter.enhance({"stock_code": "600519", "verdict": "观察"})
    assert result == "增强解读"


def test_llm_missing_api_key_returns_none():
    config = MagicMock()
    config.get_llm_config.return_value = {
        "enabled": True,
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "model": "deepseek-chat",
    }
    adapter = LLMAdapter(config)
    assert adapter.enhance({"stock_code": "600519"}) is None


def test_llm_http_error_returns_none():
    config = MagicMock()
    config.get_llm_config.return_value = {
        "enabled": True,
        "api_key": "test-key",
    }
    adapter = LLMAdapter(config)
    with patch("httpx.post") as mock_post:
        mock_post.side_effect = RuntimeError("connection failed")
        result = adapter.enhance({"stock_code": "600519"})
    assert result is None
