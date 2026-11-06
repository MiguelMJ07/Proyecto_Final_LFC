"""SLR(1): LR(0) items, CLOSURE and GOTO (Section 4.6.2), the canonical collection of LR(0) item sets,
ACTION/GOTO tables built from FOLLOW (Section 4.6.4) and the LR parsing algorithm (Section 4.6.3).
The grammar is augmented with S' -> S. Conflicts (Section 4.5.4) are recorded, never hidden."""
from functions.cfg_grammar import EPS, END, is_nt, prod_str
from functions.cfg_tree import Node, tree_to_dict

MAX_STATES = 400
MAX_TRACE_STEPS = 5000
MAX_INPUT = 2000
AUG = "S'"


class SLR1:
    def __init__(self, g):
        self.g = g
        self.aug = [(AUG, (g.start,))] + g.prods     # production 0 is S' -> S
        self.states = []                              # frozensets of items (production, dot)
        self.trans = {}                               # (state, symbol) -> state
        self.too_big = False
        self._build_collection()
        self.action = {}                              # (state, terminal or $) -> [actions]
        self.goto = {}                                # (state, nonterminal) -> state
        self.conflicts = []
        if not self.too_big:                          # a truncated collection has GOTOs to missing states
            self._build_tables()
        self.is_slr1 = not self.too_big and not self.conflicts

    # ------------------------------------------------ CLOSURE / GOTO (4.6.2)
    def closure(self, items):
        J = set(items)
        work = list(J)
        while work:
            p, d = work.pop()
            body = self.aug[p][1]
            if d < len(body) and is_nt(body[d]):
                for q, (h, _) in enumerate(self.aug):
                    if h == body[d] and (q, 0) not in J:
                        J.add((q, 0))
                        work.append((q, 0))
        return frozenset(J)

    def goto_set(self, I, X):
        moved = {(p, d + 1) for p, d in I if d < len(self.aug[p][1]) and self.aug[p][1][d] == X}
        return self.closure(moved) if moved else frozenset()

    def _build_collection(self):
        I0 = self.closure({(0, 0)})
        self.states = [I0]
        index = {I0: 0}
        symbols = sorted(set(self.g.terminals) | set(self.g.nonterminals))
        k = 0
        while k < len(self.states):
            for X in symbols:
                J = self.goto_set(self.states[k], X)
                if not J:
                    continue
                if J not in index:
                    if len(self.states) >= MAX_STATES:
                        self.too_big = True
                        return
                    index[J] = len(self.states)
                    self.states.append(J)
                self.trans[(k, X)] = index[J]
            k += 1

    # ------------------------------------------------ ACTION / GOTO (4.6.4)
    def _act_str(self, act):
        if act[0] == "s":
            return f"shift {act[1]}"
        if act[0] == "r":
            return f"reduce {prod_str(*self.aug[act[1]])}"
        return "accept"

    def _put(self, s, a, act):
        cell = self.action.setdefault((s, a), [])
        if act not in cell:
            cell.append(act)

    def _build_tables(self):
        for s, I in enumerate(self.states):
            for p, d in sorted(I):
                head, body = self.aug[p]
                if d < len(body):
                    a = body[d]
                    if not is_nt(a):
                        self._put(s, a, ("s", self.trans[(s, a)]))
                elif p == 0:
                    self._put(s, END, ("acc",))
                else:
                    for a in self.g.follow[head]:
                        self._put(s, a, ("r", p))
            for A in self.g.nonterminals:
                if (s, A) in self.trans:
                    self.goto[(s, A)] = self.trans[(s, A)]
        for (s, a), cell in sorted(self.action.items()):
            if len(cell) > 1:
                kinds = sorted({c[0] for c in cell})
                kind = "shift/reduce" if "s" in kinds else "reduce/reduce"
                self.conflicts.append({"state": s, "symbol": a, "type": kind,
                                       "actions": [self._act_str(c) for c in cell]})

    # ------------------------------------------------ output helpers
    def item_str(self, p, d):
        h, b = self.aug[p]
        return f"{h} -> {''.join(b[:d])}.{''.join(b[d:])}"

    def automaton_json(self):
        return {
            "states": [{"id": s, "items": [self.item_str(p, d) for p, d in sorted(I)],
                        "kernel": [self.item_str(p, d) for p, d in sorted(I) if d > 0 or p == 0]}
                       for s, I in enumerate(self.states)],
            "transitions": [{"from": s, "symbol": X, "to": t} for (s, X), t in sorted(self.trans.items())],
        }

    def table_json(self):
        g = self.g
        tcols = g.terminals + [END]
        rows = []
        for s in range(len(self.states)):
            act = {a: [self._act_str(c) for c in self.action[(s, a)]] for a in tcols if (s, a) in self.action}
            gt = {A: self.goto[(s, A)] for A in g.nonterminals if (s, A) in self.goto}
            rows.append({"state": s, "action": act, "goto": gt})
        return {"terminals": tcols, "nonterminals": g.nonterminals, "rows": rows, "conflicts": self.conflicts}

    def dot(self):
        lines = ["digraph LR0 {", "  rankdir=LR;", '  node [shape=box, fontname="monospace", fontsize=11];']
        for s, I in enumerate(self.states):
            label = f"I{s}\\l" + "".join(self.item_str(p, d).replace('"', "'") + "\\l" for p, d in sorted(I))
            lines.append(f'  s{s} [label="{label}"];')
        for (s, X), t in sorted(self.trans.items()):
            lines.append(f'  s{s} -> s{t} [label="{X}"];')
        lines.append("}")
        return "\n".join(lines)

    # ------------------------------------------------ LR parsing algorithm (4.6.3)
    def parse(self, w, trace=False):
        res = {"accepted": False, "tree": None, "trace": [], "error": None, "_root": None}
        if len(w) > MAX_INPUT:
            res["error"] = {"position": 0, "message": f"Input longer than {MAX_INPUT} symbols."}
            return res
        if END in w or EPS in w:
            res["error"] = {"position": 0, "message": "The input cannot contain the reserved symbols 'e' or '$'."}
            return res
        w = list(w) + [END]
        states, nodes, i = [0], [], 0

        def rec(action):
            if trace and len(res["trace"]) < MAX_TRACE_STEPS:
                stack = [{"state": 0, "symbol": None}] + [
                    {"state": q, "symbol": n.symbol} for n, q in zip(nodes, states[1:])]
                res["trace"].append({"stack": stack, "input": "".join(w[i:]), "action": action})

        while True:
            s, a = states[-1], w[i]
            cell = self.action.get((s, a))
            if not cell:
                rec("error")
                res["error"] = {"position": i, "message": f"ACTION[{s},{a}] is an error entry."}
                return res
            act = cell[0]                         # conflict-free grammars only have one action
            if act[0] == "s":
                rec(f"shift {act[1]}")
                n = Node(a)
                n.attrs["lexval"] = a
                nodes.append(n)
                states.append(act[1])
                i += 1
            elif act[0] == "r":
                p = act[1]
                head, body = self.aug[p]
                rec(f"reduce {prod_str(head, body)}")
                k = len(body)
                node = Node(head)
                node.prod = p - 1                 # index in Grammar.prods
                node.children = nodes[len(nodes) - k:]
                del nodes[len(nodes) - k:]
                del states[len(states) - k:]
                nodes.append(node)
                states.append(self.goto[(states[-1], head)])
            else:
                rec("accept")
                root = nodes[-1]
                res.update(accepted=True, tree=tree_to_dict(root), _root=root)
                return res
