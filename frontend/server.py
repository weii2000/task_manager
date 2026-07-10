"""Serve the frontend and proxy API requests to the FastAPI development server."""

from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


FRONTEND_DIR = Path(__file__).resolve().parent
DEFAULT_API_TIMEOUT_SECONDS = 15
AGENT_API_TIMEOUT_SECONDS = 60


class FrontendHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, api_url: str, **kwargs):
        self.api_url = api_url.rstrip("/")
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self) -> None:
        if self.path.startswith("/api/"):
            self._proxy()
            return
        super().do_GET()

    def do_POST(self) -> None:
        self._proxy()

    def do_PUT(self) -> None:
        self._proxy()

    def do_PATCH(self) -> None:
        self._proxy()

    def do_DELETE(self) -> None:
        self._proxy()

    def _proxy(self) -> None:
        if not self.path.startswith("/api/"):
            self.send_error(404)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) if content_length else None
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in {"host", "content-length", "connection"}
        }
        request = Request(
            f"{self.api_url}{self.path}",
            data=body,
            headers=headers,
            method=self.command,
        )
        timeout = (
            AGENT_API_TIMEOUT_SECONDS
            if self.path.startswith("/api/agent/")
            else DEFAULT_API_TIMEOUT_SECONDS
        )

        try:
            with urlopen(request, timeout=timeout) as response:
                self._relay(response.status, response.headers, response.read())
        except HTTPError as error:
            self._relay(error.code, error.headers, error.read())
        except URLError:
            payload = b'{"detail":"Cannot connect to FastAPI. Start it on port 8000."}'
            self._relay(502, {"Content-Type": "application/json"}, payload)

    def _relay(self, status: int, headers, body: bytes) -> None:
        self.send_response(status)
        for key, value in headers.items():
            if key.lower() not in {
                "connection",
                "content-length",
                "content-encoding",
                "transfer-encoding",
            }:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Task Manager frontend")
    parser.add_argument("--port", type=int, default=5173)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--host", default="127.0.0.1") #
    args = parser.parse_args()

    def handler(*handler_args, **handler_kwargs):
        return FrontendHandler(
            *handler_args,
            api_url=args.api_url,
            **handler_kwargs,
        )

    # server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Frontend: http://127.0.0.1:{args.port}")
    print(f"API proxy: {args.api_url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
