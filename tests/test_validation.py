import copy
import unittest

from font_editor.validation import validate_font

from . import glyph


def fields(errors):
    return {e["field"] for e in errors.items}


class ValidationTests(unittest.TestCase):
    def ok(self, body, require_version=False):
        clean, errors = validate_font(body, require_version)
        self.assertIsNotNone(clean, errors.items)
        return clean

    def bad(self, body, field, require_version=False):
        clean, errors = validate_font(body, require_version)
        self.assertIsNone(clean)
        self.assertIn(field, fields(errors), errors.items)

    def test_minimal_create_defaults(self):
        c = self.ok({"title": "  Hello  "})
        self.assertEqual(c["title"], "Hello")
        self.assertEqual(c["cap_height"], 700)
        self.assertEqual(c["glyphs"], [])

    def test_title_rules(self):
        for t in ["", "   ", "x" * 61, "a\nb", "a\x00b", 5, None, "\ud800"]:
            self.bad({"title": t}, "title")
        self.ok({"title": "x" * 60})

    def test_cap_height_rules(self):
        for v in [299, 1001, True, 700.0, "700", None]:
            self.bad({"title": "T", "cap_height": v}, "cap_height")
        self.ok({"title": "T", "cap_height": 300})
        self.ok({"title": "T", "cap_height": 1000})

    def test_glyph_name_rules(self):
        for n in ["", " ", "n" * 25, "a\tb", 3]:
            self.bad({"title": "T", "glyphs": [glyph(n)]}, "glyphs[0].name")
        self.ok({"title": "T", "glyphs": [glyph("n" * 24)]})

    def test_duplicate_glyph_names_case_insensitive(self):
        self.bad({"title": "T", "glyphs": [glyph("A"), glyph("a")]}, "glyphs[1].name")

    def test_advance_rules(self):
        for v in [99, 1501, True, 500.0, "500", None]:
            self.bad({"title": "T", "glyphs": [glyph(advance=v)]}, "glyphs[0].advance")
        self.ok({"title": "T", "glyphs": [glyph(advance=100), glyph("B", advance=1500)]})

    def test_point_rules(self):
        base = [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}]
        for bad_pt, field in [
            ({"x": 1.5, "y": 0}, "glyphs[0].points[0].x"),
            ({"x": True, "y": 0}, "glyphs[0].points[0].x"),
            ({"x": "1", "y": 0}, "glyphs[0].points[0].x"),
            ({"x": -1001, "y": 0}, "glyphs[0].points[0].x"),
            ({"x": 2001, "y": 0}, "glyphs[0].points[0].x"),
            ({"x": 0, "y": 2001}, "glyphs[0].points[0].y"),
            ({"x": 0}, "glyphs[0].points[0].y"),
            ([0, 0], "glyphs[0].points[0]"),
        ]:
            pts = copy.deepcopy(base)
            pts[0] = bad_pt
            self.bad({"title": "T", "glyphs": [glyph(points=pts)]}, field)
        self.ok({"title": "T", "glyphs": [glyph(points=[{"x": -1000, "y": -1000}, {"x": 2000, "y": -1000}, {"x": 2000, "y": 2000}])]})

    def test_point_count_limits(self):
        self.bad({"title": "T", "glyphs": [glyph(points=[{"x": 0, "y": 0}, {"x": 1, "y": 1}])]}, "glyphs[0].points")
        many = [{"x": i, "y": (i * i) % 50 + (i % 2)} for i in range(65)]
        self.bad({"title": "T", "glyphs": [glyph(points=many)]}, "glyphs[0].points")
        sixty4 = [{"x": i, "y": (i % 2) * 10} for i in range(63)] + [{"x": 63, "y": 500}]
        self.ok({"title": "T", "glyphs": [glyph(points=sixty4)]})

    def test_contour_degenerate(self):
        # collinear (zero area, nonzero vertical extent)
        self.bad({"title": "T", "glyphs": [glyph(points=[{"x": 0, "y": 0}, {"x": 10, "y": 10}, {"x": 20, "y": 20}])]}, "glyphs[0].points")
        # flat (zero vertical extent)
        self.bad({"title": "T", "glyphs": [glyph(points=[{"x": 0, "y": 5}, {"x": 10, "y": 5}, {"x": 20, "y": 5}])]}, "glyphs[0].points")
        # consecutive equal
        self.bad({"title": "T", "glyphs": [glyph(points=[{"x": 0, "y": 0}, {"x": 0, "y": 0}, {"x": 10, "y": 10}, {"x": 0, "y": 20}])]}, "glyphs[0].points")
        # last equals first
        self.bad({"title": "T", "glyphs": [glyph(points=[{"x": 0, "y": 0}, {"x": 10, "y": 10}, {"x": 0, "y": 20}, {"x": 0, "y": 0}])]}, "glyphs[0].points")

    def test_either_winding_and_overshoot_ok(self):
        pts = [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 1900}]
        self.ok({"title": "T", "cap_height": 300, "glyphs": [glyph(points=pts), glyph("B", points=list(reversed(pts)))]})

    def test_glyph_count_limit(self):
        def gl(n):
            return [glyph("g%d" % i) for i in range(n)]
        self.ok({"title": "T", "glyphs": gl(128)})
        self.bad({"title": "T", "glyphs": gl(129)}, "glyphs")

    def test_put_requires_everything(self):
        self.bad({"title": "T", "cap_height": 700, "glyphs": []}, "version", True)
        self.bad({"version": 1, "cap_height": 700, "glyphs": []}, "title", True)
        self.bad({"version": 1, "title": "T", "glyphs": []}, "cap_height", True)
        self.bad({"version": 1, "title": "T", "cap_height": 700}, "glyphs", True)
        self.bad({"version": True, "title": "T", "cap_height": 700, "glyphs": []}, "version", True)
        self.ok({"version": 1, "title": "T", "cap_height": 700, "glyphs": []}, True)

    def test_glyph_ids(self):
        g1, g2 = glyph("A"), glyph("B")
        g1["id"] = g2["id"] = 3
        self.bad({"title": "T", "glyphs": [g1, g2]}, "glyphs[1].id")
        g1["id"] = "x"
        self.bad({"title": "T", "glyphs": [g1]}, "glyphs[0].id")
        g1["id"] = True
        self.bad({"title": "T", "glyphs": [g1]}, "glyphs[0].id")

    def test_non_object_body_and_glyph(self):
        self.bad([], "body")
        self.bad({"title": "T", "glyphs": ["x"]}, "glyphs[0]")
        self.bad({"title": "T", "glyphs": {}}, "glyphs")

    def test_details_capped_at_50(self):
        gs = [{"name": "", "advance": 0, "points": 1} for _ in range(40)]
        clean, errors = validate_font({"title": "", "glyphs": gs}, False)
        self.assertIsNone(clean)
        self.assertEqual(len(errors.items), 50)
        self.assertTrue(errors.truncated)


if __name__ == "__main__":
    unittest.main()
