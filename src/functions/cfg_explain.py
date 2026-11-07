"""Plain-language explanations of why a grammar fails the LL(1) test or the SLR(1) table (extra, for the oral defense).

Nothing here decides anything: the verdicts come from cfg_ll1 and cfg_slr1. This module only reads their results (the
violations of Section 4.4.3, the conflicts of Section 4.6.4) and tells the reader which sets and items caused them."""
from collections import deque

from functions.cfg_grammar import END, fmt_set, prod_str


def explain_ll1(g, ll):
    """One entry per violation of the LL(1) condition: where it happens and why, in words."""
    left_rec = set(g.left_recursive())
    out = []
    for v in ll.violations:
        A, (p, q) = v["nonterminal"], v["productions"]
        syms = " or ".join(repr(x) for x in v["symbols"])
        if v["condition"] == 1:
            text = (f"On the input symbol {syms}, the predictive parser cannot choose between {p} and {q}: both can begin "
                    f"with it, so the table cell M[{A}, {v['symbols'][0]}] would hold two productions.")
            if A in left_rec:
                text += (f" {A} is left-recursive ({A} derives a string that starts with {A}), so FIRST of that production "
                         f"always contains FIRST({A}); a top-down parser would also loop. Left recursion is the usual cause.")
            elif v["symbols"]:
                text += f" The productions start the same way: they need to be left-factored."
        elif v["condition"] == 2:
            text = (f"{p} and {q} can both derive the empty string, so when the parser sees a symbol of FOLLOW({A}) = "
                    f"{fmt_set(sorted(g.follow[A]))} it cannot tell which of the two should vanish.")
        else:
            text = (f"One of {p} and {q} derives the empty string, so it is used when the next symbol is in FOLLOW({A}) = "
                    f"{fmt_set(sorted(g.follow[A]))}. The other one can also start with {syms}, which is in that set: "
                    f"on {syms} both are possible.")
        out.append({"nonterminal": A, "condition": v["condition"], "symbols": v["symbols"], "text": text})
    return out


def _prefix(slr, target):
    """Shortest string of grammar symbols that takes the LR(0) automaton from state 0 to `target` (what the stack holds)."""
    edges = {}
    for (s, X), t in slr.trans.items():
        edges.setdefault(s, []).append((X, t))
    seen, queue = {0: ""}, deque([0])
    while queue:
        s = queue.popleft()
        if s == target:
            return seen[s]
        for X, t in sorted(edges.get(s, [])):
            if t not in seen:
                seen[t] = seen[s] + X
                queue.append(t)
    return ""


def explain_slr1(g, slr):
    """One entry per conflicting ACTION cell: the competing items and the FOLLOW sets that put them in the same cell."""
    if slr.too_big:
        return []
    out = []
    for c in slr.conflicts:
        s, a = c["state"], c["symbol"]
        items = sorted(slr.states[s])
        shifts = [slr.item_str(p, d) for p, d in items if d < len(slr.aug[p][1]) and slr.aug[p][1][d] == a]
        reduces = [(p, slr.item_str(p, d)) for p, d in items
                   if p != 0 and d == len(slr.aug[p][1]) and a in g.follow[slr.aug[p][0]]]
        prefix = _prefix(slr, s)
        where = f"After the parser has read {prefix!r}" if prefix else "At the start"
        sym = "the end marker $" if a == END else repr(a)
        if c["type"] == "shift/reduce":
            r_p, r_item = reduces[0] if reduces else (None, "")
            head = slr.aug[r_p][0] if r_p is not None else "?"
            text = (f"{where} (state {s}), the next symbol is {sym}. The parser can shift it (item {shifts[0] if shifts else '?'}) "
                    f"or reduce by {prod_str(*slr.aug[r_p]) if r_p is not None else '?'}, because {sym} is in "
                    f"FOLLOW({head}) = {fmt_set(sorted(g.follow[head]))}. SLR(1) decides reductions from FOLLOW alone, "
                    f"without looking at the context, so it cannot choose.")
        else:
            names = " and ".join(prod_str(*slr.aug[p]) for p, _ in reduces)
            text = (f"{where} (state {s}), the next symbol is {sym}. Two different reductions are possible, {names}, "
                    f"because {sym} is in the FOLLOW set of both heads. The parser cannot tell which production ended here.")
        out.append({"state": s, "symbol": a, "type": c["type"], "prefix": prefix, "items": [slr.item_str(p, d) for p, d in items],
                    "text": text})
    return out
