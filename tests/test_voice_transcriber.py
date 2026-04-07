import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from aily.voice.transcriber import WhisperTranscriber, TranscriptionError


@pytest.fixture
async def transcriber():
    t = WhisperTranscriber(api_key="test_key", model="whisper-1")
    yield t
    await t.close()


@pytest.mark.asyncio
async def test_transcribe_success(tmp_path):
    transcriber = WhisperTranscriber(api_key="test_key")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "text": "This is a test transcription",
        "language": "en",
        "duration": 5.2,
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(transcriber._client, "post", return_value=mock_response):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio content")

        result = await transcriber.transcribe(audio_file)

        assert result.text == "This is a test transcription"
        assert result.language == "en"
        assert result.duration_seconds == 5.2

    await transcriber.close()


@pytest.mark.asyncio
async def test_transcribe_empty_result(tmp_path):
    transcriber = WhisperTranscriber(api_key="test_key")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "text": "",
        "language": None,
        "duration": None,
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(transcriber._client, "post", return_value=mock_response):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        result = await transcriber.transcribe(audio_file)
        assert result.text == ""

    await transcriber.close()


@pytest.mark.asyncio
async def test_transcribe_with_prompt(tmp_path):
    transcriber = WhisperTranscriber(api_key="test_key")

    mock_response = MagicMock()
    mock_response.json.return_value = {"text": "Hello world"}
    mock_response.raise_for_status = MagicMock()

    with patch.object(transcriber._client, "post", return_value=mock_response) as mock_post:
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        await transcriber.transcribe(audio_file, prompt="Technology terms")

        # Verify prompt was included in request
        call_args = mock_post.call_args
        assert "data" in call_args.kwargs
        assert call_args.kwargs["data"]["prompt"] == "Technology terms"

    await transcriber.close()


@pytest.mark.asyncio
async def test_transcribe_api_error(tmp_path):
    transcriber = WhisperTranscriber(api_key="test_key")

    from httpx import HTTPStatusError, Response

    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 401
    mock_response.text = "Invalid API key"
    mock_response.raise_for_status.side_effect = HTTPStatusError(
        "Unauthorized", request=MagicMock(), response=mock_response
    )

    with patch.object(transcriber._client, "post", return_value=mock_response):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_text("fake audio")

        with pytest.raises(TranscriptionError, match="Whisper API error: 401"):
            await transcriber.transcribe(audio_file)

    await transcriber.close()


@pytest.mark.asyncio
async def test_transcribe_file_not_found():
    transcriber = WhisperTranscriber(api_key="test_key")

    # FileNotFoundError gets wrapped in TranscriptionError
    with pytest.raises(TranscriptionError):
        await transcriber.transcribe(Path("/nonexistent/file.mp3"))

    await transcriber.close()


@pytest.mark.asyncio
async def test_close_client():
    transcriber = WhisperTranscriber(api_key="test_key")

    with patch.object(transcriber._client, "aclose") as mock_close:
        await transcriber.close()
        mock_close.assert_called_once()
