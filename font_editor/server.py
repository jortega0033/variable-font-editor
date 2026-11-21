"""HTTP server: JSON API plus an exact allowlist of static files."""

import json
import os
import re
import socket
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import storage as st
from .storage import Storage
from .validation import validate_font

MAX_BODY = 256 * 1024
HOST = "127.0.0.1"

DEFAULT_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# URL path -> (file name, content type). The only paths that ever touch the filesystem.
STATIC_ROUTES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/static/styles.css": ("styles.css", "text/css; charset=utf-8"),
}

CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
    "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)

FONT_PATH = re.compile(r"^/api/v1/fonts/([0-9]{1,15})$")
MUTATIONS = ("POST", "PUT", "DELETE")


class FontServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = os.name != "nt"  # on Windows it would allow port hijacking

    def __init__(self, addr, handler, storage, static_dir):
        self.storage = storage
        self.static_dir = static_dir
        super().__init__(addr, handler)

    @property
    def port(self):
        return self.server_address[1]

    def server_close(self):
        super().server_close()
        self.storage.checkpoint()


class Handler(BaseHTTPRequestHandler):
    server_version = "FontEditor/1"
    sys_version = ""
    protocol_version = "HTTP/1.0"
    timeout = 10

    # ---- plumbing ----
    def log_message(self, fmt, *args):
        try:
            sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))
        except Exception:
            pass

    def _common_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")

    def _send(self, status, body, ctype, extra=None, html=False):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self._common_headers()
        if html:
            self.send_header("Content-Security-Policy", CSP)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        self.close_connection = True

    def _json(self, status, obj, extra=None):
        body = json.dumps(obj).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8", extra)

    def _error(self, status, code, message, details=None, extra_fields=None, headers=None):
        err = {"code": code, "message": message}
        if details:
            err["details"] = details
        if extra_fields:
            err.update(extra_fields)
        self._json(status, {"error": err}, headers)

    def send_error(self, code, message=None, explain=None):
        # Protocol-level errors (malformed request line, too-long lines...) in our format.
        codes = {400: "bad_request", 414: "uri_too_long", 431: "headers_too_large", 408: "timeout"}
        try:
            self._error(code, codes.get(code, "http_error"), message or "request error")
        except OSError:
            self.close_connection = True

    # ---- entry points ----
    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_OPTIONS(self):
        self._dispatch("OPTIONS")

    def do_HEAD(self):
        self._dispatch("HEAD")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def _drain(self):
        """After an early rejection, swallow the unread (small) body so closing the socket
        does not reset the connection before the client has read our response."""
        if self._consumed or self.command not in MUTATIONS:
            return
        cl = (self.headers.get("Content-Length") or "").strip()
        if not (cl.isascii() and cl.isdigit() and len(cl) <= 12):
            return
        remaining = int(cl)
        if remaining > MAX_BODY:
            return
        try:
            self.wfile.flush()
            self.connection.shutdown(socket.SHUT_WR)
            self.connection.settimeout(2)
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 65536))
                if not chunk:
                    break
                remaining -= len(chunk)
        except (OSError, ValueError):
            pass

    def _dispatch(self, method):
        self._consumed = False
        try:
            self._dispatch_inner(method)
        finally:
            self._drain()

    def _dispatch_inner(self, method):
        try:
            self._handle(method)
        except (BrokenPipeError, ConnectionError, TimeoutError):
            self.close_connection = True
        except st.StorageError:
            self._safe_error(500, "storage_error", "storage failure")
        except sqlite3.OperationalError as e:
            if "locked" in str(e) or "busy" in str(e):
                self._safe_error(503, "busy", "database busy, retry")
            else:
                self._safe_error(500, "internal_error", "internal error")
        except Exception as e:  # never leak details or tracebacks to the client
            sys.stderr.write("internal error: %s\n" % type(e).__name__)
            self._safe_error(500, "internal_error", "internal error")

    def _safe_error(self, status, code, message):
        try:
            self._error(status, code, message)
        except OSError:
            self.close_connection = True

    # ---- request handling ----
    def _allowed_host_values(self, scheme=""):
        port = self.server.port
        return {f"{scheme}127.0.0.1:{port}", f"{scheme}localhost:{port}"}

    def _handle(self, method):
        host = self.headers.get("Host")
        if host is None or host.strip().lower() not in self._allowed_host_values():
            return self._error(403, "forbidden_host", "host not allowed")

        if method in MUTATIONS:
            origin = self.headers.get("Origin")
            if origin is not None and origin.strip().lower() not in self._allowed_host_values(
                "http://"
            ):
                return self._error(403, "forbidden_origin", "origin not allowed")

        path = self.path.split("?", 1)[0].split("#", 1)[0]

        if path in STATIC_ROUTES:
            if method != "GET":
                return self._error(405, "method_not_allowed", "method not allowed", headers={"Allow": "GET"})
            return self._static(path)

        if path.startswith("/api/"):
            return self._api(method, path)
        return self._not_found(method)

    def _not_found(self, method):
        if method == "OPTIONS":
            return self._not_allowed("GET")
        return self._error(404, "not_found", "not found")

    def _static(self, path):
        name, ctype = STATIC_ROUTES[path]
        try:
            with open(os.path.join(self.server.static_dir, name), "rb") as f:
                data = f.read()
        except OSError:
            return self._error(404, "not_found", "not found")
        self._send(200, data, ctype, html=(path == "/"))

    def _api(self, method, path):
        if path == "/api/v1/health":
            allow = "GET"
            if method != "GET":
                return self._not_allowed(allow)
            return self._json(
                200, {"status": "ok", "app": "font-editor", "api_version": 1, "schema_version": st.SCHEMA_VERSION}
            )
        if path == "/api/v1/fonts":
            if method == "GET":
                return self._json(200, {"fonts": self.server.storage.list_fonts()})
            if method == "POST":
                return self._create()
            return self._not_allowed("GET, POST")
        m = FONT_PATH.match(path)
        if m:
            font_id = int(m.group(1))
            if method == "GET":
                try:
                    return self._json(200, self.server.storage.get_font(font_id))
                except st.NotFound:
                    return self._error(404, "not_found", "font not found")
            if method == "PUT":
                return self._replace(font_id)
            return self._not_allowed("GET, PUT")
        return self._not_found(method)

    def _not_allowed(self, allow):
        self._error(405, "method_not_allowed", "method not allowed", headers={"Allow": allow})

    def _read_json(self):
        """Returns (ok, value). On failure an error response was already sent."""
        ctype = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if ctype != "application/json":
            self._error(415, "unsupported_media_type", "Content-Type must be application/json")
            return False, None
        if self.headers.get("Transfer-Encoding") is not None:
            self._error(411, "length_required", "Content-Length required")
            return False, None
        cl = self.headers.get("Content-Length")
        if cl is None:
            self._error(411, "length_required", "Content-Length required")
            return False, None
        cl = cl.strip()
        if not cl.isascii() or not cl.isdigit() or len(cl) > 12:
            self._error(400, "bad_request", "invalid Content-Length")
            return False, None
        length = int(cl)
        if length > MAX_BODY:
            self._error(413, "payload_too_large", f"body exceeds {MAX_BODY} bytes")
            return False, None
        self._consumed = True
        raw = self.rfile.read(length) if length else b""
        if len(raw) != length:
            self._error(400, "bad_request", "incomplete body")
            return False, None

        def reject(_):
            raise ValueError("non-finite number")

        try:
            return True, json.loads(raw.decode("utf-8"), parse_constant=reject)
        except (ValueError, RecursionError):  # includes UnicodeDecodeError
            self._error(400, "invalid_json", "body is not valid JSON")
            return False, None

    def _validation_error(self, details, truncated=False):
        msg = "validation failed"
        if truncated:
            msg += " (showing first 50 problems)"
        self._error(422, "validation_failed", msg, details=details)

    def _create(self):
        ok, body = self._read_json()
        if not ok:
            return
        clean, errors = validate_font(body, require_version=False)
        if clean is None:
            return self._validation_error(errors.items, errors.truncated)
        try:
            font = self.server.storage.create_font(clean)
        except st.DuplicateTitle:
            return self._error(409, "duplicate_title", "a font with this title already exists")
        except st.LimitReached:
            return self._error(409, "limit_reached", "maximum number of fonts reached")
        except st.ValidationFailed as e:
            return self._validation_error(e.details)
        self._json(201, font, {"Location": f"/api/v1/fonts/{font['id']}"})

    def _replace(self, font_id):
        ok, body = self._read_json()
        if not ok:
            return
        clean, errors = validate_font(body, require_version=True)
        if clean is None:
            return self._validation_error(errors.items, errors.truncated)
        try:
            font = self.server.storage.replace_font(font_id, clean)
        except st.NotFound:
            return self._error(404, "not_found", "font not found")
        except st.StaleVersion as e:
            return self._error(
                409,
                "stale_version",
                f"font was changed by another save (now version {e.current['version']})",
                extra_fields={"current": e.current},
            )
        except st.DuplicateTitle:
            return self._error(409, "duplicate_title", "a font with this title already exists")
        except st.ValidationFailed as e:
            return self._validation_error(e.details)
        self._json(200, font)


def create_server(data_dir, port, static_dir=None):
    """Create (bound, not yet serving) server. Raises StorageError / OSError on failure."""
    storage = Storage(data_dir)
    return FontServer(
        (HOST, port), Handler, storage, static_dir if static_dir is not None else DEFAULT_STATIC_DIR
    )
