import pytest
from unittest.mock import patch, MagicMock
import httpx

from aily.llm.client import LLMClient, LLMError


@pytest.fixture
def client():
    return LLMClient(api_key="test-key")


@pytest.mark.asyncio
async def test_chat_success(client):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "hello"}}]
    }
    mock_resp.raise_for_status = MagicMock()

    async def mock_post(*args, **kwargs):
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        result = await client.chat([{"role": "user", "content": "hi"}])
        assert result == "hello"


@pytest.mark.asyncio
async def test_chat_timeout_retries_then_raises(client):
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("timeout")):
        with pytest.raises(LLMError) as exc_info:
            await client.chat([{"role": "user", "content": "hi"}])
        assert "failed after" in str(exc_info.value)


@pytest.mark.asyncio
async def test_chat_json_malformed_then_repaired(client):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "{\"key\": \"value"}}]
    }
    mock_resp.raise_for_status = MagicMock()

    async def mock_post(*args, **kwargs):
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        with patch("asyncio.to_thread", return_value='{"key": "value"}'):
            result = await client.chat_json([{"role": "user", "content": "hi"}])
            assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_chat_json_repair_fails_raises_llm_error(client):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "not json"}}]
    }
    mock_resp.raise_for_status = MagicMock()

    async def mock_post(*args, **kwargs):
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        with patch("asyncio.to_thread", return_value="still not json"):
            with pytest.raises(LLMError, match="Could not parse or repair"):
                await client.chat_json([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_kimi_k25_omits_temperature_and_disables_thinking_when_requested():
    client = LLMClient(api_key="test-key", model="kimi-k2.5", thinking=False)

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "hello"}}]
    }
    mock_resp.raise_for_status = MagicMock()

    captured = {}

    async def mock_post(*args, **kwargs):
        captured.update(kwargs)
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        result = await client.chat([{"role": "user", "content": "hi"}], temperature=0.2)

    assert result == "hello"
    assert "temperature" not in captured["json"]
    assert captured["json"]["thinking"] == {"type": "disabled"}


@pytest.mark.asyncio
async def test_kimi_k2_thinking_enables_thinking_payload():
    client = LLMClient(api_key="test-key", model="kimi-k2-thinking", thinking=True)

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "hello"}}]
    }
    mock_resp.raise_for_status = MagicMock()

    captured = {}

    async def mock_post(*args, **kwargs):
        captured.update(kwargs)
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        result = await client.chat([{"role": "user", "content": "hi"}], temperature=1.0)

    assert result == "hello"
    assert captured["json"]["temperature"] == 1.0
    assert captured["json"]["thinking"] == {"type": "enabled"}
