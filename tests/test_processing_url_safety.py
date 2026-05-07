from __future__ import annotations

import socket

import pytest

from aily.processing.router import UnsafeURLError, _validate_public_http_url


pytestmark = pytest.mark.contract


@pytest.mark.asyncio
async def test_validate_public_http_url_rejects_localhost() -> None:
    with pytest.raises(UnsafeURLError):
        await _validate_public_http_url("http://localhost:8000/private")


@pytest.mark.asyncio
async def test_validate_public_http_url_allows_private_network_only_when_explicitly_enabled(monkeypatch) -> None:
    from aily.config import SETTINGS

    monkeypatch.setattr(SETTINGS, "url_intake_allow_private_network", True)

    assert await _validate_public_http_url("http://127.0.0.1:8000/local-fixture") is None


@pytest.mark.asyncio
async def test_validate_public_http_url_never_allows_cloud_metadata(monkeypatch) -> None:
    from aily.config import SETTINGS

    monkeypatch.setattr(SETTINGS, "url_intake_allow_private_network", True)

    with pytest.raises(UnsafeURLError):
        await _validate_public_http_url("http://169.254.169.254/latest/meta-data/")


@pytest.mark.asyncio
async def test_validate_public_http_url_rejects_private_dns(monkeypatch) -> None:
    def fake_getaddrinfo(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.5", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(UnsafeURLError):
        await _validate_public_http_url("https://internal.example.test")


@pytest.mark.asyncio
async def test_validate_public_http_url_allows_public_dns(monkeypatch) -> None:
    def fake_getaddrinfo(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    assert await _validate_public_http_url("https://example.com/article") is None


def test_url_with_host_pins_request_to_validated_address() -> None:
    from aily.processing.router import _host_header, _response_peer_address, _url_with_host
    from urllib.parse import urlparse

    original = "https://example.com:8443/path?q=1"

    assert _url_with_host(original, "93.184.216.34") == "https://93.184.216.34:8443/path?q=1"
    assert _host_header(urlparse(original)) == "example.com:8443"

    class ServerAddrStream:
        def get_extra_info(self, name):
            if name == "server_addr":
                return ("93.184.216.34", 443)
            return None

    class Response:
        extensions = {"network_stream": ServerAddrStream()}

    assert _response_peer_address(Response()) == "93.184.216.34"


@pytest.mark.asyncio
async def test_process_url_rejects_private_connected_peer(monkeypatch) -> None:
    from unittest.mock import AsyncMock, MagicMock

    import httpx

    from aily.processing.router import ProcessingRouter

    class PrivatePeerStream:
        def get_extra_info(self, name):
            if name == "peername":
                return ("10.0.0.5", 443)
            return None

    async def aiter_bytes():
        raise AssertionError("body must not be read from private peer")
        yield b""

    response = AsyncMock()
    response.extensions = {"network_stream": PrivatePeerStream()}
    response.headers = {"content-type": "text/plain"}
    response.is_redirect = False
    response.raise_for_status = MagicMock()
    response.aiter_bytes = aiter_bytes

    stream = AsyncMock()
    stream.__aenter__ = AsyncMock(return_value=response)
    stream.__aexit__ = AsyncMock(return_value=False)
    client = AsyncMock()
    client.stream = MagicMock(return_value=stream)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr("aily.processing.router._public_addresses_for_url", AsyncMock(return_value=["93.184.216.34"]))
    monkeypatch.setattr(httpx, "AsyncClient", MagicMock(return_value=client))

    result = await ProcessingRouter().process_url("https://example.com/private")

    httpx.AsyncClient.assert_called_once_with(follow_redirects=False, timeout=30, trust_env=False)
    assert "non-public address" in result.text


@pytest.mark.asyncio
async def test_process_url_fails_closed_when_peer_cannot_be_verified(monkeypatch) -> None:
    from unittest.mock import AsyncMock, MagicMock

    import httpx

    from aily.processing.router import ProcessingRouter

    class UnknownPeerStream:
        def get_extra_info(self, name):
            return None

    async def aiter_bytes():
        raise AssertionError("body must not be read when peer is unknown")
        yield b""

    response = AsyncMock()
    response.extensions = {"network_stream": UnknownPeerStream()}
    response.headers = {"content-type": "text/plain"}
    response.is_redirect = False
    response.raise_for_status = MagicMock()
    response.aiter_bytes = aiter_bytes

    stream = AsyncMock()
    stream.__aenter__ = AsyncMock(return_value=response)
    stream.__aexit__ = AsyncMock(return_value=False)
    client = AsyncMock()
    client.stream = MagicMock(return_value=stream)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    monkeypatch.setattr("aily.processing.router._public_addresses_for_url", AsyncMock(return_value=["93.184.216.34"]))
    monkeypatch.setattr(httpx, "AsyncClient", MagicMock(return_value=client))

    result = await ProcessingRouter().process_url("https://example.com/private")

    assert "peer could not be verified" in result.text
