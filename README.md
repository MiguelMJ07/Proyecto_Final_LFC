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
| Extra: other output formats | `POST /grammar/report` (text), `POST /grammar/export` (CSV, LaTeX), `POST /grammar/graph` (DOT, SVG) | files |
| Server | `GET /` (hub), `GET /health`, `GET /api` (index built from the live URL map) | `/` |

## Group members

- <Full name 1> (<class number>)
- <Full name 2>
- <Full name 3 (optional)>

## Environment

- OS: <fill in, e.g. Windows 11 / Ubuntu 24.04>
- Python: 3.9 or newer (developed with Python 3.12; the tests also pass with Python 3.9.6 on macOS)
- Flask 3.0.3 and pytest 8.3.3 (`requirements.txt`); gunicorn 23.0.0 only for the deployment (not on Windows).
  No parser generators or parsing libraries are used: only the Python standard library.
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

On macOS and Linux the command may be `python3` instead of `python`. In Windows PowerShell, `<` cannot redirect a
file into a program: write `Get-Content examples/ex1.txt | python cli/main.py` instead of `python cli/main.py < examples/ex1.txt`.

Optional environment variables: `PORT` (default 5000), `HOST` (default 127.0.0.1) and `FLASK_DEBUG` (`0` turns off the
debugger and the reloader). The coloured dot in the left rail of every page shows whether the browser can reach the
server (`GET /health`).

### Opening the server from other devices and deploying it

- **Same network (no internet needed):** `HOST=0.0.0.0 python src/app.py` (PowerShell: `$env:HOST="0.0.0.0"; python src/app.py`),
  then open `http://<IP of the computer>:5000` on the other device. With `HOST=0.0.0.0` the Flask debugger is off by
  default, because it would let anyone on the network run code on the computer.
- **Internet:** `render.yaml` deploys the server on Render with gunicorn (production WSGI server, 2 worker processes)
  behind HTTPS, with `/health` as health check; every push deploys again. Public address: <fill in after deploying>.
  Steps, the type of connection and its benefits are explained (in Spanish) in [DESPLIEGUE.md](DESPLIEGUE.md).

Tests: `pytest tests/` (1052 tests: the two earlier assignments plus the new stages; includes a property test that
checks both parsers against a brute-force enumeration of the language of random grammars, and a test that runs
`cli/main.py` and checks that `POST /grammar/report` gives exactly the same output).

### Items 1 and 2 from the command line (protocol of Section 2.2 of the assignment)

```bash
python cli/main.py < examples/ex1.txt
python cli/main.py --sets < examples/ex2.txt      # prints FIRST/FOLLOW first, then continues
python cli/main.py --tables --trace < examples/ex2.txt   # extra: tables and every parsing step
```

