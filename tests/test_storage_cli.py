import contextlib
import io
import os
import sqlite3
import tempfile
import unittest

from font_editor import cli
from font_editor.server import create_server
from font_editor.storage import DB_NAME, Storage, StorageError, NotFound
from font_editor.validation import validate_font

from . import glyph


class TempDirCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.data = os.path.join(tmp.name, "a", "b", "data")  # parents created on demand


class StorageTests(TempDirCase):
    def test_creates_nested_dir_and_schema(self):
        s = Storage(self.data)
        self.assertEqual(s.schema_version(), 1)
        con = sqlite3.connect(os.path.join(self.data, DB_NAME))
        self.addCleanup(con.close)
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"fonts", "glyphs"} <= tables)
        self.assertEqual(con.execute("PRAGMA journal_mode").fetchone()[0], "wal")

    def test_migration_idempotent_and_preserves_data(self):
        s = Storage(self.data)
        clean, _ = validate_font({"title": "Keep", "glyphs": [glyph()]}, False)
        font = s.create_font(clean)
        for _ in range(3):
            s2 = Storage(self.data)
            self.assertEqual(s2.schema_version(), 1)
        self.assertEqual(s2.get_font(font["id"]), font)

    def test_newer_schema_rejected_and_untouched(self):
        Storage(self.data)
        path = os.path.join(self.data, DB_NAME)
        con = sqlite3.connect(path)
        con.execute("PRAGMA user_version=99")
        con.close()
        with self.assertRaises(StorageError):
            Storage(self.data)
        with self.assertRaises(StorageError):
            create_server(self.data, 0)
        con = sqlite3.connect(path)
        self.addCleanup(con.close)
        self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 99)

    def test_corrupt_db_is_storage_error(self):
        os.makedirs(self.data)
        with open(os.path.join(self.data, DB_NAME), "wb") as f:
            f.write(b"this is not a sqlite database" * 100)
        with self.assertRaises(StorageError):
            Storage(self.data)

    def test_empty_and_file_paths(self):
        with self.assertRaises(StorageError):
            Storage("")
        f = os.path.join(self.tmp, "file")
        open(f, "w").close()
        with self.assertRaises(StorageError):
            Storage(f)
        with self.assertRaises(StorageError):
            Storage(os.path.join(f, "sub"))

    def test_get_missing(self):
        with self.assertRaises(NotFound):
            Storage(self.data).get_font(1)

    def test_db_constraints_back_up_validation(self):
        Storage(self.data)
        con = sqlite3.connect(os.path.join(self.data, DB_NAME))
        self.addCleanup(con.close)
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("INSERT INTO fonts(title,cap_height,created_at,updated_at) VALUES('x',200,'t','t')")


class CliTests(TempDirCase):
    def run_cli(self, *argv):
        err = io.StringIO()
        out = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_empty_data_dir_exit_2(self):
        code, out, err = self.run_cli("--data-dir", "", "--port", "8123")
        self.assertEqual(code, 2)
        self.assertIn("error", err)
        self.assertNotIn("Traceback", err)
        self.assertEqual(out, "")

    def test_data_dir_is_file_exit_2(self):
        f = os.path.join(self.tmp, "afile")
        open(f, "w").close()
        code, _, err = self.run_cli("--data-dir", f, "--port", "8123")
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", err)

    def test_unusable_parent_is_file_exit_2(self):
        f = os.path.join(self.tmp, "afile")
        open(f, "w").close()
        code, _, err = self.run_cli("--data-dir", os.path.join(f, "child"), "--port", "8123")
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", err)

    def test_newer_schema_exit_2(self):
        Storage(self.data)
        con = sqlite3.connect(os.path.join(self.data, DB_NAME))
        con.execute("PRAGMA user_version=42")
        con.close()
        code, out, err = self.run_cli("--data-dir", self.data, "--port", "8123")
        self.assertEqual(code, 2)
        self.assertIn("newer", err)
        self.assertEqual(out, "")

    def test_bad_args_exit_2(self):
        for argv in [[], ["--data-dir", self.data], ["--port", "8123"],
                     ["--data-dir", self.data, "--port", "0"],
                     ["--data-dir", self.data, "--port", "65536"],
                     ["--data-dir", self.data, "--port", "abc"]]:
            code, _, _ = self.run_cli(*argv)
            self.assertEqual(code, 2, argv)
        self.assertFalse(os.path.exists(self.data))

    def test_create_server_binds_loopback_port0(self):
        srv = create_server(self.data, 0)
        try:
            self.assertEqual(srv.server_address[0], "127.0.0.1")
            self.assertGreater(srv.port, 0)
            self.assertTrue(srv.daemon_threads)
        finally:
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
