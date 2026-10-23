"""Syntax-directed definitions (Chapter 5): SDD as data, validation (Section 5.1.1), classification
(Sections 5.2.3 and 5.2.4), dependency graph and topological evaluation order (Sections 5.2.1-5.2.2).
The evaluator knows nothing about any particular SDD: it only reads the compiled rule data."""
import heapq
import re
from dataclasses import dataclass

from functions.cfg_grammar import EPS, Grammar, GrammarError, is_nt, parse_grammar, prod_str
from functions.cfg_ll1 import LL1
from functions.cfg_slr1 import SLR1
from functions.cfg_tree import number_nodes
from functions.safe_expr import ExprError, compile_expr

MAX_RULES = 400
REF = re.compile(r"(?<![\w$.])(\$\d+|\S)\.([A-Za-z_]\w*)")


class SDDError(ValueError):
    pass


@dataclass
class Rule:
    target: tuple          # (position, attribute); position 0 = head, i = i-th body symbol
    deps: list             # [(position, attribute), ...] in the order the function receives them
    fn: object             # callable(list of dependency values) -> value
    text: str              # the rule as written, for display


class SDD:
    def __init__(self, defn):
        self.name = str(defn.get("name", "custom SDD"))
        self.description = str(defn.get("description", ""))
        try:
            self.grammar = parse_grammar(defn["grammar"])
        except KeyError:
            raise SDDError("Missing field 'grammar'.")
        except GrammarError as e:
            raise SDDError(f"Grammar: {e}")
        g = self.grammar
        self.attrs = self._read_attrs(defn)
        self.rules = {i: [] for i in range(len(g.prods))}      # production index -> [Rule]
        self._read_rules(defn)
        main = defn.get("main", "")
        m = re.fullmatch(r"(\S)\.(\w+)", str(main))
        if not m or m.group(1) != g.start or m.group(2) not in self.attrs[g.start]["syn"]:
            raise SDDError(f"'main' must be a synthesized attribute of the start symbol, e.g. 'S.valid' (got {main!r}).")
        self.main = (m.group(1), m.group(2))
        self.warnings = []
        self.validate()

    # --------------------------------------------------------------- reading
    def _read_attrs(self, defn):
        g = self.grammar
        raw = defn.get("attributes")
        if not isinstance(raw, dict):
            raise SDDError("Missing field 'attributes' (a table symbol -> {syn: [...], inh: [...]}).")
        out = {A: {"syn": [], "inh": []} for A in g.nonterminals}
        for sym, d in raw.items():
            if sym not in out:
                raise SDDError(f"Attributes declared for {sym!r}, which is not a nonterminal (terminals only have 'lexval').")
            if not isinstance(d, dict):
                raise SDDError(f"Attributes of {sym} must be an object with 'syn' and 'inh'.")
            for kind in ("syn", "inh"):
                lst = d.get(kind, [])
                if not isinstance(lst, list) or not all(isinstance(a, str) and re.fullmatch(r"[A-Za-z_]\w*", a) for a in lst):
                    raise SDDError(f"{sym}.{kind} must be a list of attribute names.")
                out[sym][kind] = list(lst)
            both = set(out[sym]["syn"]) & set(out[sym]["inh"])
            if both or len(set(out[sym]["syn"] + out[sym]["inh"])) != len(out[sym]["syn"] + out[sym]["inh"]):
                raise SDDError(f"Attribute names of {sym} must be unique ({sorted(both) or 'duplicates'}).")
        return out

    def attr_names(self, sym):
        if is_nt(sym):
            return self.attrs[sym]["inh"] + self.attrs[sym]["syn"]
        return ["lexval"]

    def _expand_key(self, key):
        """'D -> 0 1 2' means the same rules for productions D -> 0, D -> 1, D -> 2."""
        if "->" not in key:
            raise SDDError(f"Rule key {key!r} must look like 'A -> alternative'.")
        head, rhs = (s.strip() for s in key.split("->", 1))
        idxs = []
        for alt in rhs.split():
            body = () if alt == EPS else tuple(alt)
            found = [i for i, (h, b) in enumerate(self.grammar.prods) if h == head and b == body]
            if not found:
                raise SDDError(f"Rule key {key!r}: production {head} -> {alt} is not in the grammar.")
            idxs.append(found[0])
        if not idxs:
            raise SDDError(f"Rule key {key!r} has no alternative.")
        return idxs

    def _resolve(self, ref, attr, prod_idx):
        head, body = self.grammar.prods[prod_idx]
        syms = [head] + list(body)
        if ref.startswith("$"):
            pos = int(ref[1:])
            if pos >= len(syms):
                raise SDDError(f"In {prod_str(head, body)}: {ref} is out of range (the body has {len(body)} symbols).")
        else:
            cands = [i for i, s in enumerate(syms) if s == ref]
            if not cands:
                raise SDDError(f"In {prod_str(head, body)}: symbol {ref!r} does not occur in the production.")
            if len(cands) > 1:
                raise SDDError(f"In {prod_str(head, body)}: {ref!r} occurs more than once; "
                               f"write $0 for the head and $1..${len(body)} for body positions.")
            pos = cands[0]
        if attr not in self.attr_names(syms[pos]):
            raise SDDError(f"In {prod_str(head, body)}: {syms[pos]} has no attribute {attr!r}.")
        return pos, attr

    def _read_rules(self, defn):
        raw = defn.get("rules")
        if not isinstance(raw, dict):
            raise SDDError("Missing field 'rules' (a table production -> list of rules).")
        total = 0
        for key, lines in raw.items():
            if isinstance(lines, str):
                lines = [lines]
            if not isinstance(lines, list):
                raise SDDError(f"The rules of {key!r} must be a list of strings.")
            for idx in self._expand_key(key):
                for line in lines:
                    total += 1
                    if total > MAX_RULES:
                        raise SDDError(f"Too many rules (limit {MAX_RULES}).")
                    self.rules[idx].append(self._compile_rule(line, idx))

    def _compile_rule(self, line, idx):
        if not isinstance(line, str) or "=" not in line:
            raise SDDError(f"A rule must look like 'X.attr = expression', got {line!r}.")
        lhs, expr = line.split("=", 1)
        if expr.startswith("="):
            raise SDDError(f"Rule {line!r}: the target must be on the left of a single '='.")
        m = REF.fullmatch(lhs.strip())
        if not m:
            raise SDDError(f"Rule {line!r}: left side must be an attribute reference like L.cnt or $2.k.")
        target = self._resolve(m.group(1), m.group(2), idx)
        deps, names = [], {}

        def sub(mo):
            d = self._resolve(mo.group(1), mo.group(2), idx)
            if d not in deps:
                deps.append(d)
            name = f"_r{d[0]}_{d[1]}"
            names[name] = d
            return name

        py = REF.sub(sub, expr)
        try:
            f = compile_expr(py, set(names))
        except ExprError as e:
            raise SDDError(f"Rule {line!r}: {e}")
        order = list(deps)
        fn = lambda vals, f=f, order=order: f({f"_r{p}_{a}": v for (p, a), v in zip(order, vals)})
        return Rule(target, order, fn, line.strip())

    # ------------------------------------------------------------ validation
    def validate(self):
        """Section 5.1.1: every rule defines a synthesized attribute of the head or an inherited attribute of a body
        symbol; each such attribute is defined exactly once; the start symbol has no inherited attributes."""
        g = self.grammar
        if self.attrs[g.start]["inh"]:
            raise SDDError("The start symbol must not have inherited attributes.")
        for idx, (head, body) in enumerate(g.prods):
            needed = {(0, a) for a in self.attrs[head]["syn"]}
            for i, X in enumerate(body, 1):
                if is_nt(X):
                    needed |= {(i, a) for a in self.attrs[X]["inh"]}
            defined = [r.target for r in self.rules[idx]]
            where = prod_str(head, body)
            for t in defined:
                if t not in needed:
                    raise SDDError(f"In {where}: the rule defining {self.pos_name(idx, t)} is not allowed; "
                                   f"rules may only define synthesized attributes of the head or inherited attributes "
                                   f"of body symbols (Section 5.1.1).")
            for t in needed:
                n = defined.count(t)
                if n == 0:
                    raise SDDError(f"In {where}: {self.pos_name(idx, t)} is never defined.")
                if n > 1:
                    raise SDDError(f"In {where}: {self.pos_name(idx, t)} is defined {n} times.")
        syn_total = sum(len(v["syn"]) for v in self.attrs.values())
        inh_total = sum(len(v["inh"]) for v in self.attrs.values())
        if syn_total < 1 or inh_total < 1 or syn_total + inh_total < 2:
            self.warnings.append("The assignment asks for at least one synthesized and one inherited attribute.")
        if len(g.nonterminals) < 3 or len(g.prods) < 6 or not self._recursive():
            self.warnings.append("The assignment asks for at least 3 nonterminals, 6 productions and a recursive nonterminal (G2).")

    def _recursive(self):
        g = self.grammar
        reach = {A: {x for h, b in g.prods if h == A for x in b if is_nt(x)} for A in g.nonterminals}
        changed = True
        while changed:
            changed = False
            for A in reach:
                new = set().union(*(reach[B] for B in reach[A])) - reach[A] if reach[A] else set()
                if new:
                    reach[A] |= new
                    changed = True
        return any(A in reach[A] for A in reach)

    def pos_name(self, idx, t):
        head, body = self.grammar.prods[idx]
        syms = [head] + list(body)
        return f"{syms[t[0]]}.{t[1]}" + (f" (position {t[0]})" if t[0] and syms.count(syms[t[0]]) > 1 else "")

    # -------------------------------------------------------- classification
    def classify(self):
        """S-attributed: only synthesized attributes (5.2.3). L-attributed (5.2.4): for A -> X1..Xn each rule
        defining an inherited attribute of Xi uses only (a) inherited attributes of A, (b) attributes of X1..X(i-1),
        (c) attributes of Xi itself provided there is no cycle among Xi's attributes."""
        g = self.grammar
        s_attr = all(not v["inh"] for v in self.attrs.values())
        reasons = []
        for idx, (head, body) in enumerate(g.prods):
            for r in self.rules[idx]:
                i = r.target[0]
                if i == 0 or not is_nt(body[i - 1]):
                    continue                                   # synthesized rules may use anything
                for (p, a) in r.deps:
                    if p == 0 and a in self.attrs[head]["syn"]:
                        reasons.append(f"{prod_str(head, body)}: rule '{r.text}' uses {head}.{a}, a synthesized attribute of the head (not allowed for an inherited attribute).")
                    elif p > i:
                        reasons.append(f"{prod_str(head, body)}: rule '{r.text}' uses {self.pos_name(idx, (p, a))}, "
                                       f"an attribute of a symbol to the right of {body[i - 1]} (Section 5.2.4).")
                    elif p == i:
                        own = [x for x in self.rules[idx] if x.target[0] == i and all(d[0] == i for d in x.deps)]
                        if self._cyclic_among(own):
                            reasons.append(f"{prod_str(head, body)}: the attributes of {body[i - 1]} depend on each other cyclically.")
        l_attr = not reasons
        return {"sAttributed": s_attr, "lAttributed": l_attr, "reasons": reasons,
                "verdict": ("S-attributed and L-attributed" if s_attr else "L-attributed (not S-attributed)" if l_attr
                            else "neither S-attributed nor L-attributed")}

    @staticmethod
    def _cyclic_among(rules):
        edges = {}
        for r in rules:
            for d in r.deps:
                edges.setdefault(d, set()).add(r.target)
        seen, onstack = set(), set()

        def dfs(u):
            seen.add(u); onstack.add(u)
            for v in edges.get(u, ()):
                if v in onstack or (v not in seen and dfs(v)):
                    return True
            onstack.discard(u)
            return False
        return any(u not in seen and dfs(u) for u in list(edges))

    # ------------------------------------------------------------ description
    def describe(self):
        g = self.grammar
        return {
            "name": self.name, "description": self.description,
            "grammar": [prod_str(h, b) for h, b in g.prods],
            "attributes": [{"symbol": A, "attribute": a, "kind": k}
                           for A in g.nonterminals for k, lst in (("inherited", self.attrs[A]["inh"]), ("synthesized", self.attrs[A]["syn"])) for a in lst]
                          + [{"symbol": "(terminals)", "attribute": "lexval", "kind": "synthesized (scanner)"}],
            "rules": [{"production": prod_str(h, b), "rules": [r.text for r in self.rules[i]]}
                      for i, (h, b) in enumerate(g.prods)],
            "main": f"{self.main[0]}.{self.main[1]}",
            "classification": self.classify(),
            "warnings": self.warnings,
        }

    # ------------------------------------------------------------- evaluation
    def pick_parser(self):
        ll, slr = LL1(self.grammar), SLR1(self.grammar)
        if ll.is_ll1:
            return "LL(1)", ll
        if slr.is_slr1:
            return "SLR(1)", slr
        raise SDDError("The SDD grammar must be LL(1) or SLR(1) (condition G1).")


