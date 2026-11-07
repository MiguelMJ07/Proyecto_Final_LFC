"""Panic-mode recovery, regular-grammar comparison, practice mode, LaTeX export, saved sessions, API docs."""
import os
import random
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from app import app
from functions import practice
from functions.cfg_grammar import GrammarError, parse_grammar
from functions.cfg_ll1 import LL1
from functions.cfg_slr1 import SLR1
from functions.latex_export import esc, grammar_report, sdd_report
from functions.cfg_sdd import SDD, evaluate
from functions.cfg_sdd_presets import LUHN
from functions.sessions_store import MAX_PAYLOAD_BYTES, SessionStore
from tests.test_cfg import random_grammar, productive

BOOK_428 = "5\nS -> TX\nX -> +TX e\nT -> FY\nY -> *FY e\nF -> (S) i"      # grammar (4.28), E=S, E'=X, T'=Y, id=i
EX2 = "3\nS -> AB\nA -> aA d\nB -> bBc e"


@pytest.fixture()
def c(tmp_path):
    app.config["TESTING"] = True
    app.config["SESSIONS_DB"] = str(tmp_path / "sessions.db")
    return app.test_client()


# ---------------------------------------------------------------- panic mode (Section 4.4.5)
def test_panic_mode_follows_figure_4_23():
    ll = LL1(parse_grammar(BOOK_428))
    r = ll.parse_recover("+i*+i", trace=True)               # Example 4.36 of the book: + id * + id
    actions = [s["action"] for s in r["trace"]]
    assert actions[0] == "error: skip +"                    # blank entry: the input symbol is skipped
    assert "error: M[F,+] = synch; pop F" in actions        # synch entry: the nonterminal on top is popped
    assert not r["accepted"] and len(r["errors"]) == 2


def test_recovery_on_valid_input_reports_no_errors():
    ll = LL1(parse_grammar(BOOK_428))
    r = ll.parse_recover("i+i*i")
    assert r["accepted"] and r["errors"] == []


def test_missing_terminal_is_popped_as_if_inserted():
    r = LL1(parse_grammar(BOOK_428)).parse_recover("(i")
    assert [e["action"] for e in r["errors"]] == ["pop ) (as if ')' had been inserted)"]


def test_recovery_always_terminates_on_random_input():
    rng = random.Random(11)
    n = 0
    for _ in range(300):
        try:
            g = parse_grammar(random_grammar(rng))
        except GrammarError:
            continue
        ll = LL1(g)
        if not ll.is_ll1 or productive(g) != set(g.nonterminals):
            continue
        n += 1
        for _ in range(8):
            w = "".join(rng.choice("abc") for _ in range(rng.randint(0, 9)))
            r = ll.parse_recover(w)
            assert r["error"] is None, (g.prods, w)
    assert n > 20


def test_recover_option_over_http(c):
    r = c.post("/grammar/parse", json={"grammar": BOOK_428, "inputs": ["+i*+i", "i+i"], "parser": "ll1", "recover": True, "trace": True}).get_json()
    bad, good = r["results"]
    assert bad["answer"] == "no" and len(bad["errors"]) == 2 and good["answer"] == "yes" and good["errors"] == []
    assert c.post("/grammar/parse", json={"grammar": "3\nS -> S+T T\nT -> T*F F\nF -> (S) i", "inputs": ["i"], "recover": True}).status_code == 400
    assert c.post("/grammar/parse", json={"grammar": BOOK_428, "inputs": ["i"], "recover": "yes"}).status_code == 400


# ---------------------------------------------------------------- comparing regular grammars
ENDS_AB_1 = "2\nS -> aS bS aA\nA -> b"
ENDS_AB_2 = "3\nS -> aA bS\nA -> bC aA\nC -> e aA bS"


def test_equivalent_regular_grammars(c):
    r = c.post("/grammar/compare", json={"grammars": [ENDS_AB_1, ENDS_AB_2]}).get_json()
    assert r["equivalent"] is True and r["alphabet"] == ["a", "b"]


def test_different_regular_grammars_give_a_shortest_counterexample(c):
    ends_ba = "2\nS -> aS bS bA\nA -> a"
    r = c.post("/grammar/compare", json={"grammars": [ENDS_AB_1, ends_ba]}).get_json()
    assert r["equivalent"] is False
    w = r["counterexample"]
    in_ab, in_ba = w.endswith("ab"), w.endswith("ba")
    assert in_ab != in_ba and r["acceptedBy"] == ("first" if in_ab else "second")
    assert len(w) == 2                                       # no shorter string distinguishes them


def test_different_alphabets_are_unified(c):
    r = c.post("/grammar/compare", json={"grammars": ["1\nS -> aS e", "2\nS -> aS bT e\nT -> bT e"]}).get_json()
    assert r["equivalent"] is False and r["alphabet"] == ["a", "b"]


def test_compare_rejects_non_regular_and_bad_input(c):
    assert c.post("/grammar/compare", json={"grammars": [ENDS_AB_1, "1\nS -> aSb e"]}).status_code == 400
    assert c.post("/grammar/compare", json={"grammars": [ENDS_AB_1]}).status_code == 400
    assert c.post("/grammar/compare", json={}).status_code == 400


