import pytest
from unittest.mock import patch, MagicMock

from aily.browser.manager import BrowserUseManager, BrowserFetchError


@pytest.fixture
def manager(tmp_path):
    return BrowserUseManager(profile_dir=tmp_path / "browser_profile")


def _mock_popen_ready(port: int = 12345):
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.stdout.readline.return_value = f"READY {port}\n"
    mock_proc.stderr = None
    return mock_proc


def _patch_client(mock_conn):
    mock_client_cls = MagicMock()
    mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
    return patch("aily.browser.manager.Client", mock_client_cls)


@pytest.mark.asyncio
async def test_start_spawns_subprocess(manager):
    mock_proc = _mock_popen_ready()
    with patch("aily.browser.manager.subprocess.Popen", return_value=mock_proc) as mock_popen_cls:
        await manager.start()
        mock_popen_cls.assert_called_once()
        assert manager._port == 12345


@pytest.mark.asyncio
async def test_fetch_returns_text(manager):
    mock_proc = _mock_popen_ready()
    mock_conn = MagicMock()
    mock_conn.recv.return_value = {"status": "ok", "text": "hello world"}

    with patch("aily.browser.manager.subprocess.Popen", return_value=mock_proc):
        with _patch_client(mock_conn):
            await manager.start()
            result = await manager.fetch("http://example.com")
            assert result == "hello world"


@pytest.mark.asyncio
async def test_fetch_retries_after_subprocess_crash(manager):
    mock_proc = _mock_popen_ready()
    mock_conn = MagicMock()
    mock_conn.recv.side_effect = [ConnectionResetError("crash"), {"status": "ok", "text": "recovered"}]

    with patch("aily.browser.manager.subprocess.Popen", return_value=mock_proc) as mock_popen_cls:
        with _patch_client(mock_conn):
            await manager.start()
            result = await manager.fetch("http://example.com")
            assert result == "recovered"
            assert mock_popen_cls.call_count == 2


@pytest.mark.asyncio
async def test_fetch_raises_after_two_crashes(manager):
    mock_proc = _mock_popen_ready()
    mock_conn = MagicMock()
    mock_conn.recv.side_effect = ConnectionResetError("crash")

    with patch("aily.browser.manager.subprocess.Popen", return_value=mock_proc) as mock_popen_cls:
        with _patch_client(mock_conn):
            await manager.start()
            with pytest.raises(BrowserFetchError) as exc_info:
                await manager.fetch("http://example.com")
            assert "crashed" in str(exc_info.value)
            assert mock_popen_cls.call_count == 2


@pytest.mark.asyncio
async def test_fetch_raises_on_error_response(manager):
    mock_proc = _mock_popen_ready()
    mock_conn = MagicMock()
    mock_conn.recv.return_value = {"status": "error", "message": "page not found"}

    with patch("aily.browser.manager.subprocess.Popen", return_value=mock_proc):
        with _patch_client(mock_conn):
            await manager.start()
            with pytest.raises(BrowserFetchError) as exc_info:
                await manager.fetch("http://example.com")
            assert "page not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_start_raises_on_bad_ready_line(manager):
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.stdout.readline.return_value = "ERROR\n"
    mock_proc.stderr.read.return_value = "crash log"

    with patch("aily.browser.manager.subprocess.Popen", return_value=mock_proc):
        with pytest.raises(BrowserFetchError, match="failed to start"):
            await manager.start()
        mock_proc.kill.assert_called_once()