The input is the grammar (first line `n`, then `n` lines), then, after the program's message, one string per line
until an empty line (`e` is the empty string). When the grammar is both LL(1) and SLR(1) the program asks for `T`, `B` or `Q`.
The protocol is written once (`src/functions/cfg_protocol.py`) and the server runs the same code, so the same file sent
to `POST /grammar/report` gives exactly what the program prints (see [Other output formats](#other-output-formats-extra)).

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
│   ├── cfg_regular.py              #   right-linear grammar -> NFA (bridge to A1/A2)
│   ├── cfg_protocol.py             #   input/output protocol of Section 2.2 (shared by cli/main.py and /grammar/report)
│   └── cfg_export.py               #   CSV and LaTeX tables, DOT and SVG drawings (extra)
├── templates/                      # hub, grammar, sdd, minimization pages + shared rail
└── static/                         # app.css, common.js, vendor/viz-standalone.js
cli/main.py, cli/sdd_cli.py         # stdin/stdout programs required by the assignment
examples/                           # sample inputs: CLI inputs (ex*.txt, sdd_*.txt) and request bodies (test_*.json/txt)
tests/                              # pytest
render.yaml, DESPLIEGUE.md          # deployment on Render and its explanation
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
`/convert` and `/simulate` check the type of every field and say which one is wrong and how it must be written; `/convert`
stops with a 400 when the subset construction would create more than 1000 DFA states (an NFA with n states can need 2^n).

## Other output formats (extra)

Three endpoints return files instead of JSON. They are sent `inline` with a file name, so `curl` prints them and a
browser shows them (or saves them with that name). Errors are still JSON with HTTP 400.

| Endpoint | Body | Answer |
|---|---|---|
| `POST /grammar/report` | JSON `{"grammar", "inputs", "parser": "auto"\|"ll1"\|"slr1", "sets": true, "tables": false, "trace": false}`, or as `text/plain` exactly the stdin of `cli/main.py` (flags as `?sets=&tables=&trace=`) | `text/plain`: exactly what `python cli/main.py --sets [--tables] [--trace]` prints |
| `POST /grammar/export` | `{"grammar", "table": "sets"\|"ll1"\|"slr1"\|"all", "format": "csv"\|"latex", "standalone": false}` | `text/csv` (one table) or `text/x-tex` (`all` gives the three tables; `standalone` makes a complete document) |
| `POST /grammar/graph` | `{"grammar", "graph": "lr0"\|"tree", "format": "svg"\|"dot", "input": "...", "parser": "auto"}` | `image/svg+xml` or `text/vnd.graphviz`: the LR(0) automaton, or the parse tree of `input` |

```bash
curl -s localhost:5000/grammar/report -H 'Content-Type: text/plain' --data-binary @examples/ex2.txt
curl -s localhost:5000/grammar/report -H 'Content-Type: application/json' \
     -d '{"grammar": "3\nS -> S+T T\nT -> T*F F\nF -> (S) i", "inputs": ["i+i", "(i"], "trace": true}'
curl -s localhost:5000/grammar/export -H 'Content-Type: application/json' \
     -d '{"grammar": "3\nS -> S+T T\nT -> T*F F\nF -> (S) i", "table": "slr1"}' -o slr1.csv
curl -s localhost:5000/grammar/export -H 'Content-Type: application/json' \
     -d '{"grammar": "3\nS -> S+T T\nT -> T*F F\nF -> (S) i", "table": "all", "format": "latex", "standalone": true}' -o tables.tex
curl -s localhost:5000/grammar/graph -H 'Content-Type: application/json' \
     -d '{"grammar": "3\nS -> S+T T\nT -> T*F F\nF -> (S) i"}' -o lr0.svg
curl -s localhost:5000/grammar/graph -H 'Content-Type: application/json' \
     -d '{"grammar": "3\nS -> AB\nA -> aA d\nB -> bBc e", "graph": "tree", "input": "adbc"}' -o tree.svg
```

In PowerShell use `curl.exe` and put the JSON in a file (`-d "@body.json"`), because PowerShell changes the quotes.

- **CSV** uses the notation of the JSON answers (`A -> aB`, `e`, `shift 5`, `reduce T -> F`, `accept`); the SLR(1)
  columns are named `ACTION[a]` and `GOTO[A]`. A cell with a conflict keeps every entry, separated by ` / `.
- **LaTeX** uses the book's notation (A → aB, ε, `s5`, `r4`, `acc`) and only plain `tabular`, so no extra package is
  needed; with the SLR(1) table it also prints the numbered productions that `rN` refers to. Every special character
  of the grammar (`$ & % # _ { } [ ]` …) is escaped.
- **SVG** is laid out by the server (no Graphviz needed). In the LR(0) automaton column *k* holds the states at distance
  *k* from I0; transitions into the next column and self-loops are arrows, and the rest are written inside the box of
  their source as `GOTO: X → In`, so no arrow crosses a box. The accepting state (the one with `S' -> S.`) has a green
  border. The parse tree draws an ε leaf under every ε-production. **DOT** draws every transition as an edge, for
  Graphviz or the browser pages.

## Generative AI tools

<Review this list, add every other use by the group (and for which parts), and keep only what is true.>

- **Claude (Anthropic), in Claude Code**, October 2026, to review the finished project against the assignment and to
  write these changes, which the group reviewed: the natural order of DFA state names in `/convert` (`0-2-10`, not
  `0-10-2`); the fix of an HTTP 500 when the LR(0) collection has more than 400 states; the input checks and the
  1000-state limit of `/convert` and `/simulate`; the three extra endpoints `/grammar/report`, `/grammar/export` and
  `/grammar/graph` (`cfg_protocol.py`, now shared with `cli/main.py`, and `cfg_export.py`) with their tests; the
  deployment files (`render.yaml`, gunicorn, `run_options` in `src/app.py`, `DESPLIEGUE.md`); and a CSS fix for phones.
- <Other tools or uses, or "No other AI tools were used.">
