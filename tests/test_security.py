import json
import unittest

from . import ServerTestCase, glyph


class HostOriginTests(ServerTestCase):
    def test_foreign_host_rejected_everywhere(self):
        for host in ["evil.example", "evil.example:%d", "127.0.0.1:1", "127.0.0.1", "localhost", "127.0.0.1.evil.com:%d", ""]:
            h = host % self.port if "%d" in host else host
            for path in ["/api/v1/health", "/", "/static/app.js", "/api/v1/fonts"]:
                status, _, body = self.request("GET", path, headers={"Host": h})
                self.assertEqual(status, 403, (h, path))
                self.assertEqual(body["error"]["code"], "forbidden_host")

    def test_missing_host_rejected(self):
        status, _ = self.raw(b"GET /api/v1/health HTTP/1.0\r\n\r\n")
        self.assertEqual(status, 403)

    def test_allowed_hosts(self):
        for host in ["127.0.0.1:%d", "localhost:%d", "LOCALHOST:%d"]:
            status, _, _ = self.request("GET", "/api/v1/health", headers={"Host": host % self.port})
            self.assertEqual(status, 200, host)

    def test_foreign_origin_rejected_on_mutation(self):
        for origin in ["http://evil.example", "http://127.0.0.1:1", "https://127.0.0.1:%d", "null", "http://localhost"]:
            o = origin % self.port if "%d" in origin else origin
            status, _, body = self.request("POST", "/api/v1/fonts", {"title": "X"}, headers={"Origin": o})
            self.assertEqual((status, body["error"]["code"]), (403, "forbidden_origin"), o)
        self.assertEqual(self.request("GET", "/api/v1/fonts")[2], {"fonts": []})

    def test_foreign_origin_rejected_on_put(self):
        font = self.create("F")
        status, _, body = self.request("PUT", "/api/v1/fonts/%d" % font["id"], self.put_body(font, title="Z"),
                                       headers={"Origin": "http://evil.example"})
        self.assertEqual(status, 403)
        self.assertEqual(self.request("GET", "/api/v1/fonts/%d" % font["id"])[2]["title"], "F")

    def test_same_origin_accepted(self):
        for origin in ["http://127.0.0.1:%d", "http://localhost:%d"]:
            status, _, _ = self.request("POST", "/api/v1/fonts", {"title": "T" + origin[7:10]},
                                        headers={"Origin": origin % self.port})
            self.assertEqual(status, 201)

    def test_host_checked_before_origin_and_body(self):
        status, _, body = self.request("POST", "/api/v1/fonts", raw_body=b"{", headers={"Host": "evil.example"})
        self.assertEqual((status, body["error"]["code"]), (403, "forbidden_host"))


class ContentRulesTests(ServerTestCase):
    def test_content_type_required_json(self):
        for ct in ["text/plain", "application/x-www-form-urlencoded", "application/jsonx", "multipart/form-data"]:
            status, _, body = self.request("POST", "/api/v1/fonts", raw_body=b'{"title":"X"}', headers={"Content-Type": ct})
            self.assertEqual((status, body["error"]["code"]), (415, "unsupported_media_type"), ct)

    def test_missing_content_type(self):
        status, _ = self.raw(self.post_head(b"Content-Length: 2\r\n", ct=b"") + b"{}", half_close=True)
        self.assertEqual(status, 415)

    def test_charset_param_allowed(self):
        status, _, _ = self.request("POST", "/api/v1/fonts", raw_body=b'{"title":"X"}',
                                    headers={"Content-Type": "Application/JSON; charset=utf-8"})
        self.assertEqual(status, 201)

    def post_head(self, extra=b"", ct=b"Content-Type: application/json\r\n", path=b"/api/v1/fonts", method=b"POST"):
        return (method + b" " + path + b" HTTP/1.1\r\nHost: 127.0.0.1:" + str(self.port).encode() + b"\r\n" + ct + extra + b"\r\n")

    def test_length_required(self):
        status, body = self.raw(self.post_head())
        self.assertEqual(status, 411)
        self.assertEqual(json.loads(body)["error"]["code"], "length_required")
        status, _ = self.raw(self.post_head(b"Transfer-Encoding: chunked\r\n"))
        self.assertEqual(status, 411)

    def test_oversize_rejected_before_read(self):
        # Only headers are sent; a server that tried to read the body would block until timeout.
        status, body = self.raw(self.post_head(b"Content-Length: %d\r\n" % (256 * 1024 + 1)))
        self.assertEqual(status, 413)
        self.assertEqual(json.loads(body)["error"]["code"], "payload_too_large")
        status, _ = self.raw(self.post_head(b"Content-Length: 99999999999\r\n"))
        self.assertEqual(status, 413)

    def test_body_at_limit_is_read(self):
        pad = b" " * (256 * 1024 - 13)
        raw = b'{"title":"X"}' + pad
        self.assertEqual(len(raw), 256 * 1024)
        status, _, _ = self.request("POST", "/api/v1/fonts", raw_body=raw)
        self.assertEqual(status, 201)

    def test_bad_content_length(self):
        for v in [b"abc", b"-1", b"1.5", b""]:
            status, _ = self.raw(self.post_head(b"Content-Length: " + v + b"\r\n"))
            self.assertEqual(status, 400, v)

    def test_truncated_body(self):
        status, _ = self.raw(self.post_head(b"Content-Length: 50\r\n") + b'{"title"', half_close=True)
        self.assertEqual(status, 400)

    def test_put_size_cap(self):
        font = self.create("F")
        status, body = self.raw(self.post_head(b"Content-Length: 300000\r\n", path=b"/api/v1/fonts/%d" % font["id"], method=b"PUT"))
        self.assertEqual(status, 413)


