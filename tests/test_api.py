import os
import threading
import unittest

from . import ServerTestCase, glyph, fixture_points


class HealthAndFontsTests(ServerTestCase):
    def test_health(self):
        status, h, body = self.request("GET", "/api/v1/health")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "ok", "app": "font-editor", "api_version": 1, "schema_version": 1})

    def test_empty_list(self):
        self.assertEqual(self.request("GET", "/api/v1/fonts")[2], {"fonts": []})

    def test_create_get_list_sorted_nocase(self):
        self.create("beta")
        self.create("Alpha", glyphs=[glyph()])
        self.create("Gamma")
        status, _, body = self.request("GET", "/api/v1/fonts")
        self.assertEqual([f["title"] for f in body["fonts"]], ["Alpha", "beta", "Gamma"])
        self.assertEqual(body["fonts"][0]["glyph_count"], 1)
        self.assertEqual(set(body["fonts"][0]), {"id", "title", "version", "glyph_count", "updated_at"})

    def test_create_response_shape_and_location(self):
        status, h, font = self.request("POST", "/api/v1/fonts", {"title": " Smoke ", "glyphs": [glyph("Fixture A")]})
        self.assertEqual(status, 201)
        self.assertEqual(h["location"], "/api/v1/fonts/%d" % font["id"])
        self.assertEqual(set(font), {"id", "title", "cap_height", "version", "created_at", "updated_at", "glyphs"})
        self.assertEqual(font["title"], "Smoke")
        self.assertEqual(font["cap_height"], 700)
        self.assertEqual(font["version"], 1)
        self.assertEqual(font["glyphs"][0]["points"], fixture_points())
        self.assertTrue(font["created_at"].endswith("Z"))
        self.assertEqual(self.request("GET", "/api/v1/fonts/%d" % font["id"])[2], font)

    def test_duplicate_title_case_insensitive(self):
        self.create("Smoke")
        status, _, body = self.request("POST", "/api/v1/fonts", {"title": "sMOKE"})
        self.assertEqual((status, body["error"]["code"]), (409, "duplicate_title"))

    def test_put_duplicate_title(self):
        self.create("One")
        two = self.create("Two")
        status, _, body = self.request("PUT", "/api/v1/fonts/%d" % two["id"], self.put_body(two, title="ONE"))
        self.assertEqual((status, body["error"]["code"]), (409, "duplicate_title"))
        # renaming to own title with different case is fine
        status, _, body = self.request("PUT", "/api/v1/fonts/%d" % two["id"], self.put_body(two, title="TWO"))
        self.assertEqual(status, 200)

    def test_duplicate_glyph_name_422(self):
        status, _, body = self.request("POST", "/api/v1/fonts", {"title": "X", "glyphs": [glyph("A"), glyph("a")]})
        self.assertEqual((status, body["error"]["code"]), (422, "validation_failed"))
        self.assertEqual(body["error"]["details"][0]["field"], "glyphs[1].name")

    def test_validation_reports_multiple_details(self):
        status, _, body = self.request("POST", "/api/v1/fonts", {"title": "", "cap_height": 5, "glyphs": [glyph(advance=1)]})
        self.assertEqual(status, 422)
        got = {d["field"] for d in body["error"]["details"]}
        self.assertEqual(got, {"title", "cap_height", "glyphs[0].advance"})

    def test_invalid_json(self):
        for raw in [b"{", b"\xff\xfe", b"[1,2", b'{"title": NaN}', b"[" * 100000]:
            status, _, body = self.request("POST", "/api/v1/fonts", raw_body=raw)
            self.assertEqual((status, body["error"]["code"]), (400, "invalid_json"), raw[:20])

    def test_non_object_body_422(self):
        status, _, body = self.request("POST", "/api/v1/fonts", raw_body=b"[]")
        self.assertEqual((status, body["error"]["code"]), (422, "validation_failed"))

    def test_font_limit(self):
        for i in range(200):
            self.create("f%d" % i)
        status, _, body = self.request("POST", "/api/v1/fonts", {"title": "one too many"})
        self.assertEqual((status, body["error"]["code"]), (409, "limit_reached"))

    def test_bad_ids_and_unknown_routes(self):
        for p in ["/api/v1/fonts/999", "/api/v1/fonts/abc", "/api/v1/fonts/" + "9" * 40, "/api/v1/fonts/-1",
                  "/api/v1/fonts/1/", "/api/v2/fonts", "/api/nothing", "/api/v1/fonts/1/glyphs", "/nope"]:
            status, _, body = self.request("GET", p)
            self.assertEqual((status, body["error"]["code"]), (404, "not_found"), p)
        status, _, body = self.request("PUT", "/api/v1/fonts/999", {"version": 1, "title": "T", "cap_height": 700, "glyphs": []})
        self.assertEqual(status, 404)

    def test_method_not_allowed(self):
        cases = [("DELETE", "/api/v1/fonts", "GET, POST"), ("PUT", "/api/v1/fonts", "GET, POST"),
                 ("POST", "/api/v1/health", "GET"), ("PATCH", "/api/v1/fonts", "GET, POST"),
                 ("OPTIONS", "/api/v1/fonts", "GET, POST"), ("POST", "/api/v1/fonts/1", "GET, PUT"),
                 ("DELETE", "/api/v1/fonts/1", "GET, PUT"), ("POST", "/", "GET")]
        for m, p, allow in cases:
            status, h, body = self.request(m, p, body={} if m in ("POST", "PUT", "DELETE") else None)
            self.assertEqual(status, 405, (m, p))
            self.assertEqual(h["allow"], allow)
            self.assertEqual(body["error"]["code"], "method_not_allowed")


