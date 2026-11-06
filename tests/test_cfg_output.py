"""The other output formats of Items 1-2 (extra): POST /grammar/report (plain text, the same as cli/main.py),
POST /grammar/export (CSV and LaTeX tables) and POST /grammar/graph (Graphviz DOT and SVG drawings)."""
import csv
import io
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from app import app
from functions.cfg_export import tex
from functions.cfg_grammar import parse_grammar, sets_json
from functions.cfg_ll1 import LL1
from functions.cfg_slr1 import SLR1

ROOT = os.path.join(os.path.dirname(__file__), "..")
CLI = os.path.join(ROOT, "cli", "main.py")
EX1 = "3\nS -> S+T T\nT -> T*F F\nF -> (S) i"
EX2 = "3\nS -> AB\nA -> aA d\nB -> bBc e"
NEITHER = "1\nS -> SS a"
KOZEN_212 = "2\nS -> [B [SB [BS [SBS\nB -> ]"
EPS = "2\nS -> aSb A\nA -> e"
HUGE = "1\nS -> " + "a" * 450                 # more than 400 LR(0) states
SVG = "{http://www.w3.org/2000/svg}"


@pytest.fixture()
def c():
    app.config["TESTING"] = True
    return app.test_client()


def run_cli(stdin, *flags):
    return subprocess.run([sys.executable, CLI, *flags], input=stdin, capture_output=True, text=True,
                          timeout=60).stdout


def example(name):
    with open(os.path.join(ROOT, "examples", name)) as f:
        return f.read()


# ------------------------------------------------------------------ /grammar/report
@pytest.mark.parametrize("name", ["ex1.txt", "ex2.txt", "ex3.txt"])
@pytest.mark.parametrize("flags", [(), ("--sets",), ("--sets", "--tables"), ("--sets", "--tables", "--trace")])
def test_text_report_is_exactly_the_cli_output(c, name, flags):
    stdin = example(name)
    query = "&".join(f"{f} =true".replace("-", "").replace(" ", "") for f in ("--sets", "--tables", "--trace")
                     if f in flags) or "sets=false"
    r = c.post(f"/grammar/report?{query}", data=stdin, content_type="text/plain")
    assert r.status_code == 200 and r.mimetype == "text/plain"
    assert r.get_data(as_text=True) == run_cli(stdin, *flags)


@pytest.mark.parametrize("grammar,inputs,parser,choice", [
    (EX1, ["i+i", "(i)", "(i+i)*i)"], "auto", None),          # case 3: SLR(1) only
    (EX2, ["d", "adbc", "a", "e"], "auto", "T"),                # case 1: auto takes LL(1)
    (EX2, ["d", "adbc", "a"], "slr1", "B"),
    (NEITHER, ["a"], "auto", None),                             # case 4: strings are not read
    (EPS, ["aabb", "e", "", "aab"], "ll1", "T"),                # "" and "e" are both the empty string
    (KOZEN_212, ["[]", "[[]]", "[][]", "[[]", "]["], "auto", None),
])
def test_json_report_matches_the_cli_on_the_same_input(c, grammar, inputs, parser, choice):
    body = {"grammar": grammar, "inputs": inputs, "parser": parser, "tables": True, "trace": True}
    r = c.post("/grammar/report", json=body)
    assert r.status_code == 200 and r.mimetype == "text/plain"
    stdin_lines = grammar.split("\n") + ([choice] if choice else []) + [w or "e" for w in inputs] + ["", "Q", ""]
    assert r.get_data(as_text=True) == run_cli("\n".join(stdin_lines), "--sets", "--tables", "--trace")


def test_report_defaults_and_flags(c):
    r = c.post("/grammar/report", json={"grammar": EX1, "input": "i+i"}).get_data(as_text=True)
    assert r.splitlines() == ["First(F) = {(, i}", "First(S) = {(, i}", "First(T) = {(, i}", "Follow(F) = {), *, +, $}",
                              "Follow(S) = {), +, $}", "Follow(T) = {), *, +, $}", "Grammar is SLR(1).", "yes"]
    r = c.post("/grammar/report", json={"grammar": EX1, "input": "i", "sets": False}).get_data(as_text=True)
    assert r == "Grammar is SLR(1).\nyes\n"
    r = c.post("/grammar/report", json={"grammar": EX1, "sets": False, "tables": True}).get_data(as_text=True)
    assert "LL(1) table (Algorithm 4.31):" in r and "ACTION[0,i] = shift 5" in r and "GOTO[0,S] = 3" in r


