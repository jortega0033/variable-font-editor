"""Command line entry point."""

import argparse
import os
import sys
import tempfile

from .server import create_server
from .storage import StorageError


def _port(value):
    try:
        p = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("port must be an integer 1-65535")
    if not 1 <= p <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return p


def _fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    return 2


def main(argv=None):
    parser = argparse.ArgumentParser(prog="font_editor", description="Local variable font editor")
    parser.add_argument("--data-dir", required=True, help="directory for the database")
    parser.add_argument("--port", required=True, type=_port, help="TCP port on 127.0.0.1 (1-65535)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 2

    data_dir = args.data_dir
    if data_dir.strip() == "":
        return _fail("--data-dir must not be empty")
    if os.path.exists(data_dir) and not os.path.isdir(data_dir):
        return _fail(f"--data-dir is not a directory: {data_dir}")
    try:
        os.makedirs(data_dir, exist_ok=True)
        with tempfile.TemporaryFile(dir=data_dir):
            pass
    except OSError as e:
        return _fail(f"--data-dir is not usable: {e.strerror or e}")

    try:
        server = create_server(data_dir, args.port)
    except StorageError as e:
        return _fail(str(e))
    except OSError as e:
        print(f"error: cannot listen on 127.0.0.1:{args.port}: {e.strerror or e}", file=sys.stderr)
        return 1

    print(f"Serving on http://127.0.0.1:{server.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
