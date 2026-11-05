"""本地预览服务器：为 .ics 返回正确的 text/calendar MIME，便于直接用日历客户端订阅。"""

from __future__ import annotations

import functools
import socket
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".ics": "text/calendar; charset=utf-8",
        ".webcal": "text/calendar; charset=utf-8",
        ".html": "text/html; charset=utf-8",
    }

    def end_headers(self) -> None:  # noqa: D102
        if self.path.lower().endswith((".ics", ".webcal")):
            self.send_header("Cache-Control", "no-store, must-revalidate")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Disposition", "inline")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:  # 静默日志
        pass


def _lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def serve(directory: Path, port: int = 8000) -> None:
    handler = functools.partial(Handler, directory=str(directory))
    with ThreadingHTTPServer(("0.0.0.0", port), handler) as httpd:
        ip = _lan_ip()
        print()
        print(f"  预览页面  http://localhost:{port}/")
        print(f"  订阅地址  http://localhost:{port}/china-festivals.ics")
        print(f"  局域网    http://{ip}:{port}/china-festivals.ics   （同一 Wi-Fi 下的 iPhone 可用）")
        print("  Ctrl+C 停止")
        print()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")