@pytest.mark.parametrize("body", [
    {"grammar": EX2, "parser": "x"}, {"grammar": NEITHER, "parser": "ll1"}, {"grammar": EX1, "parser": "ll1"},
    {"grammar": EX2, "inputs": 5}, {"grammar": EX2, "inputs": ["a", 3]}, {"grammar": EX2, "inputs": ["a\nb"]},
    {"grammar": EX2, "inputs": ["d"] * 201}, {"grammar": EX2, "tables": "yes"}, {"grammar": 5}, {"grammar": "2\nS -> a"},
    {"inputs": ["a"]},
])
def test_report_rejects_bad_json(c, body):
    r = c.post("/grammar/report", json=body)
    assert r.status_code == 400 and "error" in r.get_json()


@pytest.mark.parametrize("url,text", [
    ("/grammar/report", ""), ("/grammar/report", "x\n"), ("/grammar/report", "999999999\n"),
    ("/grammar/report", "2\nS -> a\n"), ("/grammar/report?trace=maybe", EX1), ("/grammar/report", EX1 + "\na" * 1001),
])
def test_report_rejects_bad_text(c, url, text):
    r = c.post(url, data=text, content_type="text/plain")
    assert r.status_code == 400 and "error" in r.get_json()


# ------------------------------------------------------------------ /grammar/export
def read_csv(r):
    assert r.status_code == 200 and r.mimetype == "text/csv", r.get_data()
    assert r.headers["Content-Disposition"].endswith('.csv"')
    return list(csv.reader(io.StringIO(r.get_data(as_text=True))))


def test_csv_sets_match_the_json_answer(c):
    for g in (EX1, EX2, EPS, KOZEN_212):
        rows = read_csv(c.post("/grammar/export", json={"grammar": g}))
        assert rows[0] == ["Nonterminal", "FIRST", "FOLLOW"]
        lines = sets_json(parse_grammar(g))["lines"]
        n = len(rows) - 1
        assert [f"First({A}) = {f}" for A, f, _ in rows[1:]] == lines[:n]
        assert [f"Follow({A}) = {f}" for A, _, f in rows[1:]] == lines[n:]


def test_csv_ll1_table(c):
    rows = read_csv(c.post("/grammar/export", json={"grammar": EX2, "table": "ll1"}))
    assert rows == [["Nonterminal", "a", "b", "c", "d", "$"],
                    ["A", "A -> aA", "", "", "A -> d", ""],
                    ["B", "", "B -> bBc", "B -> e", "", "B -> e"],
                    ["S", "S -> AB", "", "", "S -> AB", ""]]
    # A grammar that is not LL(1) keeps every production of a conflicting cell.
    rows = read_csv(c.post("/grammar/export", json={"grammar": EX1, "table": "ll1"}))
    assert rows[2][1] == "S -> S+T / S -> T"


def test_csv_slr1_table_matches_the_parser_tables(c):
    rows = read_csv(c.post("/grammar/export", json={"grammar": EX1, "table": "slr1"}))
    slr = SLR1(parse_grammar(EX1))
    header = rows[0]
    assert header[0] == "State" and header[1:7] == ["ACTION[(]", "ACTION[)]", "ACTION[*]", "ACTION[+]", "ACTION[i]",
                                                    "ACTION[$]"]
    assert header[7:] == ["GOTO[F]", "GOTO[S]", "GOTO[T]"] and len(rows) == len(slr.states) + 1
    for row in rows[1:]:
        s = int(row[0])
        for col, cell in zip(header[1:7], row[1:7]):
            a = col[len("ACTION["):-1]
            assert cell == " / ".join(slr._act_str(x) for x in slr.action.get((s, a), []))
        for col, cell in zip(header[7:], row[7:]):
            A = col[len("GOTO["):-1]
            assert cell == (str(slr.goto[(s, A)]) if (s, A) in slr.goto else "")
    # A conflict is shown, not hidden.
    rows = read_csv(c.post("/grammar/export", json={"grammar": NEITHER, "table": "slr1"}))
    assert any(" / " in cell for row in rows for cell in row)


