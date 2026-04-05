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
