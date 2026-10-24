# OpenAPI 3 description of the whole server, written as data. /docs renders it with Swagger UI (bundled locally).
# A test checks that every route of the Flask URL map appears here, so the documentation cannot drift.

J = "application/json"
EX_GRAMMAR = "3\nS -> AB\nA -> aA d\nB -> bBc e"
EX_NFA = {"states": [0, 1, 2], "alphabet": ["a", "b"], "initial": 0, "accepting": [2],
          "transitions": [{"from": 0, "symbol": "a", "to": 1}, {"from": 1, "symbol": None, "to": 2}, {"from": 2, "symbol": "b", "to": 2}]}


def _body(example, description="", schema=None):
    return {"required": True, "description": description,
            "content": {J: {"schema": schema or {"type": "object"}, "example": example}}}


def _ok(description="OK"):
    return {"200": {"description": description, "content": {J: {"schema": {"type": "object"}}}},
            "400": {"description": "Invalid request. The body is always {\"error\": \"...\"} (plus \"line\" for grammar/DFA text errors)."}}


def _op(tag, summary, description="", body=None, params=None, responses=None):
    op = {"tags": [tag], "summary": summary, "description": description, "responses": responses or _ok()}
    if body is not None:
        op["requestBody"] = body
    if params:
        op["parameters"] = params
    return op


def _page(tag, summary):
    return _op(tag, summary, responses={"200": {"description": "HTML page", "content": {"text/html": {"schema": {"type": "string"}}}}})


def _q(name, desc, schema, required=False, example=None):
    p = {"name": name, "in": "query", "description": desc, "required": required, "schema": schema}
    if example is not None:
        p["example"] = example
    return p