class HeaderTests(ServerTestCase):
    def check_common(self, h):
        self.assertEqual(h["cache-control"], "no-store")
        self.assertEqual(h["x-content-type-options"], "nosniff")
        self.assertEqual(h["referrer-policy"], "no-referrer")
        self.assertFalse([k for k in h if k.startswith("access-control-")], h)

    def test_common_and_no_cors_on_all_kinds_of_responses(self):
        font = self.create("F")
        responses = [
            self.request("GET", "/api/v1/health"),
            self.request("GET", "/api/v1/fonts/999"),
            self.request("GET", "/"),
            self.request("GET", "/static/app.js"),
            self.request("GET", "/nope"),
            self.request("OPTIONS", "/api/v1/fonts", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "PUT"}),
            self.request("GET", "/api/v1/health", headers={"Host": "evil.example"}),
            self.request("POST", "/api/v1/fonts", {"title": "Y"}, headers={"Origin": "http://evil.example"}),
            self.request("PUT", "/api/v1/fonts/%d" % font["id"], self.put_body(font), headers={"Origin": "http://%s:%d" % ("127.0.0.1", self.port)}),
        ]
        for status, h, _ in responses:
            self.check_common(h)

    def test_options_405(self):
        status, h, body = self.request("OPTIONS", "/api/v1/fonts", headers={"Origin": "http://evil.example"})
        self.assertEqual(status, 405)
        status, h, body = self.request("OPTIONS", "/anything")
        self.assertEqual(status, 405)
        self.assertNotIn("access-control-allow-origin", h)

    def test_csp_on_html_only(self):
        _, h, _ = self.request("GET", "/")
        csp = h["content-security-policy"]
        for part in ["default-src 'none'", "script-src 'self'", "style-src 'self'", "connect-src 'self'",
                     "img-src 'self' data:", "base-uri 'none'", "form-action 'none'", "frame-ancestors 'none'"]:
            self.assertIn(part, csp)
        _, h, _ = self.request("GET", "/api/v1/health")
        self.assertNotIn("content-security-policy", h)

    def test_error_content_type_is_json(self):
        _, h, _ = self.request("GET", "/api/v1/fonts/999")
        self.assertTrue(h["content-type"].startswith("application/json"))


class StaticTests(ServerTestCase):
    def test_allowlisted_files_and_types(self):
        status, h, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertTrue(h["content-type"].startswith("text/html"))
        self.assertIn(b"stub", body)
        status, h, _ = self.request("GET", "/static/app.js")
        self.assertEqual(status, 200)
        self.assertTrue(h["content-type"].startswith("text/javascript"))
        status, h, _ = self.request("GET", "/static/styles.css")
        self.assertEqual(status, 200)
        self.assertTrue(h["content-type"].startswith("text/css"))

    def test_query_string_ignored(self):
        self.assertEqual(self.request("GET", "/static/app.js?v=1")[0], 200)

    def test_traversal_and_non_allowlisted_404(self):
        paths = [
            "/static/../server.py", "/static/..%2fserver.py", "/static/%2e%2e/server.py", "/static/%2E%2E%2Fserver.py",
            "/static\\app.js", "/static/..\\server.py", "/static/", "/static", "/static/index.html",
            "/index.html", "/static/app.js/", "/static//app.js","/static/app.js%00.css",
            "/static/%61pp.js", "/..%5cserver.py", "/font_editor/server.py", "/fonts.sqlite3", "/static/app.js/..",
            "/../../etc/passwd", "/%2e%2e/%2e%2e/etc/passwd", "/static/styles.css%20",
        ]
        for p in paths:
            status, _, body = self.request("GET", p)
            self.assertEqual(status, 404, p)
            self.assertEqual(body["error"]["code"], "not_found", p)

    def test_missing_static_file_404_not_500(self):
        import os
        os.remove(os.path.join(self.static_dir, "app.js"))
        self.assertEqual(self.request("GET", "/static/app.js")[0], 404)

    def test_real_static_files_when_present(self):
        # The interface engineer writes these concurrently; only check status/type if present.
        import os
        from font_editor.server import DEFAULT_STATIC_DIR, create_server
        import tempfile, threading, http.client
        names = ["index.html", "app.js", "styles.css"]
        if not all(os.path.isfile(os.path.join(DEFAULT_STATIC_DIR, n)) for n in names):
            self.skipTest("static files not present yet")
        with tempfile.TemporaryDirectory() as d:
            srv = create_server(os.path.join(d, "data"), 0)
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            try:
                for path, prefix in [("/", "text/html"), ("/static/app.js", "text/javascript"), ("/static/styles.css", "text/css")]:
                    c = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=10)
                    c.request("GET", path)
                    r = c.getresponse()
                    r.read()
                    c.close()
                    self.assertEqual(r.status, 200, path)
                    self.assertTrue(r.getheader("Content-Type").startswith(prefix))
            finally:
                srv.shutdown()
                srv.server_close()
                t.join(5)


if __name__ == "__main__":
    unittest.main()
