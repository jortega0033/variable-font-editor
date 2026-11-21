"""Pure validation of font payloads. No I/O."""

import unicodedata

TITLE_MAX = 60
GLYPH_NAME_MAX = 24
CAP_MIN, CAP_MAX, CAP_DEFAULT = 300, 1000, 700
ADVANCE_MIN, ADVANCE_MAX = 100, 1500
POINTS_MIN, POINTS_MAX = 3, 64
COORD_MIN, COORD_MAX = -1000, 2000
MAX_GLYPHS = 128
MAX_FONTS = 200
MAX_DETAILS = 50
MAX_ID = 2**63 - 1


class Errors:
    def __init__(self):
        self.items = []
        self.truncated = False

    def add(self, field, message):
        if len(self.items) >= MAX_DETAILS:
            self.truncated = True
            return
        self.items.append({"field": field, "message": message})

    def __bool__(self):
        return bool(self.items)


def is_int(v):
    return type(v) is int  # excludes bool


def _bad_chars(s):
    for ch in s:
        if unicodedata.category(ch) in ("Cc", "Cs", "Zl", "Zp"):
            return True
    return False


def _clean_text(value, field, maxlen, errors, label):
    if not isinstance(value, str):
        errors.add(field, f"{label} must be a string")
        return None
    s = value.strip()
    if _bad_chars(s):
        errors.add(field, f"{label} must not contain control characters")
        return None
    if not 1 <= len(s) <= maxlen:
        errors.add(field, f"{label} must be 1-{maxlen} characters")
        return None
    return s


def _int_in_range(value, field, lo, hi, errors, label):
    if not is_int(value):
        errors.add(field, f"{label} must be an integer")
        return None
    if not lo <= value <= hi:
        errors.add(field, f"{label} must be between {lo} and {hi}")
        return None
    return value


def validate_contour(points):
    """Return list of messages for a list of {'x','y'} dicts (already typed/ranged)."""
    msgs = []
    n = len(points)
    for j in range(n):
        a, b = points[j], points[(j + 1) % n]
        if a["x"] == b["x"] and a["y"] == b["y"]:
            msgs.append(f"points[{j}] and points[{(j + 1) % n}] are identical consecutive points")
    ys = [p["y"] for p in points]
    if max(ys) - min(ys) <= 0:
        msgs.append("contour must have a vertical extent greater than zero")
    twice_area = 0
    for j in range(n):
        a, b = points[j], points[(j + 1) % n]
        twice_area += a["x"] * b["y"] - b["x"] * a["y"]
    if twice_area == 0:
        msgs.append("contour must enclose a non-zero area")
    return msgs


def _validate_glyph(g, i, errors):
    base = f"glyphs[{i}]"
    if not isinstance(g, dict):
        errors.add(base, "glyph must be an object")
        return None
    out = {}
    if "id" in g:
        gid = g["id"]
        if not is_int(gid) or not 1 <= gid <= MAX_ID:
            errors.add(f"{base}.id", "id must be a positive integer")
        else:
            out["id"] = gid
    out["name"] = _clean_text(g.get("name"), f"{base}.name", GLYPH_NAME_MAX, errors, "name")
    out["advance"] = _int_in_range(
        g.get("advance"), f"{base}.advance", ADVANCE_MIN, ADVANCE_MAX, errors, "advance"
    )
    pts = g.get("points")
    clean_pts = None
    if not isinstance(pts, list):
        errors.add(f"{base}.points", "points must be a list")
    elif not POINTS_MIN <= len(pts) <= POINTS_MAX:
        errors.add(f"{base}.points", f"points must contain {POINTS_MIN}-{POINTS_MAX} points")
    else:
        ok = True
        cp = []
        for j, p in enumerate(pts):
            if not isinstance(p, dict):
                errors.add(f"{base}.points[{j}]", "point must be an object with x and y")
                ok = False
                continue
            xy = {}
            for axis in ("x", "y"):
                v = _int_in_range(
                    p.get(axis), f"{base}.points[{j}].{axis}", COORD_MIN, COORD_MAX, errors, axis
                )
                if v is None:
                    ok = False
                xy[axis] = v
            cp.append(xy)
        if ok:
            msgs = validate_contour(cp)
            for m in msgs:
                errors.add(f"{base}.points", m)
            if not msgs:
                clean_pts = cp
    out["points"] = clean_pts
    return out


def validate_font(body, require_version):
    """Validate a create/replace payload.

    Returns (clean, errors). clean is None when errors is non-empty.
    """
    errors = Errors()
    if not isinstance(body, dict):
        errors.add("body", "request body must be a JSON object")
        return None, errors
    clean = {}

    if require_version:
        v = body.get("version")
        if not is_int(v) or v < 1 or v > MAX_ID:
            errors.add("version", "version must be a positive integer")
        else:
            clean["version"] = v

    clean["title"] = _clean_text(body.get("title"), "title", TITLE_MAX, errors, "title")

    if "cap_height" not in body and not require_version:
        clean["cap_height"] = CAP_DEFAULT
    else:
        clean["cap_height"] = _int_in_range(
            body.get("cap_height"), "cap_height", CAP_MIN, CAP_MAX, errors, "cap_height"
        )

    glyphs_in = body.get("glyphs", [] if not require_version else None)
    glyphs = []
    if not isinstance(glyphs_in, list):
        errors.add("glyphs", "glyphs must be a list")
    elif len(glyphs_in) > MAX_GLYPHS:
        errors.add("glyphs", f"a font may have at most {MAX_GLYPHS} glyphs")
    else:
        seen_names = {}
        seen_ids = {}
        for i, g in enumerate(glyphs_in):
            cg = _validate_glyph(g, i, errors)
            if cg is None:
                continue
            glyphs.append(cg)
            if cg["name"] is not None:
                key = cg["name"].casefold()
                if key in seen_names:
                    errors.add(
                        f"glyphs[{i}].name",
                        f"name duplicates glyphs[{seen_names[key]}] (case-insensitive)",
                    )
                else:
                    seen_names[key] = i
            if "id" in cg:
                if cg["id"] in seen_ids:
                    errors.add(f"glyphs[{i}].id", f"id duplicates glyphs[{seen_ids[cg['id']]}]")
                else:
                    seen_ids[cg["id"]] = i
    clean["glyphs"] = glyphs

    if errors:
        return None, errors
    return clean, errors
