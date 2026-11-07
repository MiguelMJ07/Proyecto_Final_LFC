"""Deep parse trees must not turn into HTTP 500. The JSON encoder recurses once per tree level, and an annotated tree is
nested about 3 levels per symbol, so with Python's default recursion limit /sdd/evaluate failed at about 300 digits and
/grammar/parse at about 450 symbols, below the limits the server announces (400 digits, 2000 symbols)."""
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import app as server  # noqa: E402


def _post(path, body):
    """Like the development server: the request runs in a new thread (smaller stack than the main thread on Windows)."""
    out = {}

    def run():
        r = server.app.test_client().post(path, json=body)
        out["status"], out["json"] = r.status_code, r.get_json()

    t = threading.Thread(target=run)
    t.start()
    t.join()
    return out


def test_sdd_evaluates_the_longest_allowed_string():
    out = _post("/sdd/evaluate", {"preset": "luhn", "input": "1" * 400})
    assert out["status"] == 200 and "error" not in str(out["json"])[:200]


def test_grammar_parse_accepts_a_very_deep_tree_with_both_parsers():
    for parser in ("ll1", "slr1"):
        out = _post("/grammar/parse", {"grammar": "1\nS -> aS e", "inputs": ["a" * 1990], "parser": parser})
        assert out["status"] == 200 and out["json"]["results"][0]["answer"] == "yes", parser