def build_graph(sdd, nodes):
    """Instantiates the rules of every internal node (Section 5.2.1).
    Returns (rules, edges): rules[v] = (Rule, [dependency vertices]); edges = [(used, defined)].
    A vertex is (node id, attribute)."""
    rules, edges = {}, []
    for n in nodes:
        if n.prod is None:
            continue                          # leaves provide their lexval
        pos = [n] + n.children
        for r in sdd.rules[n.prod]:
            tgt = (pos[r.target[0]].id, r.target[1])
            deps = [(pos[p].id, a) for p, a in r.deps]
            rules[tgt] = (r, deps)
            edges.extend((d, tgt) for d in deps)
    return rules, edges


def topological_order(rules, edges, rank):
    """Kahn's algorithm (Section 5.2.2). `rank` gives a deterministic tie-break.
    Returns (order, None) or (None, cycle)."""
    indeg = {v: 0 for v in rules}
    succ = {}
    for u, v in edges:
        succ.setdefault(u, []).append(v)
        if u in rules:                        # edges out of leaves (lexval) are already satisfied
            indeg[v] += 1
    ready = [(rank(v), v) for v, d in indeg.items() if d == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        _, u = heapq.heappop(ready)
        order.append(u)
        for v in succ.get(u, ()):
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(ready, (rank(v), v))
    if len(order) == len(rules):
        return order, None
    done = set(order)
    rest = {v for v in rules if v not in done}
    v = min(rest, key=rank)
    path = []
    while v not in path:                      # every remaining vertex has a remaining predecessor
        path.append(v)
        v = next(d for d in rules[v][1] if d in rest)
    cyc = path[path.index(v):]
    return None, cyc + [cyc[0]]


# ------------------------------------------------------------------ evaluation
def vname(nodes, v):
    return f"{nodes[v[0]].symbol}#{v[0]}.{v[1]}"


def graph_dot(sdd, nodes, edges, cycle=None):
    """Graphviz source of the dependency graph: one vertex per attribute of each node (clustered by
    parse-tree node), dependency edges in blue (used -> defined), parse-tree edges in dashed gray."""
    lines = ["digraph G {", "  compound=true; rankdir=TB; fontname=Helvetica;",
             '  node [shape=ellipse, fontname=Helvetica, fontsize=11]; edge [fontname=Helvetica];']
    cyc_edges = set(zip(cycle, cycle[1:])) if cycle else set()
    for n in nodes:
        attrs = sdd.attr_names(n.symbol) if (n.prod is not None or is_nt(n.symbol)) else ["lexval"]
        lines.append(f'  subgraph cluster_{n.id} {{ label="{n.symbol.replace(chr(34), "")}#{n.id}"; style=rounded; color="#9ca3af";')
        lines.append(f'    h{n.id} [label="", shape=point, width=0.01];')
        for a in attrs:
            lines.append(f'    v{n.id}_{a} [label="{a}"];')
        lines.append("  }")
    for n in nodes:
        for c in n.children:
            lines.append(f"  h{n.id} -> h{c.id} [style=dashed, color=\"#9ca3af\", arrowhead=none, ltail=cluster_{n.id}, lhead=cluster_{c.id}];")
    for (u, v) in edges:
        bad = (u, v) in cyc_edges
        lines.append(f'  v{u[0]}_{u[1]} -> v{v[0]}_{v[1]} [color="{"#dc2626" if bad else "#2563eb"}"{", penwidth=2.5" if bad else ""}];')
    lines.append("}")
    return "\n".join(lines)


def evaluate(sdd, w, max_nodes=20000):
    """Parses `w` with the Item-2 parser of the SDD grammar, builds the dependency graph, orders it
    topologically and evaluates. Returns a JSON-ready dict."""
    pname, parser = sdd.pick_parser()
    res = parser.parse(w)
    out = {"input": w, "parser": pname}
    if not res["accepted"]:
        out.update(accepted=False, error=res["error"])
        return out
    root = res["_root"]
    nodes = number_nodes(root)
    if len(nodes) > max_nodes:
        raise SDDError(f"Parse tree too large ({len(nodes)} nodes).")
    values = {(n.id, "lexval"): n.attrs["lexval"] for n in nodes if n.prod is None and "lexval" in n.attrs}
    rules, edges = build_graph(sdd, nodes)
    attr_rank = {}
    rank = lambda v: (v[0], attr_rank.setdefault(v[1], len(attr_rank)), v[1])
    order, cycle = topological_order(rules, edges, rank)
    out["accepted"] = True
    out["edges"] = [{"from": vname(nodes, u), "to": vname(nodes, v)} for u, v in edges]
    out["stats"] = {"treeNodes": len(nodes), "attributeInstances": len(rules), "edges": len(edges)}
    if cycle:
        out.update(circular=True, cycle=[vname(nodes, v) for v in cycle],
                   dot=graph_dot(sdd, nodes, edges, cycle),
                   message="The SDD is circular: the dependency graph of this parse tree has a cycle.")
        out["tree"] = _annotated_tree(nodes, {})
        return out
    steps = []
    for k, v in enumerate(order, 1):
        r, deps = rules[v]
        try:
            val = r.fn([values[d] for d in deps])
        except ExprError as e:
            raise SDDError(f"Evaluating {vname(nodes, v)} with rule '{r.text}': {e}")
        values[v] = val
        steps.append({"step": k, "vertex": vname(nodes, v), "id": f"v{v[0]}_{v[1]}", "rule": r.text,
                      "uses": [{"vertex": vname(nodes, d), "value": values[d]} for d in deps], "value": val})
    out.update(circular=False, order=steps, dot=graph_dot(sdd, nodes, edges),
               tree=_annotated_tree(nodes, values),
               main={"attribute": f"{sdd.main[0]}.{sdd.main[1]}", "value": values[(root.id, sdd.main[1])]})
    return out


def _annotated_tree(nodes, values):
    for n in nodes:
        n.attrs = {a: v for (i, a), v in values.items() if i == n.id}
    from functions.cfg_tree import tree_to_dict
    return tree_to_dict(nodes[0])


def with_circular_variant(defn):
    """Applies the preset's 'circularVariant' (rules that replace the originals) to demonstrate Step 6."""
    var = defn.get("circularVariant")
    if not var:
        raise SDDError("This SDD has no 'circularVariant'. Edit a rule yourself to make it circular.")
    d = dict(defn)
    d["rules"] = {**defn["rules"], **var}
    d["name"] = defn.get("name", "SDD") + " (circular variant)"
    return d