# ---------------------------------------------------------------- practice mode
def perfect_answer(kind, ex):
    g = parse_grammar(ex["grammar"])
    if kind == "sets":
        return {"first": {A: " ".join(sorted(g.first[A])) for A in g.nonterminals},
                "follow": {A: " ".join(sorted(g.follow[A])) for A in g.nonterminals}}
    if kind == "ll1_table":
        ll = LL1(g)
        return {"isLL1": ll.is_ll1, "cells": {f"{A},{a}": ", ".join(map(str, cell)) for (A, a), cell in ll.table.items()}}
    if kind == "derivation":
        r = LL1(g).parse(ex["input"], trace=True)
        return {"productions": [s["production"] for s in r["trace"] if "production" in s], "result": "yes" if r["accepted"] else "no"}
    slr = SLR1(g)
    return {"closure": "\n".join(slr.item_str(p, d) for p, d in sorted(slr.states[0])), "numStates": len(slr.states), "isSLR1": slr.is_slr1}


@pytest.mark.parametrize("kind", list(practice.KINDS))
def test_practice_perfect_answers_get_full_marks(c, kind):
    for seed in (1, 2, 3, 17, 4242):
        for diff in (1, 2, 3):
            ex = c.get(f"/practice/new?kind={kind}&seed={seed}&difficulty={diff}").get_json()
            assert ex == c.get(f"/practice/new?kind={kind}&seed={seed}&difficulty={diff}").get_json()      # reproducible
            r = c.post("/practice/check", json={"kind": kind, "seed": seed, "difficulty": diff, "answer": perfect_answer(kind, ex)}).get_json()
            assert r["score"]["correct"] == r["score"]["total"] > 0, (kind, seed, diff, [i for i in r["items"] if not i["ok"]])


@pytest.mark.parametrize("kind", list(practice.KINDS))
def test_practice_wrong_answers_are_marked_and_explained(c, kind):
    r = c.post("/practice/check", json={"kind": kind, "seed": 5, "difficulty": 2, "answer": {}}).get_json()
    assert r["score"]["correct"] < r["score"]["total"] and r["solution"]
    assert any(not i["ok"] and i["label"] for i in r["items"])


def test_practice_generated_grammars_respect_the_assignment_assumptions():
    for kind in practice.KINDS:
        for seed in range(60):
            ex = practice.new_exercise(kind, seed, 1 + seed % 3)
            g = parse_grammar(ex["grammar"])
            assert productive(g) == set(g.nonterminals) and len(g.prods) <= practice.MAX_PRODS[ex["difficulty"]] + 3
            if kind == "derivation":
                assert LL1(g).is_ll1 and ex["input"]
            if kind == "sets":
                assert any(not b for _, b in g.prods)


def test_practice_parameter_validation(c):
    assert c.get("/practice/new?kind=zzz").status_code == 400
    assert c.get("/practice/new?kind=sets&seed=x").status_code == 400
    assert c.get("/practice/new?kind=sets&difficulty=9").status_code == 400
    assert c.get("/practice/new?kind=sets").get_json()["seed"] >= 1                 # random seed when omitted
    assert c.post("/practice/check", json={"kind": "sets", "seed": 1, "answer": []}).status_code == 400
    assert c.post("/practice/check", json={"kind": "lr0", "seed": 1, "answer": {"closure": 5, "numStates": [1]}}).status_code in (200, 400)


# ---------------------------------------------------------------- LaTeX export
def test_latex_escaping():
    assert esc(r"a_b & 50% #1 {x} ^ ~ \ < > |") == r"a\_b \& 50\% \#1 \{x\} \textasciicircum{} \textasciitilde{} \textbackslash{} \textless{} \textgreater{} \textbar{}"


def test_latex_reports_contain_the_report_tables():
    tex = grammar_report(parse_grammar(EX2), ["adbc", "a"])
    for needle in ("FIRST and FOLLOW", "Algorithm 4.31", "LR(0) item sets", "ACTION and GOTO", "Parsing steps", r"\end{document}"):
        assert needle in tex
    assert tex.count(r"\begin{table}") == tex.count(r"\end{table}") and tex.count("{longtable}") == 2
    tex = sdd_report(SDD(LUHN), evaluate(SDD(LUHN), "79927398713"))
    assert "Attribute table" in tex and "Semantic rules" in tex and "neither S-attributed nor L-attributed" in tex and "Evaluation order" in tex


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex is not installed")
def test_latex_reports_compile(tmp_path):
    docs = {"g1": grammar_report(parse_grammar("3\nS -> S+T T\nT -> T*F F\nF -> (S) i"), ["i+i", "(i+i)*i)"]),
            "g2": grammar_report(parse_grammar(EX2), ["adbc", "e", "a"]),
            "g3": grammar_report(parse_grammar("1\nS -> SS a"), ["a"]),
            "g4": grammar_report(parse_grammar("2\nS -> [S] #&\nB -> ~^_%"), ["[#]"]),
            "s1": sdd_report(SDD(LUHN), evaluate(SDD(LUHN), "79927398713"))}
    for name, tex in docs.items():
        (tmp_path / f"{name}.tex").write_text(tex, encoding="utf-8")
        r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", f"{name}.tex"], cwd=tmp_path, capture_output=True, text=True)
        assert r.returncode == 0, (name, [l for l in r.stdout.splitlines() if l.startswith("!")][:3])