def test_latex_tables(c):
    r = c.post("/grammar/export", json={"grammar": EX1, "table": "all", "format": "latex"})
    assert r.status_code == 200 and r.mimetype == "text/x-tex"
    t = r.get_data(as_text=True)
    assert t.count(r"\begin{tabular}") == t.count(r"\end{tabular}") == 4 and r"\documentclass" not in t
    assert r"F & \{(, i\} & \{), *, +, \$\} \\ \hline" in t                     # FIRST/FOLLOW, $ escaped
    assert r"S $\to$ S+T / S $\to$ T" in t                                       # LL(1) conflict
    assert r"0 & S$'$ $\to$ S \\ \hline" in t                                    # numbered productions
    assert r"\multicolumn{6}{c|}{ACTION} & \multicolumn{3}{c|}{GOTO}" in t
    assert r"3 &  &  &  & s7 &  & acc &  &  &  \\ \hline" in t
    assert r"2 &  & r4 & r4 & r4 &  & r4 &  &  &  \\ \hline" in t               # r4 = T -> F
    t = c.post("/grammar/export", json={"grammar": EPS, "table": "sets", "format": "latex",
                                        "standalone": True}).get_data(as_text=True)
    assert t.splitlines()[1] == r"\documentclass{article}" and t.rstrip().endswith(r"\end{document}")
    assert r"\{a, $\varepsilon$\}" in t                                          # epsilon in FIRST(S)
    t = c.post("/grammar/export", json={"grammar": EPS, "table": "ll1", "format": "latex"}).get_data(as_text=True)
    assert r"A $\to$ $\varepsilon$" in t


def test_latex_escapes_every_special_character():
    assert tex("\\{}$&#%_^~<>|[]-'`") == (r"\textbackslash{}\{\}\$\&\#\%\_\^{}\~{}\textless{}\textgreater{}"
                                          r"\textbar{}{[}{]}{-}\textquotesingle{}\textasciigrave{}")
    assert tex("a+b*(c)") == "a+b*(c)"


def test_latex_with_special_terminals(c):
    g = "2\nS -> [B %S& #_\nB -> ]"
    t = c.post("/grammar/export", json={"grammar": g, "table": "all", "format": "latex"}).get_data(as_text=True)
    body = t.split("\n", 1)[1]                                                   # skip the % comment line
    assert r"S $\to$ \%S\&" in body and r"S $\to$ \#\_" in body and r"S $\to$ {[}B" in body
    assert r"B $\to$ {]}" in body
    assert "%" not in body.replace(r"\%", "")                                   # no unescaped comment character


@pytest.mark.parametrize("body", [
    {"grammar": EX1, "table": "all"}, {"grammar": EX1, "format": "xls"}, {"grammar": EX1, "table": "x"},
    {"grammar": EX1, "format": "latex", "standalone": "yes"}, {"grammar": HUGE, "table": "slr1"},
    {"grammar": HUGE, "table": "all", "format": "latex"}, {"grammar": 5}, {"table": "sets"},
])
def test_export_rejects_bad_requests(c, body):
    r = c.post("/grammar/export", json=body)
    assert r.status_code == 400 and "error" in r.get_json()


# ------------------------------------------------------------------ /grammar/graph
def svg_root(r):
    assert r.status_code == 200 and r.mimetype == "image/svg+xml", r.get_data()
    root = ET.fromstring(r.data)                                                 # well-formed XML
    assert root.tag == SVG + "svg"
    return root


def texts(root):
    return [t.text for t in root.iter(SVG + "text")]


def test_lr0_svg_has_one_box_per_state(c):
    for g in (EX1, EX2, KOZEN_212, NEITHER):
        slr = SLR1(parse_grammar(g))
        root = svg_root(c.post("/grammar/graph", json={"grammar": g}))
        labels = texts(root)
        assert [t for t in labels if t and t[0] == "I" and t[1:].isdigit()] == [f"I{s}" for s in range(len(slr.states))]
        for I in slr.states:                                                     # every item is written
            for p, d in I:
                assert slr.item_str(p, d) in labels
        # every transition appears exactly once: as an arrow label or as "X → In" inside its source box
        arrows = sum(len(t.split(", ")) for t in labels if t and not t.startswith(("I", "GOTO")) and "->" not in t)
        listed = sum(t.count("→") for t in labels if t and t.startswith("GOTO: "))
        assert arrows + listed == len(slr.trans), g


