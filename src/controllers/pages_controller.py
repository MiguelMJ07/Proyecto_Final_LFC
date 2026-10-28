# CONTROLLER layer for the landing page and server diagnostics.
#   GET /        hub page that links every stage of the course pipeline
#   GET /health  liveness check (used by the page's status light and by tests)
#   GET /api     machine-readable index of every endpoint (built from the live URL map)
from flask import Blueprint, current_app, jsonify, render_template

pages_bp = Blueprint("pages", __name__)

STAGES = [
    {"no": 1, "title": "NFA → DFA", "kicker": "Assignment 1", "href": "/minimize/ui#nfa",
     "text": "Subset construction and DFA simulation.", "endpoints": ["POST /convert", "POST /simulate"]},
    {"no": 2, "title": "DFA minimization", "kicker": "Assignment 2", "href": "/minimize/ui",
     "text": "Table-filling algorithm, equivalent states, language equivalence of two DFAs.",
     "endpoints": ["POST /minimize", "POST /minimize/compare"]},
    {"no": 3, "title": "Grammars and parsers", "kicker": "Final project · Items 1-2", "href": "/grammar/ui",
     "text": "FIRST/FOLLOW, LL(1) table, LR(0) automaton, SLR(1) tables, step-by-step parsing.",
     "endpoints": ["POST /grammar/analyze", "POST /grammar/parse", "POST /grammar/to-nfa", "POST /grammar/report",
                   "POST /grammar/export", "POST /grammar/graph"]},
    {"no": 4, "title": "Syntax-directed definitions", "kicker": "Final project · Item 3", "href": "/sdd/ui",
     "text": "Annotated parse tree, dependency graph and evaluation order; detects circular SDDs.",
     "endpoints": ["POST /sdd/evaluate", "POST /sdd/describe"]},
]


@pages_bp.route("/", methods=["GET"])
def hub():
    return render_template("hub.html", stages=STAGES)


@pages_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "formal-languages-web-server"})


@pages_bp.route("/api", methods=["GET"])
def api_index():
    rows = []
    for rule in sorted(current_app.url_map.iter_rules(), key=lambda r: r.rule):
        if rule.endpoint == "static":
            continue
        methods = sorted(m for m in rule.methods if m not in ("HEAD", "OPTIONS"))
        rows.append({"path": rule.rule, "methods": methods, "endpoint": rule.endpoint})
    return jsonify(rows)