def test_latex_endpoints(c):
    r = c.post("/export/latex/grammar", json={"grammar": EX2, "inputs": ["adbc"]}).get_json()
    assert r["filename"] == "grammar_report.tex" and r["tex"].startswith(r"\documentclass")
    d = c.post("/export/latex/grammar?download=1", json={"grammar": EX2})
    assert d.headers["Content-Disposition"] == 'attachment; filename="grammar_report.tex"' and d.mimetype == "application/x-tex"
    s = c.post("/export/latex/sdd", json={"preset": "weighted", "input": "123"}).get_json()
    assert "L-attributed" in s["tex"] and "Annotated parse tree" in s["tex"]
    assert c.post("/export/latex/sdd", json={"preset": "luhn", "circular": True, "input": "18"}).get_json()["tex"].count("circular") >= 1
    assert c.post("/export/latex/grammar", json={"grammar": "x"}).status_code == 400
    assert c.post("/export/latex/grammar", json={"grammar": EX2, "inputs": ["x"] * 11}).status_code == 400
    assert c.post("/export/latex/grammar", json={"grammar": EX2, "parser": "zzz"}).status_code == 400


# ---------------------------------------------------------------- saved sessions
def test_sessions_crud(c):
    assert c.get("/sessions").get_json() == []
    r = c.post("/sessions", json={"kind": "grammar", "name": "ex2", "payload": {"grammar": EX2}})
    assert r.status_code == 201
    sid = r.get_json()["id"]
    again = c.post("/sessions", json={"kind": "grammar", "name": "ex2", "payload": {"grammar": "1\nS -> a"}}).get_json()
    assert again["id"] == sid                                                   # same (kind, name) replaces
    assert c.get(f"/sessions/{sid}").get_json()["payload"] == {"grammar": "1\nS -> a"}
    c.post("/sessions", json={"kind": "sdd", "name": "mine", "payload": {"x": 1}})
    assert [s["name"] for s in c.get("/sessions?kind=sdd").get_json()] == ["mine"] and len(c.get("/sessions").get_json()) == 2
    assert c.delete(f"/sessions/{sid}").status_code == 200 and c.get(f"/sessions/{sid}").status_code == 404
    assert c.delete(f"/sessions/{sid}").status_code == 404


def test_sessions_validation_and_limits(c, tmp_path):
    bad = [{"kind": "zzz", "name": "a", "payload": {}}, {"kind": "sdd", "name": " ", "payload": {}},
           {"kind": "sdd", "name": "x" * 61, "payload": {}}, {"kind": "sdd", "name": "a", "payload": []},
           {"kind": "sdd", "name": "a", "payload": {"big": "x" * (MAX_PAYLOAD_BYTES + 1)}}]
    for b in bad:
        assert c.post("/sessions", json=b).status_code == 400, b
    assert c.get("/sessions?kind=zzz").status_code == 400
    s = SessionStore(str(tmp_path / "full.db"))
    from functions import sessions_store
    old = sessions_store.MAX_SESSIONS
    sessions_store.MAX_SESSIONS = 2
    try:
        s.save("sdd", "a", {}); s.save("sdd", "b", {}); s.save("sdd", "a", {"v": 2})      # replacing is allowed when full
        with pytest.raises(sessions_store.SessionError):
            s.save("sdd", "c", {})
    finally:
        sessions_store.MAX_SESSIONS = old


def test_sessions_survive_a_new_store_object(tmp_path):
    p = str(tmp_path / "x" / "s.db")                                             # directory is created on demand
    SessionStore(p).save("grammar", "g", {"a": [1, 2, "é"]})
    assert SessionStore(p).list("grammar")[0]["name"] == "g"
    assert SessionStore(p).get(1)["payload"] == {"a": [1, 2, "é"]}


# ---------------------------------------------------------------- docs and pages
def test_openapi_covers_every_route_and_docs_work_offline(c):
    spec = c.get("/openapi.json").get_json()
    assert spec["openapi"].startswith("3.")
    missing = [r.rule for r in app.url_map.iter_rules()
               if r.endpoint != "static" and re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", r.rule) not in spec["paths"]]
    assert missing == []
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            assert op["tags"] and op["summary"], (path, method)
    page = c.get("/docs")
    assert page.status_code == 200 and b"/static/vendor/swagger/swagger-ui-bundle.js" in page.data
    assert c.get("/static/vendor/swagger/swagger-ui-bundle.js").status_code == 200
    assert c.get("/static/vendor/swagger/swagger-ui.css").status_code == 200


def test_new_pages_load(c):
    for url in ("/practice/ui", "/docs", "/grammar/ui", "/sdd/ui"):
        r = c.get(url)
        assert r.status_code == 200 and b"/practice/ui" in r.data            # the shared rail links to practice mode