def test_lr0_dot_is_the_automaton_of_slr1(c):
    r = c.post("/grammar/graph", json={"grammar": EX1, "format": "dot"})
    assert r.status_code == 200 and r.mimetype == "text/vnd.graphviz"
    assert r.get_data(as_text=True) == SLR1(parse_grammar(EX1)).dot() + "\n"


def tree_symbols(tree):
    out, stack = [], [tree]
    while stack:
        n = stack.pop()
        out.append(n["symbol"])
        if n["prod"] is not None and not n["children"]:
            out.append("ε")
        stack.extend(reversed(n["children"]))
    return out


@pytest.mark.parametrize("grammar,word,parser", [
    (EX1, "(i+i)*i", "auto"), (EX2, "adbc", "ll1"), (EX2, "aadbbcc", "slr1"), (EPS, "aabb", "auto"), (EPS, "e", "auto"),
    (KOZEN_212, "[[]][]", "auto"),
])
def test_parse_tree_svg_and_dot(c, grammar, word, parser):
    body = {"grammar": grammar, "graph": "tree", "input": word, "parser": parser}
    root = svg_root(c.post("/grammar/graph", json=body))
    tree = c.post("/grammar/parse", json={"grammar": grammar, "inputs": [word], "parser": parser}).get_json()
    expected = tree_symbols(tree["results"][0]["tree"])
    assert sorted(texts(root)) == sorted(expected)                               # one label per node (+ ε leaves)
    dot = c.post("/grammar/graph", json={**body, "format": "dot"})
    assert dot.mimetype == "text/vnd.graphviz"
    d = dot.get_data(as_text=True)
    assert d.startswith("digraph tree {") and d.count("[label=") == len(expected)


def test_svg_escapes_markup_characters(c):
    g = "1\nS -> <S>& a"
    root = svg_root(c.post("/grammar/graph", json={"grammar": g}))
    assert "S -> <.S>&" in texts(root)
    root = svg_root(c.post("/grammar/graph", json={"grammar": g, "graph": "tree", "input": "<a>&"}))
    assert sorted(texts(root)) == sorted(["S", "<", "S", "a", ">", "&"])


def test_deep_parse_tree_does_not_hit_the_recursion_limit(c):
    word = "a" * 999 + "b" * 999                                                # depth 1001, input limit 2000
    root = svg_root(c.post("/grammar/graph", json={"grammar": EPS, "graph": "tree", "input": word}))
    assert len(texts(root)) == 3 * 999 + 3                                       # S, a, b per level + S, A, ε


@pytest.mark.parametrize("body", [
    {"grammar": EX1, "format": "png"}, {"grammar": EX1, "graph": "dfa"}, {"grammar": EX1, "graph": "tree"},
    {"grammar": EX1, "graph": "tree", "input": 5}, {"grammar": EX1, "graph": "tree", "input": "ii"},
    {"grammar": NEITHER, "graph": "tree", "input": "a"}, {"grammar": EX1, "graph": "tree", "input": "i", "parser": "ll1"},
    {"grammar": HUGE}, {"grammar": HUGE, "format": "dot"}, {"grammar": 5},
])
def test_graph_rejects_bad_requests(c, body):
    r = c.post("/grammar/graph", json=body)
    assert r.status_code == 400 and "error" in r.get_json()


# ------------------------------------------------------------------ the server as a whole
def test_huge_lr0_collection_is_a_400_or_a_partial_answer_never_a_500(c):
    for url in ("/grammar/sets", "/grammar/ll1", "/grammar/slr1", "/grammar/analyze"):
        r = c.post(url, json={"grammar": HUGE})
        assert r.status_code == 200, url
    assert c.post("/grammar/slr1", json={"grammar": HUGE}).get_json()["tooBig"] is True
    r = c.post("/grammar/parse", json={"grammar": HUGE, "inputs": ["a" * 450]}).get_json()
    assert r["case"] == 2 and r["results"][0]["accepted"] is True               # LL(1) still works
    assert not SLR1(parse_grammar(HUGE)).is_slr1 and LL1(parse_grammar(HUGE)).is_ll1


def test_new_endpoints_are_listed(c):
    paths = {row["path"] for row in c.get("/api").get_json()}
    assert {"/grammar/report", "/grammar/export", "/grammar/graph"} <= paths
    hub = c.get("/").get_data(as_text=True)
    for e in ("POST /grammar/report", "POST /grammar/export", "POST /grammar/graph"):
        assert e in hub
