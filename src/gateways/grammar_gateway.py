# GATEWAY layer for Items 1-2: orchestrates the grammar functions and translates any internal
# exception into a ValueError (-> HTTP 400), the same pattern as AutomataGateway.
from functions.cfg_grammar import GrammarError, parse_grammar, sets_json
from functions.cfg_ll1 import LL1
from functions.cfg_regular import right_linear_to_nfa
from functions.cfg_slr1 import SLR1, MAX_STATES

MAX_GRAMMAR_CHARS = 20000
MAX_STRINGS = 200
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
    def _verdict(ll, slr):
        if ll.is_ll1 and slr.is_slr1:
            return 1, "Select a parser (T: for LL(1), B: for SLR(1), Q: quit):", ["ll1", "slr1"]
        if ll.is_ll1:
            return 2, "Grammar is LL(1).", ["ll1"]
        if slr.is_slr1:
            return 3, "Grammar is SLR(1).", ["slr1"]
        return 4, "Grammar is neither LL(1) nor SLR(1).", []

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
        case, message, parsers = self._verdict(ll, slr)
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
        case, message, parsers = self._verdict(ll, slr)
        if parser == "auto":
            if not parsers:
                return {"case": case, "message": message, "results": []}
            parser = parsers[0]
        if parser not in ("ll1", "slr1"):
            raise ValueError("Field 'parser' must be 'll1', 'slr1' or 'auto'.")
        if parser not in parsers:
            name = "LL(1)" if parser == "ll1" else "SLR(1)"
            raise ValueError(f"The grammar is not {name}; its parser cannot be used ({message})")
        if not isinstance(strings, list) or len(strings) > MAX_STRINGS or not all(isinstance(s, str) for s in strings):
            raise ValueError(f"Field 'inputs' must be a list of at most {MAX_STRINGS} strings (the empty string is written 'e' or '').")
        p = ll if parser == "ll1" else slr
        results = []
        for s in strings:
            w = "" if s.strip() == "e" else s.strip()
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
