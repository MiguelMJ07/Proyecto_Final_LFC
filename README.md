# Formal Languages Web Server: automata, grammars, parsers and SDDs

One Flask server for the whole course. It extends the two earlier assignments (NFA → DFA, DFA minimization)
with the final project (FIRST/FOLLOW, LL(1), SLR(1) and syntax-directed definitions). Every stage is an
endpoint (or a few) and has its own page.

| Stage | Endpoints | Page |
|---|---|---|
| Assignment 1: NFA → DFA, DFA simulation | `POST /convert`, `POST /simulate` | `/minimize/ui#nfa` |
| Assignment 2: DFA minimization | `POST /minimize`, `POST /minimize/compare`, `GET /minimize/example` | `/minimize/ui` |
| Final project, Items 1-2: FIRST/FOLLOW, LL(1), SLR(1) | `POST /grammar/sets`, `/grammar/ll1`, `/grammar/slr1`, `/grammar/analyze`, `/grammar/parse`, `/grammar/to-nfa`, `GET /grammar/examples` | `/grammar/ui` |
| Final project, Item 3: SDD | `GET /sdd/presets`, `GET /sdd/presets/<id>`, `POST /sdd/describe`, `POST /sdd/evaluate` | `/sdd/ui` |
| Server | `GET /` (hub), `GET /health`, `GET /api` (index built from the live URL map) | `/` |

## Group members

- <Full name 1> (<class number>)
- <Full name 2>
- <Full name 3 (optional)>

## Environment

- OS: <fill in, e.g. Windows 11 / Ubuntu 24.04>
- Python: 3.10 or newer (developed and tested with Python 3.12)
- Flask 3.0.3 or newer, pytest 8.3.3 or newer (`requirements.txt`). No parser generators or parsing libraries are used.
- Browser pages use `@viz-js/viz` 3.11.0 (Graphviz compiled to WebAssembly, MIT), bundled in `src/static/vendor/`,
  so the pages work without internet access.

## Build and run

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # macOS / Linux
pip install -r requirements.txt
python src/app.py                 # http://127.0.0.1:5000
```

Optional environment variables: `PORT` (default 5000), `HOST` (default 127.0.0.1), `FLASK_DEBUG=0` to turn off the reloader.
The coloured dot in the left rail of every page shows whether the browser can reach the server (`GET /health`).

Tests: `pytest tests/` (950 tests: the two earlier assignments plus the new stages; includes a property test that
checks both parsers against a brute-force enumeration of the language of random grammars).

### Items 1 and 2 from the command line (protocol of Section 2.2 of the assignment)

```bash
python cli/main.py < examples/ex1.txt
python cli/main.py --sets < examples/ex2.txt      # prints FIRST/FOLLOW first, then continues
python cli/main.py --tables --trace < examples/ex2.txt   # extra: tables and every parsing step
```

The input is the grammar (first line `n`, then `n` lines), then, after the program's message, one string per line
until an empty line (`e` is the empty string). When the grammar is both LL(1) and SLR(1) the program asks for `T`, `B` or `Q`.

### Item 3 from the command line (Step 5 of the assignment)

```bash
python cli/sdd_cli.py < examples/sdd_strings.txt              # Luhn SDD (default)
python cli/sdd_cli.py --preset weighted < examples/sdd_strings.txt
python cli/sdd_cli.py --circular < examples/sdd_circular.txt  # Step 6: temporarily circular SDD
python cli/sdd_cli.py --graph                                 # also prints the dependency edges
```

For each string it prints `no`, or the annotated parse tree (one node per line, indented by depth), the evaluation order
and the value of the main attribute. A circular SDD stops with the cycle that was found.

### Item 3 on the web (`/sdd/ui`)

Pick an SDD, edit its JSON if you want (it is the data the evaluator reads), enter strings and press **Evaluate**. You get the
annotated tree, the dependency graph evaluated step by step (attributes turn green in topological order) and the evaluation
order table. **Make the SDD circular** applies the preset's `circularVariant` (Step 6). From the API:

```bash
curl -s localhost:5000/sdd/evaluate -H 'Content-Type: application/json' \
     -d '{"preset": "luhn", "inputs": ["79927398713", "12a"]}'
