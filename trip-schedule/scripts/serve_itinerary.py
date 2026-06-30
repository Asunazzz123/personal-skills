from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests


@dataclass(frozen=True)
class RuntimeConfig:
    js_api_key: str
    security_key: str
    webservice_key: str

    @classmethod
    def from_environment(cls) -> RuntimeConfig:
        values = {
            "AMAP_JSAPI_KEY": os.getenv("AMAP_JSAPI_KEY"),
            "AMAP_SECURITY_KEY": os.getenv("AMAP_SECURITY_KEY"),
            "AMAP_WEBSERVICE_KEY": os.getenv("AMAP_WEBSERVICE_KEY"),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")
        return cls(
            js_api_key=values["AMAP_JSAPI_KEY"],
            security_key=values["AMAP_SECURITY_KEY"],
            webservice_key=values["AMAP_WEBSERVICE_KEY"],
        )


class ItineraryHandler(SimpleHTTPRequestHandler):
    runtime_config: RuntimeConfig

    def do_GET(self) -> None:
        if self.path == "/runtime-config":
            body = json.dumps(
                {"amapJsApiKey": self.runtime_config.js_api_key}
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/_AMapService/"):
            self._proxy_amap()
            return
        super().do_GET()

    def _proxy_amap(self) -> None:
        split = urlsplit(self.path)
        upstream_path = split.path.removeprefix("/_AMapService")
        query = dict(parse_qsl(split.query, keep_blank_values=True))
        query["jscode"] = self.runtime_config.security_key
        upstream = urlunsplit(
            ("https", "restapi.amap.com", upstream_path, urlencode(query), "")
        )
        response = requests.get(upstream, timeout=20)
        body = response.content
        self.send_response(response.status_code)
        self.send_header(
            "Content-Type",
            response.headers.get("Content-Type", "application/json"),
        )
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(directory: Path, *, port: int) -> ThreadingHTTPServer:
    config = RuntimeConfig.from_environment()

    class BoundItineraryHandler(ItineraryHandler):
        runtime_config = config

    def handler(*args, **kwargs):
        return BoundItineraryHandler(
            *args,
            directory=str(directory.resolve()),
            **kwargs,
        )

    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = create_server(args.directory.resolve(), port=args.port)
    print(f"http://127.0.0.1:{server.server_port}/itinerary.html")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
