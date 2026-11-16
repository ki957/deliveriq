"""Small exact-host HTTPS CONNECT proxy for the Builder Agent network."""

from __future__ import annotations

import json
import select
import socket
import socketserver
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

GITHUB_HOSTS = frozenset(
    {
        "api.github.com",
        "codeload.github.com",
        "github.com",
        "raw.githubusercontent.com",
    }
)
CONNECT_PORT = 443


def configured_provider_hosts(config_path: Path) -> frozenset[str]:
    """Return exact HTTPS hosts for configured non-mock providers."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    hosts: set[str] = set()
    for provider in config.get("providers", {}).values():
        if provider.get("adapter") == "mock":
            continue
        raw_host = provider.get("host")
        if not isinstance(raw_host, str) or not raw_host:
            raise ValueError("configured provider must declare a host")
        parsed = urlsplit(raw_host if "://" in raw_host else f"https://{raw_host}")
        host = parsed.hostname
        if (
            parsed.scheme != "https"
            or host is None
            or parsed.port not in (None, CONNECT_PORT)
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or "*" in host
        ):
            raise ValueError("provider host must be an exact HTTPS hostname")
        hosts.add(host.lower())
    return frozenset(hosts)


def parse_connect_target(target: str) -> tuple[str, int] | None:
    """Parse an HTTPS CONNECT authority, rejecting ambiguous or unsafe targets."""
    if target.count(":") != 1:
        return None
    host, port_text = target.rsplit(":", 1)
    if not host or not port_text.isascii() or not port_text.isdigit():
        return None
    port = int(port_text)
    if not 1 <= port <= 65535:
        return None
    return host.rstrip(".").lower(), port


class _ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    allowed_hosts: frozenset[str] = GITHUB_HOSTS

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_CONNECT(self) -> None:
        target = parse_connect_target(self.path)
        if target is None:
            self.send_error(400)
            return
        host, port = target
        if port != CONNECT_PORT or host not in self.allowed_hosts:
            self.send_error(403)
            return
        try:
            upstream = socket.create_connection((host, port), timeout=8)
        except OSError:
            self.send_error(502)
            return

        self.send_response(200, "Connection established")
        self.end_headers()
        self.connection.setblocking(False)
        upstream.setblocking(False)
        sockets = (self.connection, upstream)
        try:
            while True:
                readable, _, exceptional = select.select(sockets, (), sockets, 60)
                if exceptional or not readable:
                    break
                for source in readable:
                    destination = upstream if source is self.connection else self.connection
                    try:
                        payload = source.recv(65536)
                    except OSError:
                        payload = b""
                    if not payload:
                        return
                    destination.sendall(payload)
        finally:
            upstream.close()


class _ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _handler_for_hosts(hosts: frozenset[str]) -> type[_ProxyHandler]:
    class ConfiguredProxyHandler(_ProxyHandler):
        allowed_hosts = hosts

    return ConfiguredProxyHandler


def main() -> None:
    config_path = Path(sys.argv[1])
    handler = _handler_for_hosts(GITHUB_HOSTS | configured_provider_hosts(config_path))
    server = _ThreadedHTTPServer(("0.0.0.0", 3128), handler)  # noqa: S104
    server.serve_forever()


if __name__ == "__main__":
    main()
