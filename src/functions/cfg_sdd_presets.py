"""Ready-made SDDs, stored as data (JSON-compatible dicts). Grammar of Section 2.2 format.
Both are our own (not from the book or the assignment): checksums over a digit string."""

_GRAMMAR = "4\nS -> L\nL -> DM\nM -> L e\nD -> 0 1 2 3 4 5 6 7 8 9"

LUHN = {
    "id": "luhn",
    "name": "Luhn checksum (right to left)",
    "description": "Counting from the rightmost digit (k = 0), every digit with odd k is doubled (minus 9 if > 9). "
                   "D.k is inherited from the right-hand sibling M.cnt, so the SDD is neither S- nor L-attributed.",
    "grammar": _GRAMMAR,
    "attributes": {
        "S": {"syn": ["sum", "valid"]},
        "L": {"syn": ["cnt", "sum"]},
        "M": {"syn": ["cnt", "sum"]},
        "D": {"inh": ["k"], "syn": ["s"]},
    },
    "main": "S.valid",
    "rules": {
        "S -> L": ["S.sum = L.sum", "S.valid = L.sum % 10 == 0"],
        "L -> DM": ["D.k = M.cnt", "L.cnt = M.cnt + 1", "L.sum = D.s + M.sum"],
        "M -> L": ["M.cnt = L.cnt", "M.sum = L.sum"],
        "M -> e": ["M.cnt = 0", "M.sum = 0"],
        "D -> 0 1 2 3 4 5 6 7 8 9": [
            "D.s = (int($1.lexval) * 2 - 9 * (int($1.lexval) * 2 > 9)) if D.k % 2 == 1 else int($1.lexval)"],
    },
    "circularVariant": {"L -> DM": ["D.k = M.cnt + D.s", "L.cnt = M.cnt + 1", "L.sum = D.s + M.sum"]},
    "samples": ["79927398713", "0", "4", "1234", "49927398716", "12a", "0" * 40],
}

WEIGHTED = {
    "id": "weighted",
    "name": "Position-weighted checksum (left to right)",
    "description": "The i-th digit from the left (i = 1, 2, ...) is multiplied by i; the string is valid when the "
                   "total is a multiple of 11. The position travels down from the left, so the SDD is L-attributed.",
    "grammar": _GRAMMAR,
    "attributes": {
        "S": {"syn": ["sum", "valid"]},
        "L": {"inh": ["pos"], "syn": ["sum"]},
        "M": {"inh": ["pos"], "syn": ["sum"]},
        "D": {"inh": ["pos"], "syn": ["s"]},
    },
    "main": "S.valid",
    "rules": {
        "S -> L": ["L.pos = 0", "S.sum = L.sum", "S.valid = L.sum % 11 == 0"],
        "L -> DM": ["D.pos = L.pos", "M.pos = L.pos + 1", "L.sum = D.s + M.sum"],
        "M -> L": ["L.pos = M.pos", "M.sum = L.sum"],
        "M -> e": ["M.sum = 0"],
        "D -> 0 1 2 3 4 5 6 7 8 9": ["D.s = int($1.lexval) * (D.pos + 1)"],
    },
    "circularVariant": {"L -> DM": ["D.pos = L.pos + D.s", "M.pos = L.pos + 1", "L.sum = D.s + M.sum"]},
    "samples": ["0", "1", "9", "123456", "0123456789", "00", "5x", "1" * 30],
}

PRESETS = {p["id"]: p for p in (LUHN, WEIGHTED)}
