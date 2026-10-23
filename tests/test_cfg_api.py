"""HTTP layer of the new stages and the connection of the whole server (every blueprint on one app)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from app import app

EX1 = "3\nS -> S+T T\nT -> T*F F\nF -> (S) i"
EX2 = "3\nS -> AB\nA -> aA d\nB -> bBc e"


@pytest.fixture()
def c():
    app.config["TESTING"] = True
    return app.test_client()


def post(c, url, body=None, **kw):
    return c.post(url, json=body, **kw)


def test_server_is_connected_and_all_pages_load(c):
    assert c.get("/health").get_json()["status"] == "ok"
    for url in ("/", "/grammar/ui", "/sdd/ui", "/minimize/ui"):
        r = c.get(url)
        assert r.status_code == 200 and b"Formal Languages" in r.data, url
        assert b"/static/app.css" in r.data
    paths = {row["path"] for row in c.get("/api").get_json()}
    for p in ("/convert", "/simulate", "/minimize", "/minimize/compare", "/grammar/analyze", "/grammar/parse",
              "/grammar/to-nfa", "/sdd/evaluate", "/sdd/describe"):
        assert p in paths, p
    assert c.get("/static/vendor/viz-standalone.js").status_code == 200       # no CDN needed
    assert c.get("/static/app.css").status_code == 200 and c.get("/static/common.js").status_code == 200


def test_errors_are_json_never_html(c):
    for r in (c.get("/nope"), c.get("/convert"), c.post("/convert", data="junk"), c.post("/convert", json=[1]),
              c.post("/simulate", json={}), c.post("/grammar/sets", data=""), c.post("/sdd/evaluate", json={"preset": "zzz", "input": "1"}),
              c.post("/grammar/sets", json={"grammar": 5})):
        assert r.is_json and "error" in r.get_json() and r.status_code in (400, 404, 405), r.get_data()


def test_assignment1_and_2_still_work_on_the_shared_server(c):
    nfa = {"states": [0, 1], "alphabet": ["a"], "initial": 0, "accepting": [1],
           "transitions": [{"from": 0, "symbol": "a", "to": 1}]}
    dfa = post(c, "/convert", nfa).get_json()
    assert dfa["acceptingStates"] == ["1"]
    assert post(c, "/minimize", dfa).get_json()["cases"][0]["isMinimal"] in (True, False)
    assert c.get("/minimize/example").status_code == 200
    bad = post(c, "/convert", {"states": 5, "alphabet": [], "initial": 0, "accepting": [], "transitions": []})
    assert bad.status_code == 400


def test_analyze_cases_of_section_2_2_2(c):
    cases = {EX1: (3, "Grammar is SLR(1)."), EX2: (1, "Select a parser (T: for LL(1), B: for SLR(1), Q: quit):"),
             "1\nS -> SS a": (4, "Grammar is neither LL(1) nor SLR(1)."), "2\nS -> aSb A\nA -> e": (1, None)}
    for g, (case, msg) in cases.items():
        d = post(c, "/grammar/analyze", {"grammar": g}).get_json()
        assert d["case"] == case and (msg is None or d["message"] == msg)
    # LL(1) but not SLR(1) (case 2): S -> Aa | b A ... use a known grammar: A -> aA | e  with S -> A
    d = post(c, "/grammar/analyze", {"grammar": "2\nS -> A\nA -> aA e"}).get_json()
    assert d["case"] in (1, 2)


def test_sets_endpoint_accepts_text_plain(c):
    r = c.post("/grammar/sets", data=EX2, content_type="text/plain")
    assert r.status_code == 200 and "First(B) = {b, e}" in r.get_json()["lines"]
    assert r.get_json()["steps"]["first"] and r.get_json()["steps"]["follow"]


def test_parse_endpoint_with_trace_and_tree(c):
    r = post(c, "/grammar/parse", {"grammar": EX2, "inputs": ["d", "adbc", "a", "e"], "parser": "ll1", "trace": True}).get_json()
    assert [x["answer"] for x in r["results"]] == ["yes", "yes", "no", "no"]
    assert r["results"][1]["trace"][-1]["action"] == "accept" and r["results"][1]["tree"]["symbol"] == "S"
    r = post(c, "/grammar/parse", {"grammar": EX1, "inputs": ["i+i", "(i)", "(i+i)*i)"]}).get_json()
    assert r["parser"] == "slr1" and [x["answer"] for x in r["results"]] == ["yes", "yes", "no"]
    assert post(c, "/grammar/parse", {"grammar": EX1, "inputs": ["i"], "parser": "ll1"}).status_code == 400
    assert post(c, "/grammar/parse", {"grammar": "1\nS -> SS a", "inputs": ["a"]}).get_json()["results"] == []


def test_regular_grammar_bridge_reaches_the_earlier_assignments(c):
    g = "2\nS -> aS bS aA\nA -> b"                        # strings over {a,b} ending in ab
    nfa = post(c, "/grammar/to-nfa", {"grammar": g}).get_json()
    dfa = post(c, "/convert", nfa).get_json()
    sim = lambda w: post(c, "/simulate", {"transitions": dfa["transitions"], "initial": dfa["dfaStates"][0],
                                          "accepting": dfa["acceptingStates"], "input": w}).get_json()["accepted"]
    parse = lambda w: post(c, "/grammar/parse", {"grammar": g, "inputs": [w]}).get_json()
    gl = {w: sim(w) for w in ("ab", "aab", "bab", "abb", "a", "b", "bbab")}
    assert gl == {"ab": True, "aab": True, "bab": True, "abb": False, "a": False, "b": False, "bbab": True}
    assert post(c, "/minimize", dfa).get_json()["cases"][0]["stats"]["statesMinimized"] == 3
    assert post(c, "/grammar/to-nfa", {"grammar": "1\nS -> aSb e"}).status_code == 400


def test_sdd_endpoints(c):
    assert {p["id"] for p in c.get("/sdd/presets").get_json()} == {"luhn", "weighted"}
    assert c.get("/sdd/presets/luhn").get_json()["main"] == "S.valid"
    assert c.get("/sdd/presets/zzz").status_code == 404
    d = post(c, "/sdd/describe", {"preset": "luhn"}).get_json()
    assert d["classification"]["verdict"].startswith("neither") and d["rules"]
    r = post(c, "/sdd/evaluate", {"preset": "luhn", "inputs": ["79927398713", "x"]}).get_json()
    assert r["results"][0]["main"]["value"] is True and r["results"][1]["accepted"] is False
    r = post(c, "/sdd/evaluate", {"preset": "weighted", "circular": True, "input": "18"}).get_json()
    assert r["results"][0]["circular"] is True
    custom = c.get("/sdd/presets/weighted").get_json()
    custom.pop("samples"); custom["rules"]["M -> e"] = ["M.sum = 0", "M.sum = 1"]
    assert post(c, "/sdd/evaluate", {"definition": custom, "input": "1"}).status_code == 400
    assert post(c, "/sdd/evaluate", {"preset": "luhn", "inputs": ["1"] * 51}).status_code == 400