def build_spec():
    paths = {
        "/": {"get": _page("Server", "Home page with the whole pipeline")},
        "/health": {"get": _op("Server", "Liveness check", "Returns {\"status\": \"ok\"}. The coloured dot of every page calls it.")},
        "/api": {"get": _op("Server", "Index of every route", "Built from the live Flask URL map.")},
        "/docs": {"get": _page("Server", "This documentation (Swagger UI)")},
        "/openapi.json": {"get": _op("Server", "OpenAPI description of the server")},
        # --- Assignment 1
        "/convert": {"post": _op("Assignment 1: NFA to DFA", "Subset construction",
                                 "Epsilon transitions are written with \"symbol\": null.", _body(EX_NFA))},
        "/simulate": {"post": _op("Assignment 1: NFA to DFA", "Run a string on a DFA", "",
                                  _body({"initial": "0", "accepting": ["1"], "input": "ab",
                                         "transitions": [{"from": "0", "symbol": "a", "to": "1"}, {"from": "1", "symbol": "b", "to": "1"}]}))},
        # --- Assignment 2
        "/minimize": {"post": _op("Assignment 2: minimization", "Equivalent states and minimal DFA",
                                  "Accepts the course text format (text/plain), JSON with the field names of /convert, or the output of /convert unchanged.",
                                  {"required": True, "content": {"text/plain": {"schema": {"type": "string"}, "example": "1\n6\na b\n1 4 5\n0 1 2\n1 3 4\n2 4 3\n3 5 5\n4 5 5\n5 5 5\n"},
                                                                  J: {"schema": {"type": "object"}}}},
                                  [_q("format", "json (default) or text", {"type": "string", "enum": ["json", "text"]}),
                                   _q("steps", "Include the step-by-step trace", {"type": "boolean"})])},
        "/minimize/compare": {"post": _op("Assignment 2: minimization", "Do two DFAs accept the same language?",
                                          "Takes exactly two DFAs (text with c = 2, or {\"cases\": [dfa1, dfa2]}).",
                                          {"required": True, "content": {J: {"schema": {"type": "object"}, "example": {"cases": []}}, "text/plain": {"schema": {"type": "string"}}}})},
        "/minimize/example": {"get": _op("Assignment 2: minimization", "The example of the assignment, solved")},
        "/minimize/ui": {"get": _page("Assignment 2: minimization", "Interactive page for assignments 1 and 2")},
        # --- Grammars
        "/grammar/examples": {"get": _op("Final project: grammars", "Example grammars")},
        "/grammar/sets": {"post": _op("Final project: grammars", "FIRST and FOLLOW (Item 1)",
                                      "Section 4.4.2. Send JSON {\"grammar\": \"...\"} or the grammar as text/plain.", _body({"grammar": EX_GRAMMAR}))},
        "/grammar/ll1": {"post": _op("Final project: grammars", "LL(1) test and predictive table",
                                     "Condition of Section 4.4.3, table by Algorithm 4.31.", _body({"grammar": EX_GRAMMAR}))},
        "/grammar/slr1": {"post": _op("Final project: grammars", "LR(0) automaton and SLR(1) tables",
                                      "Sections 4.6.2 to 4.6.4. Conflicts are listed, never hidden.", _body({"grammar": EX_GRAMMAR}))},
        "/grammar/analyze": {"post": _op("Final project: grammars", "Everything at once plus the decision of Section 2.2.2",
                                         "case 1: both, 2: LL(1) only, 3: SLR(1) only, 4: neither.", _body({"grammar": EX_GRAMMAR}))},
        "/grammar/parse": {"post": _op("Final project: grammars", "Parse strings (yes/no, tree, step-by-step trace)",
                                       "parser: ll1 (Algorithm 4.34), slr1 (Section 4.6.3) or auto. \"recover\": true uses panic-mode recovery "
                                       "(Section 4.4.5) and reports every error found. The empty string is written e.",
                                       _body({"grammar": EX_GRAMMAR, "inputs": ["d", "adbc", "a"], "parser": "ll1", "trace": True, "recover": False}))},
        "/grammar/to-nfa": {"post": _op("Final project: grammars", "Right-linear grammar to NFA",
                                        "The result has the exact format of POST /convert.", _body({"grammar": "2\nS -> aS bS aA\nA -> b"}))},
        "/grammar/compare": {"post": _op("Final project: grammars", "Do two regular grammars generate the same language?",
                                         "grammar -> NFA -> DFA over the union of the alphabets -> /minimize/compare.",
                                         _body({"grammars": ["2\nS -> aS bS aA\nA -> b", "2\nS -> aS bS aB\nB -> b"]}))},
        "/grammar/ui": {"get": _page("Final project: grammars", "Interactive page")},
        # --- SDD
        "/sdd/presets": {"get": _op("Final project: SDD", "The ready-made SDDs")},
        "/sdd/presets/{pid}": {"get": _op("Final project: SDD", "One SDD as editable data",
                                          params=[{"name": "pid", "in": "path", "required": True, "schema": {"type": "string", "enum": ["luhn", "weighted"]}}],
                                          responses={"200": {"description": "SDD definition"}, "404": {"description": "Unknown preset"}})},
        "/sdd/describe": {"post": _op("Final project: SDD", "Validate a definition and describe it",
                                      "Attribute table, rules, S/L-attributed classification (Sections 5.2.3, 5.2.4).", _body({"preset": "luhn"}))},
        "/sdd/evaluate": {"post": _op("Final project: SDD", "Evaluate strings (Item 3)",
                                      "Parse tree, dependency graph, topological order and the main attribute. \"circular\": true applies the "
                                      "circular variant (Step 6). A custom SDD goes in \"definition\".",
                                      _body({"preset": "luhn", "inputs": ["79927398713", "12a"], "circular": False}))},
        "/sdd/ui": {"get": _page("Final project: SDD", "Interactive page")},
        # --- Practice
        "/practice/kinds": {"get": _op("Practice", "Exercise types")},
        "/practice/new": {"get": _op("Practice", "A reproducible exercise", "The same seed always gives the same grammar.",
                                     params=[_q("kind", "Exercise type", {"type": "string", "enum": ["sets", "ll1_table", "derivation", "lr0"]}, True, "sets"),
                                             _q("seed", "Integer seed (random if omitted)", {"type": "integer"}, False, 42),
                                             _q("difficulty", "1 to 3", {"type": "integer", "enum": [1, 2, 3]}, False, 2)])},
        "/practice/check": {"post": _op("Practice", "Correct an answer", "Returns item-by-item feedback and the solution.",
                                        _body({"kind": "sets", "seed": 42, "difficulty": 2, "answer": {"first": {"S": "a b"}, "follow": {"S": "$"}}}))},
        "/practice/ui": {"get": _page("Practice", "Interactive page")},
        # --- Export
        "/export/latex/grammar": {"post": _op("LaTeX export", "Report tables of a grammar as a .tex file",
                                              "FIRST/FOLLOW, LL(1) table, LR(0) items, ACTION/GOTO and parsing traces. Add ?download=1 for the file itself.",
                                              _body({"grammar": EX_GRAMMAR, "inputs": ["adbc"]}), [_q("download", "Return the .tex as an attachment", {"type": "boolean"})])},
        "/export/latex/sdd": {"post": _op("LaTeX export", "Report tables of an SDD as a .tex file",
                                          "Attribute table, rules, classification and, with \"input\", the annotated tree and evaluation order.",
                                          _body({"preset": "luhn", "input": "79927398713"}), [_q("download", "Return the .tex as an attachment", {"type": "boolean"})])},
        # --- Sessions
        "/sessions": {
            "get": _op("Saved sessions", "List saved sessions", params=[_q("kind", "grammar or sdd", {"type": "string", "enum": ["grammar", "sdd"]})]),
            "post": _op("Saved sessions", "Save (or replace) a session by kind and name", "Stored in a local SQLite file.",
                        _body({"kind": "grammar", "name": "Example 2", "payload": {"grammar": EX_GRAMMAR, "inputs": ["adbc"]}}),
                        responses={"201": {"description": "Saved"}, "400": {"description": "Invalid request"}})},
        "/sessions/{sid}": {
            "get": _op("Saved sessions", "One session with its payload", params=[{"name": "sid", "in": "path", "required": True, "schema": {"type": "integer"}}],
                       responses={"200": {"description": "Session"}, "404": {"description": "Not found"}}),
            "delete": _op("Saved sessions", "Delete a session", params=[{"name": "sid", "in": "path", "required": True, "schema": {"type": "integer"}}],
                          responses={"200": {"description": "Deleted"}, "404": {"description": "Not found"}})},
    }
    return {"openapi": "3.0.3",
            "info": {"title": "Formal Languages Server", "version": "1.0.0",
                     "description": "NFA to DFA, DFA minimization, grammars (FIRST/FOLLOW, LL(1), SLR(1)), syntax-directed definitions, "
                                    "practice mode, LaTeX export and saved sessions, on one Flask server."},
            "servers": [{"url": "/"}], "paths": paths}
