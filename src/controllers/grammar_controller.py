# CONTROLLER layer for Items 1 and 2 (First/Follow, LL(1), SLR(1)).
# Validates the request shape and returns HTTP responses; the algorithms live in functions/cfg_*.py.
#
#   POST /grammar/sets      FIRST / FOLLOW (Item 1) with the fixed-point trace
#   POST /grammar/ll1       LL(1) test (Section 4.4.3), table (Alg. 4.31), conflicts
#   POST /grammar/slr1      LR(0) automaton, ACTION/GOTO, conflicts
#   POST /grammar/analyze   everything above plus the decision of Section 2.2.2
#   POST /grammar/parse     strings -> yes/no (+ parse tree, + step-by-step trace)
#   POST /grammar/to-nfa    right-linear grammar -> NFA (input of /convert)
#   GET  /grammar/examples  grammars of the assignment and a regular one
#   GET  /grammar/ui        interactive page
from flask import Blueprint, jsonify, render_template

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
    inputs = data.get("inputs", data.get("input", []))
    if isinstance(inputs, str):
        inputs = [inputs]
    parser = data.get("parser", "auto")
    trace = data.get("trace", False)
    if not isinstance(trace, bool):
        raise BadRequest("Field 'trace' must be true or false.")
    return jsonify(gateway.parse(data["grammar"], inputs, parser, trace))


@grammar_bp.route("/grammar/ui", methods=["GET"])
def ui():
    return render_template("grammar.html", examples=EXAMPLES)
