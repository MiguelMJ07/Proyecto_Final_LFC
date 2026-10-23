"""LL(1): literal grammar test of Section 4.4.3, predictive parsing table
(Algorithm 4.31) and the table-driven predictive parser (Algorithm 4.34, Fig. 4.20 of Section 4.4.4).
The input grammar is never transformed."""
from functions.cfg_grammar import EPS, END, is_nt, prod_str
from functions.cfg_tree import Node, tree_to_dict

MAX_TRACE_STEPS = 5000
MAX_INPUT = 2000


def _set(items):
    return "{" + ", ".join(items) + "}"


def check_ll1_conditions(g):
    """Section 4.4.3: G is LL(1) iff for every pair of distinct productions A -> alpha | beta:
      1. FIRST(alpha) and FIRST(beta) have no terminal in common (no a with both deriving a...);
      2. at most one of alpha, beta derives epsilon;
      3. if beta =>* epsilon then FIRST(alpha) and FOLLOW(A) are disjoint (and symmetrically).
    Returns the list of violations (empty list <=> LL(1))."""
    violations = []
    by_head = {}
    for idx, (A, body) in enumerate(g.prods):
        by_head.setdefault(A, []).append(idx)
    for A in g.nonterminals:
        ids = by_head[A]
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                i, j = ids[x], ids[y]
                al, be = g.prods[i][1], g.prods[j][1]
                fa, fb = g.first_of(al), g.first_of(be)
                pair = [prod_str(A, al), prod_str(A, be)]
                common = sorted((fa & fb) - {EPS})
                if common:
                    violations.append({"condition": 1, "nonterminal": A, "productions": pair, "symbols": common,
                                       "message": f"FIRST sets of the two {A}-productions share {_set(common)}"})
                if EPS in fa and EPS in fb:
                    violations.append({"condition": 2, "nonterminal": A, "productions": pair, "symbols": [EPS],
                                       "message": f"Both {A}-productions can derive the empty string"})
                for (p_nullable, p_other, f_other, text) in ((fb, fa, fa, "second"), (fa, fb, fb, "first")):
                    if EPS in p_nullable:
                        clash = sorted((f_other - {EPS}) & g.follow[A])
                        if clash:
                            violations.append({
                                "condition": 3, "nonterminal": A, "productions": pair, "symbols": clash,
                                "message": f"The {text} {A}-production derives epsilon, but FIRST of the other "
                                           f"production meets FOLLOW({A}) in {_set(clash)}"})
    return violations


class LL1:
    def __init__(self, g):
        self.g = g
        self.table = {}                          # (A, a) -> [production indices]
        for idx, (A, body) in enumerate(g.prods):          # Algorithm 4.31
            fb = g.first_of(body)
            for a in fb - {EPS}:                 # step 1
                self._add(A, a, idx)
            if EPS in fb:                        # step 2 (FOLLOW(A) contains $ when needed)
                for b in g.follow[A]:
                    self._add(A, b, idx)
        self.violations = check_ll1_conditions(g)
        self.is_ll1 = not self.violations
        self.conflicts = [{"nonterminal": A, "symbol": a, "productions": [prod_str(*g.prods[i]) for i in cell]}
                          for (A, a), cell in sorted(self.table.items()) if len(cell) > 1]

    def _add(self, A, a, idx):
        cell = self.table.setdefault((A, a), [])
        if idx not in cell:
            cell.append(idx)

    def table_json(self):
        g = self.g
        cols = g.terminals + [END]
        rows = []
        for A in g.nonterminals:
            row = {"nonterminal": A, "cells": {}}
            for a in cols:
                cell = self.table.get((A, a))
                if cell:
                    row["cells"][a] = [{"production": i, "text": prod_str(*g.prods[i])} for i in cell]
            rows.append(row)
        return {"columns": cols, "rows": rows}

    def table_lines(self):
        g, out = self.g, []
        for A in g.nonterminals:
            for a in g.terminals + [END]:
                for i in self.table.get((A, a), []):
                    out.append(f"M[{A},{a}] = {prod_str(*g.prods[i])}")
        return out

    def parse(self, w, trace=False):
        """Algorithm 4.34. Returns dict(accepted, tree, trace, error). The tree is built while the
        parser expands nonterminals (the 'additional code' the book mentions)."""
        g = self.g
        res = {"accepted": False, "tree": None, "trace": [], "error": None, "_root": None}
        if len(w) > MAX_INPUT:
            res["error"] = {"position": 0, "message": f"Input longer than {MAX_INPUT} symbols."}
            return res
        if END in w or EPS in w:
            # 'e' is epsilon in grammars, so it can never be an input terminal (empty string is given as "")
            res["error"] = {"position": 0, "message": "The input cannot contain the reserved symbols 'e' or '$'."}
            return res
        w = list(w) + [END]
        root = Node(g.start)
        stack = [None, root]                     # None is the bottom marker $
        i = 0

        def rec(action):
            if trace and len(res["trace"]) < MAX_TRACE_STEPS:
                st = [n.symbol for n in reversed(stack[1:])]      # top of the stack first
                res["trace"].append({"stack": st, "input": "".join(w[i:]), "action": action})

        while True:
            X, a = stack[-1], w[i]
            if X is None:                        # stack is $ : X = $ ends the loop
                if a == END:
                    rec("accept")
                    res.update(accepted=True, tree=tree_to_dict(root), _root=root)
                else:
                    rec("error")
                    res["error"] = {"position": i, "message": f"Unexpected symbol {a!r}; the stack is empty."}
                return res
            if not is_nt(X.symbol):
                if X.symbol == a:                # X = a: pop and advance
                    rec(f"match {a}")
                    X.attrs["lexval"] = a
                    stack.pop()
                    i += 1
                else:
                    rec("error")
                    res["error"] = {"position": i, "message": f"Expected {X.symbol!r} but found {a!r}."}
                    return res
                continue
            cell = self.table.get((X.symbol, a))
            if not cell:
                rec("error")
                res["error"] = {"position": i, "message": f"M[{X.symbol},{a}] is an error entry."}
                return res
            idx = cell[0]
            head, body = g.prods[idx]
            rec(f"output {prod_str(head, body)}")
            stack.pop()
            X.prod = idx
            X.children = [Node(s) for s in body]
            stack.extend(reversed(X.children))
