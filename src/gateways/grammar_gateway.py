# GATEWAY layer for Items 1-2: orchestrates the grammar functions and translates any internal
# exception into a ValueError (-> HTTP 400), the same pattern as AutomataGateway.
import io

from functions import cfg_export as export
from functions.cfg_grammar import GrammarError, parse_grammar, sets_json
from functions.cfg_ll1 import LL1
from functions.cfg_protocol import line_reader, read_grammar, run_session, verdict
from functions.cfg_regular import right_linear_to_nfa
from functions.cfg_slr1 import SLR1, MAX_STATES

MAX_GRAMMAR_CHARS = 20000
MAX_STRINGS = 200
MAX_REPORT_LINES = 1000          # a text/plain report body: the grammar, the parser choice and the strings
BOOK = {
    "first/follow": "Aho et al., Compilers 2nd ed., Section 4.4.2",
    "ll1": "Section 4.4.3 (LL(1) condition, Algorithm 4.31) and Section 4.4.4 (Algorithm 4.34)",
    "slr1": "Sections 4.5 and 4.6 (LR(0) items 4.6.2, parsing algorithm 4.6.3, SLR tables 4.6.4)",
}


class GrammarGateway:

    def load(self, text):
        if not isinstance(text, str):
            raise GrammarError("Field 'grammar' must be a string in the course format (n, then n production lines).")
        if len(text) > MAX_GRAMMAR_CHARS:
            raise GrammarError(f"Grammar longer than {MAX_GRAMMAR_CHARS} characters.")
        return parse_grammar(text)

    @staticmethod
    def _choose(parser, parsers, message):
        """'auto' picks the first usable parser (LL(1) when both are), or None when there is none."""
        if parser not in ("auto", "ll1", "slr1"):
            raise ValueError("Field 'parser' must be 'll1', 'slr1' or 'auto'.")
        if parser == "auto":
            return parsers[0] if parsers else None
        if parser not in parsers:
            name = "LL(1)" if parser == "ll1" else "SLR(1)"
            raise ValueError(f"The grammar is not {name}; its parser cannot be used ({message})")
        return parser

    @staticmethod
    def _words(strings):
        if not isinstance(strings, list) or len(strings) > MAX_STRINGS or not all(isinstance(s, str) for s in strings):
            raise ValueError(f"Field 'inputs' must be a list of at most {MAX_STRINGS} strings (the empty string is written 'e' or '').")
        return ["" if s.strip() == "e" else s.strip() for s in strings]

    def sets(self, text):
        g = self.load(text)
        out = sets_json(g)
        out.update(productions=g.productions_json(), nonterminals=g.nonterminals, terminals=g.terminals,
                   leftRecursive=g.left_recursive(), reference=BOOK["first/follow"])
        return out

    def ll1(self, text):
        g = self.load(text)
        ll = LL1(g)
        return {"isLL1": ll.is_ll1, "violations": ll.violations, "tableConflicts": ll.conflicts,
                "table": ll.table_json(), "tableLines": ll.table_lines(),
                "leftRecursive": g.left_recursive(), "reference": BOOK["ll1"]}

    def slr1(self, text):
        g = self.load(text)
        slr = SLR1(g)
        out = {"isSLR1": slr.is_slr1, "conflicts": slr.conflicts, "numStates": len(slr.states),
               "tooBig": slr.too_big, "reference": BOOK["slr1"]}
        if slr.too_big:
            out["message"] = f"The LR(0) collection exceeds {MAX_STATES} states; tables were not built."
            return out
        out.update(automaton=slr.automaton_json(), table=slr.table_json(), dot=slr.dot(),
                   augmented=[f"{h} -> {''.join(b) or 'e'}" for h, b in slr.aug[:1]])
        return out

    def analyze(self, text):
        """The decision of Section 2.2.2 plus every table (what the CLI prints with --sets/--tables)."""
        g = self.load(text)
        ll, slr = LL1(g), SLR1(g)
        case, message, parsers = verdict(ll, slr)
        out = {"case": case, "message": message, "parsers": parsers, "isLL1": ll.is_ll1, "isSLR1": slr.is_slr1,
               "productions": g.productions_json(), "sets": sets_json(g), "leftRecursive": g.left_recursive(),
               "ll1": {"violations": ll.violations, "tableConflicts": ll.conflicts, "table": ll.table_json(),
                       "tableLines": ll.table_lines()},
               "slr1": {"conflicts": slr.conflicts, "numStates": len(slr.states), "tooBig": slr.too_big}}
        if not slr.too_big:
            out["slr1"].update(automaton=slr.automaton_json(), table=slr.table_json(), dot=slr.dot())
        return out

    def parse(self, text, strings, parser="auto", trace=False):
        g = self.load(text)
        ll, slr = LL1(g), SLR1(g)
        case, message, parsers = verdict(ll, slr)
        parser = self._choose(parser, parsers, message)
        if parser is None:
            return {"case": case, "message": message, "results": []}
        p = ll if parser == "ll1" else slr
        results = []
        for s, w in zip(strings, self._words(strings)):
            r = p.parse(w, trace=trace)
            item = {"input": s, "accepted": r["accepted"], "answer": "yes" if r["accepted"] else "no"}
            if r["accepted"]:
                item["tree"] = r["tree"]
            else:
                item["error"] = r["error"]
            if trace:
                item["trace"] = r["trace"]
            results.append(item)
        return {"case": case, "message": message, "parser": parser, "results": results}

    def to_nfa(self, text):
        g = self.load(text)
        try:
            return right_linear_to_nfa(g)
        except ValueError as e:
            raise ValueError(str(e))

    # ------------------------------------------------------------ other output formats (extra)
    def report_text(self, body, sets=True, tables=False, trace=False):
        """`body` is exactly what cli/main.py reads on stdin; the answer is exactly what it prints (same code)."""
        if not body.strip():
            raise GrammarError("Empty body.")
        if body.count("\n") > MAX_REPORT_LINES:
            raise ValueError(f"At most {MAX_REPORT_LINES} lines (grammar, parser choice and strings).")
        read = line_reader(io.StringIO(body).readline)
        g = read_grammar(read)
        out = []
        run_session(g, LL1(g), SLR1(g), read, out.append, sets, tables, trace)
        return "\n".join(out) + "\n"

    def report(self, text, strings, parser="auto", sets=True, tables=False, trace=False):
        """JSON version of report_text: the strings and the parser come as fields and are turned into the lines the
        program would read (T or B when it asks, the strings, an empty line, Q)."""
        g = self.load(text)
        ll, slr = LL1(g), SLR1(g)
        case, message, parsers = verdict(ll, slr)
        parser = self._choose(parser, parsers, message)
        lines = []
        if parser:
            words = self._words(strings)
            if any("\n" in w or "\r" in w for w in words):
                raise ValueError("Strings cannot contain line breaks.")
            lines = (["T" if parser == "ll1" else "B"] if case == 1 else []) + [w or "e" for w in words] + ["", "Q"]
        it, out = iter(lines), []
        run_session(g, ll, slr, lambda: next(it, None), out.append, sets, tables, trace)
        return "\n".join(out) + "\n"

    def export(self, text, table="sets", fmt="csv", standalone=False):
        """FIRST/FOLLOW, the LL(1) table or the SLR(1) table as CSV (one table) or LaTeX ('all' gives the three)."""
        if fmt not in ("csv", "latex"):
            raise ValueError("Field 'format' must be 'csv' or 'latex'.")
        if table not in ("sets", "ll1", "slr1", "all"):
            raise ValueError("Field 'table' must be 'sets', 'll1', 'slr1' or 'all'.")
        if table == "all" and fmt == "csv":
            raise ValueError("A CSV file holds one table: use 'sets', 'll1' or 'slr1' (or format 'latex' for all of them).")
        g = self.load(text)
        slr = SLR1(g) if table in ("slr1", "all") else None
        if slr and slr.too_big:
            raise ValueError(f"The LR(0) collection exceeds {MAX_STATES} states; the SLR(1) table was not built.")
        cells = (export.PlainCells if fmt == "csv" else export.TexCells)(slr)
        tables = []
        if table in ("sets", "all"):
            tables.append(export.sets_table(g, cells))
        if table in ("ll1", "all"):
            tables.append(export.ll1_table(g, LL1(g), cells))
        if table in ("slr1", "all"):
            if fmt == "latex":
                tables.append(export.numbered_productions(slr, cells))
            tables.append(export.slr1_table(g, slr, cells))
        if fmt == "csv":
            return {"content": export.to_csv(tables[0]), "format": "csv", "filename": f"{table}.csv"}
        return {"content": export.to_latex(tables, standalone), "format": "latex", "filename": f"{table}.tex"}

    def graph(self, text, graph="lr0", fmt="svg", string=None, parser="auto"):
        """The LR(0) automaton, or the parse tree of `string`, as Graphviz DOT or SVG."""
        if fmt not in ("svg", "dot"):
            raise ValueError("Field 'format' must be 'svg' or 'dot'.")
        if graph not in ("lr0", "tree"):
            raise ValueError("Field 'graph' must be 'lr0' (LR(0) automaton) or 'tree' (parse tree of 'input').")
        g = self.load(text)
        if graph == "lr0":
            slr = SLR1(g)
            if slr.too_big:
                raise ValueError(f"The LR(0) collection exceeds {MAX_STATES} states; it is too big to draw.")
            content = export.lr0_svg(slr) if fmt == "svg" else slr.dot() + "\n"
            return {"content": content, "format": fmt, "filename": f"lr0.{fmt}"}
        if not isinstance(string, str):
            raise ValueError("Field 'input' (the string to parse) is required for a parse tree.")
        ll, slr = LL1(g), SLR1(g)
        case, message, parsers = verdict(ll, slr)
        parser = self._choose(parser, parsers, message)
        if parser is None:
            raise ValueError(f"No parse tree: {message}")
        w = self._words([string])[0]
        res = (ll if parser == "ll1" else slr).parse(w)
        if not res["accepted"]:
            shown = string if len(string) <= 40 else string[:40] + "..."
            raise ValueError(f"The string {shown!r} is not in the language: {res['error']['message']}")
        title = f"Parse tree of {w or 'e'} ({'LL(1)' if parser == 'll1' else 'SLR(1)'})"
        content = export.tree_svg(res["_root"], title) if fmt == "svg" else export.tree_dot(res["_root"])
        return {"content": content, "format": fmt, "filename": f"tree.{fmt}"}