class ReplaceTests(ServerTestCase):
    def test_put_roundtrip_ids_and_version(self):
        font = self.create("F", glyphs=[glyph("A"), glyph("B")])
        a, b = font["glyphs"]
        self.assertNotEqual(a["id"], b["id"])
        status, _, f2 = self.request("PUT", "/api/v1/fonts/%d" % font["id"], self.put_body(font, cap_height=650))
        self.assertEqual((status, f2["version"], f2["cap_height"]), (200, 2, 650))
        self.assertEqual([g["id"] for g in f2["glyphs"]], [a["id"], b["id"]])
        self.assertEqual(f2["created_at"], font["created_at"])

    def test_swap_names_and_reorder(self):
        font = self.create("F", glyphs=[glyph("A"), glyph("B"), glyph("C")])
        a, b, c = font["glyphs"]
        new = [dict(c, name="A"), dict(a, name="B"), dict(b, name="C")]
        status, _, f2 = self.request("PUT", "/api/v1/fonts/%d" % font["id"], self.put_body(font, glyphs=new))
        self.assertEqual(status, 200, f2)
        self.assertEqual([(g["id"], g["name"]) for g in f2["glyphs"]],
                         [(c["id"], "A"), (a["id"], "B"), (b["id"], "C")])

    def test_delete_by_omission_and_ids_not_reused(self):
        font = self.create("F", glyphs=[glyph("A"), glyph("B")])
        a, b = font["glyphs"]
        _, _, f2 = self.request("PUT", "/api/v1/fonts/%d" % font["id"], self.put_body(font, glyphs=[b]))
        self.assertEqual([g["id"] for g in f2["glyphs"]], [b["id"]])
        new = [b, glyph("N")]
        _, _, f3 = self.request("PUT", "/api/v1/fonts/%d" % font["id"], self.put_body(f2, glyphs=new))
        self.assertGreater(f3["glyphs"][1]["id"], max(a["id"], b["id"]))
        # a deleted id cannot be resurrected
        status, _, body = self.request("PUT", "/api/v1/fonts/%d" % font["id"], self.put_body(f3, glyphs=[a]))
        self.assertEqual((status, body["error"]["code"]), (422, "validation_failed"))
        self.assertEqual(body["error"]["details"][0]["field"], "glyphs[0].id")

    def test_foreign_glyph_id_rejected_and_nothing_changed(self):
        f1 = self.create("One", glyphs=[glyph("A")])
        f2 = self.create("Two", glyphs=[glyph("A")])
        status, _, body = self.request("PUT", "/api/v1/fonts/%d" % f2["id"],
                                       self.put_body(f2, title="Changed", glyphs=[f1["glyphs"][0]]))
        self.assertEqual(status, 422)
        self.assertEqual(self.request("GET", "/api/v1/fonts/%d" % f2["id"])[2], f2)
        self.assertEqual(self.request("GET", "/api/v1/fonts/%d" % f1["id"])[2], f1)

    def test_stale_version_409_with_current(self):
        font = self.create("F", glyphs=[glyph("A")])
        _, _, v2 = self.request("PUT", "/api/v1/fonts/%d" % font["id"], self.put_body(font, title="Second"))
        status, _, body = self.request("PUT", "/api/v1/fonts/%d" % font["id"], self.put_body(font, title="Third"))
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "stale_version")
        self.assertEqual(body["error"]["current"], v2)
        self.assertEqual(self.request("GET", "/api/v1/fonts/%d" % font["id"])[2]["title"], "Second")
        # resubmit over the current version succeeds
        status, _, v3 = self.request("PUT", "/api/v1/fonts/%d" % font["id"], self.put_body(font, version=v2["version"], title="Third", glyphs=v2["glyphs"]))
        self.assertEqual((status, v3["version"]), (200, 3))

    def test_failed_put_is_atomic(self):
        font = self.create("F", glyphs=[glyph("A"), glyph("B")])
        other = self.create("Other")
        status, _, _ = self.request("PUT", "/api/v1/fonts/%d" % font["id"], self.put_body(font, title="Other", glyphs=[]))
        self.assertEqual(status, 409)
        self.assertEqual(self.request("GET", "/api/v1/fonts/%d" % font["id"])[2], font)

    def test_put_validation_errors(self):
        font = self.create("F")
        for body in [{}, {"version": 1}, self.put_body(font, glyphs=None), self.put_body(font, version="1")]:
            status, _, resp = self.request("PUT", "/api/v1/fonts/%d" % font["id"], body)
            self.assertEqual((status, resp["error"]["code"]), (422, "validation_failed"), body)

    def test_concurrent_puts_exactly_one_wins(self):
        font = self.create("F", glyphs=[glyph("A")])
        n = 8
        barrier = threading.Barrier(n)
        results = [None] * n

        def work(i):
            barrier.wait()
            results[i] = self.request("PUT", "/api/v1/fonts/%d" % font["id"], self.put_body(font, title="T%d" % i))

        threads = [threading.Thread(target=work, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        statuses = sorted(r[0] for r in results)
        self.assertEqual(statuses, [200] + [409] * (n - 1), statuses)
        winner = next(r[2] for r in results if r[0] == 200)
        self.assertEqual(winner["version"], 2)
        for r in results:
            if r[0] == 409:
                self.assertEqual(r[2]["error"]["code"], "stale_version")
                self.assertEqual(r[2]["error"]["current"]["version"], 2)
        self.assertEqual(self.request("GET", "/api/v1/fonts/%d" % font["id"])[2], winner)


class PersistenceTests(ServerTestCase):
    def test_roundtrip_exact_across_restart(self):
        fx = glyph("Fixture A", 500)
        font = self.create("Smoke", glyphs=[fx])
        self.assertEqual(font["glyphs"][0]["advance"], 500)
        g = dict(font["glyphs"][0], advance=640)
        g["points"] = [dict(p) for p in g["points"]]
        g["points"][2]["x"] = 300
        status, _, saved = self.request("PUT", "/api/v1/fonts/%d" % font["id"], self.put_body(font, glyphs=[g]))
        self.assertEqual((status, saved["version"]), (200, 2))
        listing = self.request("GET", "/api/v1/fonts")[2]

        self.restart()
        status, _, again = self.request("GET", "/api/v1/fonts/%d" % font["id"])
        self.assertEqual(status, 200)
        self.assertEqual(again, saved)
        self.assertEqual(again["glyphs"][0]["advance"], 640)
        self.assertEqual(again["glyphs"][0]["points"][2], {"x": 300, "y": 700})
        self.assertEqual(self.request("GET", "/api/v1/fonts")[2], listing)

    def test_ids_not_reused_after_restart(self):
        font = self.create("F", glyphs=[glyph("A")])
        old = font["glyphs"][0]["id"]
        _, _, f2 = self.request("PUT", "/api/v1/fonts/%d" % font["id"], self.put_body(font, glyphs=[]))
        self.restart()
        _, _, f3 = self.request("PUT", "/api/v1/fonts/%d" % font["id"], self.put_body(f2, glyphs=[glyph("A")]))
        self.assertGreater(f3["glyphs"][0]["id"], old)

    def test_database_file_in_data_dir(self):
        self.assertTrue(os.path.exists(os.path.join(self.data_dir, "fonts.sqlite3")))


if __name__ == "__main__":
    unittest.main()
