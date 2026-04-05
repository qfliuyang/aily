from unittest.mock import MagicMock

from aily.browser.subprocess_worker import _run_loop


def test_run_loop_fetch():
    mock_conn = MagicMock()
    mock_conn.recv.side_effect = [
        {"type": "fetch", "url": "http://example.com", "timeout": 10},
        {"type": "shutdown"},
    ]
    mock_listener = MagicMock()
    mock_listener.accept.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_listener.accept.return_value.__exit__ = MagicMock(return_value=False)

    fetch_fn = MagicMock(return_value="hello")

    _run_loop(mock_listener, fetch_fn)

    fetch_fn.assert_called_once_with("http://example.com", 10)
    mock_conn.send.assert_any_call({"status": "ok", "text": "hello"})
    mock_conn.send.assert_any_call({"status": "ok"})


def test_run_loop_fetch_error():
    mock_conn = MagicMock()
    mock_conn.recv.side_effect = [
        {"type": "fetch", "url": "http://bad.com", "timeout": 10},
        {"type": "shutdown"},
    ]
    mock_listener = MagicMock()
    mock_listener.accept.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_listener.accept.return_value.__exit__ = MagicMock(return_value=False)

    fetch_fn = MagicMock(side_effect=RuntimeError("fetch failed"))

    _run_loop(mock_listener, fetch_fn)

    mock_conn.send.assert_any_call({"status": "error", "message": "fetch failed"})


def test_run_loop_unknown_type():
    mock_conn = MagicMock()
    mock_conn.recv.side_effect = [
        {"type": "unknown"},
        {"type": "shutdown"},
    ]
    mock_listener = MagicMock()
    mock_listener.accept.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_listener.accept.return_value.__exit__ = MagicMock(return_value=False)

    _run_loop(mock_listener, lambda u, t: "")

    mock_conn.send.assert_any_call({"status": "error", "message": "Unknown type"})