curl -s localhost:5000/sdd/evaluate -H 'Content-Type: application/json' \
     -d '{"preset": "luhn", "circular": true, "input": "18"}'
```

## Project structure

```
src/
├── app.py                          # creates the server and registers every blueprint
├── controllers/                    # HTTP only: validation of the request and responses
│   ├── automata_controller.py      #   A1: /convert, /simulate
│   ├── minimization_controller.py  #   A2: /minimize...
│   ├── grammar_controller.py       #   Items 1-2: /grammar/*
│   ├── sdd_controller.py           #   Item 3: /sdd/*
│   ├── pages_controller.py         #   /, /health, /api
│   └── http_utils.py               #   strict JSON body reading, uniform JSON errors
├── gateways/                       # orchestration; every internal error becomes a ValueError (HTTP 400)
│   ├── automata_gateway.py, minimization_gateway.py
│   ├── grammar_gateway.py          #   decision of Section 2.2.2, parse with traces
│   └── sdd_gateway.py
├── functions/                      # pure algorithms, no Flask
│   ├── subset_construction.py, simulate.py, dfa*.py, minimization*.py     (earlier assignments)
│   ├── cfg_grammar.py              #   grammar reading, FIRST, FOLLOW, left-recursion diagnostic
│   ├── cfg_ll1.py                  #   LL(1) test, predictive table, table-driven parser
│   ├── cfg_slr1.py                 #   LR(0) items, CLOSURE, GOTO, ACTION/GOTO, LR parser
│   ├── cfg_tree.py                 #   parse tree node
│   ├── cfg_sdd.py                  #   SDD as data, validation, classification, dependency graph, evaluation
│   ├── cfg_sdd_presets.py          #   the SDDs, stored as data
│   ├── safe_expr.py                #   safe expression language for semantic rules (no eval)
│   └── cfg_regular.py              #   right-linear grammar -> NFA (bridge to A1/A2)
├── templates/                      # hub, grammar, sdd, minimization pages + shared rail
└── static/                         # app.css, common.js, vendor/viz-standalone.js
cli/main.py, cli/sdd_cli.py         # stdin/stdout programs required by the assignment
examples/                           # sample inputs
tests/                              # pytest
```

## How the algorithms follow the book

Aho, Lam, Sethi, Ullman, *Compilers: Principles, Techniques, and Tools*, 2nd ed.

| Part | Book | Where |
|---|---|---|
| FIRST(X), FIRST of a string, FOLLOW(A) | Section 4.4.2 (rules 1-3 of each) | `cfg_grammar.py` |
| LL(1) condition (three conditions on each pair A → α \| β) | Section 4.4.3 | `check_ll1_conditions` in `cfg_ll1.py` |
| Predictive parsing table | Algorithm 4.31 | `LL1.__init__` |
| Table-driven predictive parser | Section 4.4.4, Algorithm 4.34 and Fig. 4.20 | `LL1.parse` |
| LR(0) items, CLOSURE, GOTO, augmented grammar | Section 4.6.2 | `cfg_slr1.py` |
| LR parsing algorithm | Section 4.6.3 | `SLR1.parse` |
| ACTION/GOTO from the collection and FOLLOW; conflicts | Sections 4.6.4 and 4.5.4 | `SLR1._build_tables` |
| SDD, synthesized/inherited attributes, annotated tree | Sections 5.1.1 and 5.1.2 | `cfg_sdd.py` |
| Dependency graph and topological evaluation order | Sections 5.2.1 and 5.2.2 | `build_graph`, `topological_order` |
| S-attributed / L-attributed classification | Sections 5.2.3 and 5.2.4 | `SDD.classify` |

Checked against the text: Section 4.4 (the attached `Cap4.pdf`, pages 192-232) for FIRST/FOLLOW, the LL(1) condition,
Algorithms 4.31 and 4.34. Sections 4.5, 4.6 and 5.1-5.2 are not in that file; their numbering comes from the assignment, so
**check the SLR(1) and SDD parts and their algorithm numbers against your copy of the book before citing them in the report.**

Connection with Kozen, *Automata and Computability* (the lectures provided): the grammars (21.1) and (21.2) of Lecture 21 are
included as examples (`/grammar/ui`), and the stack discipline of the predictive parser is the deterministic form of the
one-state NPDA that accepts by empty stack built from a grammar in Lecture 24.

### Design decisions

- The LL(1) decision uses the literal test of Section 4.4.3. The table is built anyway, and the server also reports table
  conflicts. The input grammar is never transformed (no left-recursion removal before the check).
- SLR(1) never hides a conflict: every ACTION cell keeps all its candidate actions and conflicts are listed with state, symbol and type.
- The SDD is data: a grammar, an attribute table, and for each production a list of rules `X.attr = expression`. A rule's
  dependencies are derived from the references it contains. The evaluator never assumes a traversal order: it builds the
  dependency graph of the actual parse tree, orders it with Kahn's algorithm and evaluates. A cycle is reported with the
  attributes that form it. Every loop over the tree is iterative, so deep inputs do not hit Python's recursion limit.
- Rules use a restricted expression language (arithmetic, comparisons, `and/or/not`, `a if c else b`, `max min abs int str len`)
  that is parsed and interpreted, never passed to `eval`, so an SDD can be edited from the browser safely.
- Limits that keep the server responsive: 20,000 characters per grammar, 400 productions, 400 LR(0) states, 200 strings per
  request, 2,000 symbols per string (400 for SDD evaluation), 2 MB per body.

## The SDDs

Both are ours (not from the book or the assignment) and work on strings of decimal digits with the grammar
`S → L`, `L → DM`, `M → L | e`, `D → 0 | 1 | … | 9`.

**Luhn checksum** (main attribute `S.valid`). Counting from the rightmost digit (k = 0), digits with odd k are doubled
(minus 9 if above 9); the string is valid when the total is a multiple of 10. `D.k` is inherited from the right-hand
sibling `M.cnt`, so it is **neither S-attributed nor L-attributed** and the general method is required.

| Production | Semantic rules |
|---|---|
| S → L | S.sum = L.sum; S.valid = (L.sum mod 10 = 0) |
| L → D M | D.k = M.cnt; L.cnt = M.cnt + 1; L.sum = D.s + M.sum |
| M → L | M.cnt = L.cnt; M.sum = L.sum |
| M → ε | M.cnt = 0; M.sum = 0 |
| D → d | D.s = (2·d − 9 if 2·d > 9 else 2·d) if D.k is odd, else d |

**Position-weighted checksum** (left to right). The i-th digit is multiplied by i; valid when the total is a multiple of 11.
The position travels down from the left (`pos` inherited), so it is **L-attributed** (and not S-attributed).

Circular variants for Step 6: Luhn `D.k = M.cnt + D.s` (D.k and D.s depend on each other), weighted `D.pos = L.pos + D.s`.

## Endpoint details

`POST /grammar/analyze` (JSON `{"grammar": "3\nS -> S+T T\nT -> T*F F\nF -> (S) i"}`, or the same text as `text/plain`) returns the
decision of Section 2.2.2 (`case` 1-4 and `message`), the productions, FIRST/FOLLOW with the fixed-point trace, the LL(1) violations
and table, and the LR(0) automaton with the SLR(1) tables and conflicts. `POST /grammar/parse` takes `{"grammar", "inputs": [...],
"parser": "ll1" | "slr1" | "auto", "trace": true}` and answers `yes`/`no` for each string, with the parse tree and every step.
`POST /grammar/to-nfa` turns a right-linear grammar into an NFA in the exact format of `/convert`, so a regular grammar can go
through `/convert` and `/minimize`. Errors are always JSON `{"error": "...", "line": n}` with HTTP 400 (404/405/413 for routing and size).

## Generative AI tools

<State here which AI tools you used and for what purpose, or that you did not use any. The assignment requires this section.>
