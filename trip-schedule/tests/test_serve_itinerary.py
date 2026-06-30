import json
import threading
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from serve_itinerary import RuntimeConfig, create_server


def test_runtime_config_requires_all_map_credentials(monkeypatch) -> None:
    monkeypatch.delenv("AMAP_SECURITY_KEY", raising=False)

    with pytest.raises(RuntimeError, match="AMAP_SECURITY_KEY"):
        RuntimeConfig.from_environment()


def test_server_binds_loopback_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AMAP_JSAPI_KEY", "js-key")
    monkeypatch.setenv("AMAP_SECURITY_KEY", "security-key")
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "web-key")

    server = create_server(tmp_path, port=0)

    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()


def start_server(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def configure_keys(monkeypatch) -> None:
    monkeypatch.setenv("AMAP_JSAPI_KEY", "js-key")
    monkeypatch.setenv("AMAP_SECURITY_KEY", "security-key")
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "web-key")


def test_runtime_config_endpoint_exposes_only_js_key(tmp_path, monkeypatch) -> None:
    configure_keys(monkeypatch)
    server = create_server(tmp_path, port=0)
    start_server(server)
    try:
        body = (
            urlopen(f"http://127.0.0.1:{server.server_port}/runtime-config")
            .read()
            .decode("utf-8")
        )
        assert json.loads(body) == {"amapJsApiKey": "js-key"}
        assert "security-key" not in body
        assert "web-key" not in body
    finally:
        server.shutdown()
        server.server_close()


def test_proxy_keeps_security_key_upstream_only(
    tmp_path,
    monkeypatch,
) -> None:
    configure_keys(monkeypatch)
    observed = {}

    class Response:
        status_code = 200
        content = b'{"ok":true}'
        headers = {"Content-Type": "application/json"}

    def fake_get(url, *, timeout):
        observed["url"] = url
        return Response()

    monkeypatch.setattr("serve_itinerary.requests.get", fake_get)
    server = create_server(tmp_path, port=0)
    start_server(server)
    try:
        body = (
            urlopen(
                f"http://127.0.0.1:{server.server_port}"
                "/_AMapService/v3/test?value=1"
            )
            .read()
            .decode("utf-8")
        )
        assert "security-key" in observed["url"]
        assert "security-key" not in body
    finally:
        server.shutdown()
        server.server_close()


def test_static_handler_cannot_escape_itinerary_directory(
    tmp_path,
    monkeypatch,
) -> None:
    configure_keys(monkeypatch)
    root = tmp_path / "trip"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    server = create_server(root, port=0)
    start_server(server)
    try:
        with pytest.raises(HTTPError) as exc_info:
            urlopen(f"http://127.0.0.1:{server.server_port}/../secret.txt")
        assert exc_info.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
