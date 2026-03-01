#!/usr/bin/env python3.10
"""Simple HTTP server that serves the test client and generates Agora RTC tokens."""

import http.server
import json
import os
import ssl
import time
import urllib.parse

from agora_token_builder import RtcTokenBuilder

APP_ID = os.environ.get("AGORA_APP_ID", "371a0ec85abf406698db695f32423e9c")
APP_CERTIFICATE = os.environ.get("AGORA_APP_CERTIFICATE", "0bc075d3d6fb421d914aec3632453837")
TOKEN_EXPIRY = 3600  # 1 hour


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/token":
            self.handle_token(parsed.query)
        elif parsed.path == "/" or parsed.path == "":
            self.path = "/index.html"
            super().do_GET()
        else:
            super().do_GET()

    def handle_token(self, query_string):
        params = urllib.parse.parse_qs(query_string)
        channel = params.get("channel", ["deep_trip_demo"])[0]
        uid = int(params.get("uid", ["0"])[0])
        expire_ts = int(time.time()) + TOKEN_EXPIRY

        token = RtcTokenBuilder.buildTokenWithUid(
            APP_ID, APP_CERTIFICATE, channel, uid,
            1,  # Role_Publisher
            expire_ts,
        )

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"token": token}).encode())

    def log_message(self, fmt, *args):
        print(f"[test-client] {fmt % args}")


if __name__ == "__main__":
    port = 3000
    server = http.server.HTTPServer(("0.0.0.0", port), Handler)
    cert_dir = os.path.dirname(os.path.abspath(__file__))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(
        os.path.join(cert_dir, "cert.pem"),
        os.path.join(cert_dir, "key.pem"),
    )
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    print(f"Test client server running at https://0.0.0.0:{port}")
    print(f"Access via Tailscale: https://100.124.66.113:{port}")
    server.serve_forever()
