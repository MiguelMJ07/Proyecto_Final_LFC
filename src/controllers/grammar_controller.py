# CONTROLLER layer for Items 1 and 2 (First/Follow, LL(1), SLR(1)).
# Validates the request shape and returns HTTP responses; the algorithms live in functions/cfg_*.py.
#
#   POST /grammar/sets      FIRST / FOLLOW (Item 1) with the fixed-point trace
#   POST /grammar/ll1       LL(1) test (Section 4.4.3), table (Alg. 4.31), conflicts
#   POST /grammar/slr1      LR(0) automaton, ACTION/GOTO, conflicts
#   POST /grammar/analyze   everything above plus the decision of Section 2.2.2
#   POST /grammar/parse     strings -> yes/no (+ parse tree, + step-by-step trace)
#   POST /grammar/to-nfa    right-linear grammar -> NFA (input of /convert)
#   POST /grammar/report    plain text: exactly what cli/main.py prints (extra: other output formats)
#   POST /grammar/export    FIRST/FOLLOW, LL(1) or SLR(1) table as CSV or LaTeX
#   POST /grammar/graph     LR(0) automaton or parse tree as Graphviz DOT or SVG
#   GET  /grammar/examples  grammars of the assignment and a regular one
#   GET  /grammar/ui        interactive page
from flask import Blueprint, Response, jsonify, render_template, request

from controllers.http_utils import BadRequest, grammar_text, json_body
from functions.cfg_grammar import GrammarError
from gateways.grammar_gateway import GrammarGateway

grammar_bp = Blueprint("grammar", __name__)
gateway = GrammarGateway()

EXAMPLES = [
    {"id": "ex1", "name": "Example 1 (expressions, SLR(1) only)", "grammar": "3\nS -> S+T T\nT -> T*F F\nF -> (S) i",
     "inputs": ["i+i", "(i)", "(i+i)*i)"]},
    {"id": "ex2", "name": "Example 2 (LL(1) and SLR(1))", "grammar": "3\nS -> AB\nA -> aA d\nB -> bBc e",
     "inputs": ["d", "adbc", "a"]},
    {"id": "ex3", "name": "Example 3 (neither)", "grammar": "1\nS -> SS a", "inputs": ["a"]},
    {"id": "eps", "name": "Epsilon productions (LL(1))", "grammar": "2\nS -> aSb A\nA -> e", "inputs": ["aabb", "e", "aab"]},
    {"id": "kozen212", "name": "Kozen, Lecture 21, grammar (21.2): Greibach form for balanced brackets",
     "grammar": "2\nS -> [B [SB [BS [SBS\nB -> ]", "inputs": ["[]", "[[]]", "[][]", "[[]", "]["]},
    {"id": "kozen211", "name": "Kozen, Lecture 21, grammar (21.1): Chomsky form for balanced brackets (neither)",
     "grammar": "4\nS -> AB AC SS\nC -> SB\nA -> [\nB -> ]", "inputs": ["[]"]},
    {"id": "regular", "name": "Regular grammar (strings over {a,b} ending in ab)",
     "grammar": "2\nS -> aS bS aA\nA -> b", "inputs": ["ab", "aab", "abb", "bab"]},
]


MIMETYPES = {"text": "text/plain", "csv": "text/csv", "latex": "text/x-tex", "dot": "text/vnd.graphviz",
             "svg": "image/svg+xml"}


def _flag(data, name, default):
    value = data.get(name, default)
    if not isinstance(value, bool):
        raise BadRequest(f"Field '{name}' must be true or false.")
    return value


def _query_flag(name, default):
    value = request.args.get(name)
    if value is None:
        return default
    if value.lower() in ("1", "true", "yes"):
        return True
    if value.lower() in ("0", "false", "no"):
        return False
    raise BadRequest(f"Query parameter '{name}' must be true or false.")


def _inputs(data):
    inputs = data.get("inputs", data.get("input", []))
    return [inputs] if isinstance(inputs, str) else inputs


def _file(out):
    """A file response (inline, so curl prints it and the browser shows it; the name is used when it is saved)."""
    return Response(out["content"], mimetype=MIMETYPES[out["format"]],
                    headers={"Content-Disposition": f'inline; filename="{out["filename"]}"'})


@grammar_bp.errorhandler(GrammarError)
def _grammar_error(e):
    body = {"error": str(e)}
    if e.line:
        body["line"] = e.line
    return jsonify(body), 400


@grammar_bp.errorhandler(ValueError)
def _value_error(e):
    return jsonify({"error": str(e)}), 400


@grammar_bp.route("/grammar/examples", methods=["GET"])
def examples():
    return jsonify(EXAMPLES)


@grammar_bp.route("/grammar/sets", methods=["POST"])
def sets():
    return jsonify(gateway.sets(grammar_text()))


@grammar_bp.route("/grammar/ll1", methods=["POST"])
def ll1():
    return jsonify(gateway.ll1(grammar_text()))


@grammar_bp.route("/grammar/slr1", methods=["POST"])
def slr1():
    return jsonify(gateway.slr1(grammar_text()))


@grammar_bp.route("/grammar/analyze", methods=["POST"])
def analyze():
    return jsonify(gateway.analyze(grammar_text()))


@grammar_bp.route("/grammar/to-nfa", methods=["POST"])
def to_nfa():
    return jsonify(gateway.to_nfa(grammar_text()))


@grammar_bp.route("/grammar/parse", methods=["POST"])
def parse():
    data = json_body(["grammar"])
    trace = _flag(data, "trace", False)
    return jsonify(gateway.parse(data["grammar"], _inputs(data), data.get("parser", "auto"), trace))


@grammar_bp.route("/grammar/report", methods=["POST"])
def report():
    """JSON {"grammar", "inputs", "parser", "sets", "tables", "trace"}, or as text/plain exactly the stdin of
    cli/main.py (flags as query parameters ?sets=&tables=&trace=). The answer is the program's output."""
    if request.is_json:
        data = json_body(["grammar"])
        flags = {name: _flag(data, name, name == "sets") for name in ("sets", "tables", "trace")}
        text = gateway.report(data["grammar"], _inputs(data), data.get("parser", "auto"), **flags)
    else:
        flags = {name: _query_flag(name, name == "sets") for name in ("sets", "tables", "trace")}
        text = gateway.report_text(request.get_data(as_text=True), **flags)
    return _file({"content": text, "format": "text", "filename": "report.txt"})


@grammar_bp.route("/grammar/export", methods=["POST"])
def export():
    data = json_body(["grammar"])
    return _file(gateway.export(data["grammar"], data.get("table", "sets"), data.get("format", "csv"),
                                _flag(data, "standalone", False)))


@grammar_bp.route("/grammar/graph", methods=["POST"])
def graph():
    data = json_body(["grammar"])
    return _file(gateway.graph(data["grammar"], data.get("graph", "lr0"), data.get("format", "svg"),
                               data.get("input"), data.get("parser", "auto")))


@grammar_bp.route("/grammar/ui", methods=["GET"])
def ui():
    return render_template("grammar.html", examples=EXAMPLES)
