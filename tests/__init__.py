"""Shared test helpers (stdlib only)."""

import http.client
import json
import os
import socket
import tempfile
import threading
import unittest

from font_editor.server import create_server

STUBS = {
    "index.html": b"<!doctype html><title>stub</title>",
    "app.js": b"// stub\n",
    "styles.css": b"/* stub */\n",
}


def fixture_points():
    pairs = [[30, 0], [215, 700], [285, 700], [470, 0], [390, 0], [345, 160], [155, 160], [110, 0]]
    return [{"x": x, "y": y} for x, y in pairs]


def glyph(name="A", advance=500, points=None):
    return {"name": name, "advance": advance, "points": points or fixture_points()}


class ServerTestCase(unittest.TestCase):
    """Starts a server on port 0 with a temp data dir and temp stub static dir."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_dir = os.path.join(tmp.name, "data")
        self.static_dir = os.path.join(tmp.name, "static")
        os.makedirs(self.static_dir)
        for name, content in STUBS.items():
            with open(os.path.join(self.static_dir, name), "wb") as f:
                f.write(content)
        self.start()

    def start(self):
        self.server = create_server(self.data_dir, 0, static_dir=self.static_dir)
        self.port = self.server.port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self._running = True
        self.addCleanup(self.stop)

    def stop(self):
        if getattr(self, "_running", False):
            self._running = False
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(5)

    def restart(self):
        self.stop()
        self.start()

    def request(self, method, path, body=None, headers=None, raw_body=None):
        """Returns (status, headers_dict_lowercase, parsed_json_or_bytes)."""
        hdrs = {}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        if raw_body is not None:
            data = raw_body
            hdrs["Content-Type"] = "application/json"
        hdrs.update(headers or {})
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(method, path, body=data, headers=hdrs)
            resp = conn.getresponse()
            payload = resp.read()
            h = {k.lower(): v for k, v in resp.getheaders()}
            if h.get("content-type", "").startswith("application/json"):
                payload = json.loads(payload)
            return resp.status, h, payload
        finally:
            conn.close()

    def raw(self, data, half_close=False):
        """Send raw bytes, return (status, body_bytes)."""
        s = socket.create_connection(("127.0.0.1", self.port), timeout=10)
        try:
            s.sendall(data)
            if half_close:
                s.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                c = s.recv(65536)
                if not c:
                    break
                chunks.append(c)
        finally:
            s.close()
        resp = b"".join(chunks)
        status = int(resp.split(b" ", 2)[1])
        return status, resp.split(b"\r\n\r\n", 1)[-1]

    def create(self, title="Font", glyphs=None, cap_height=None):
        body = {"title": title}
        if glyphs is not None:
            body["glyphs"] = glyphs
        if cap_height is not None:
            body["cap_height"] = cap_height
        status, _, font = self.request("POST", "/api/v1/fonts", body)
        self.assertEqual(status, 201, font)
        return font

    def put_body(self, font, **over):
        body = {
            "version": font["version"],
            "title": font["title"],
            "cap_height": font["cap_height"],
            "glyphs": font["glyphs"],
        }
        body.update(over)
        return body
