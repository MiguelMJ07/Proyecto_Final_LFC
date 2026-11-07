"""Practice mode: random exercises on grammars to work out by hand before the oral defense.
An exercise is a pure function of (kind, seed, difficulty): the server stores nothing, it regenerates the same
grammar when the answer arrives. The answers are computed with the same algorithms the rest of the server uses."""
import random
import re

from functions.cfg_grammar import EPS, END, GrammarError, is_nt, parse_grammar, prod_str, sets_lines
from functions.cfg_ll1 import LL1
from functions.cfg_slr1 import SLR1

KINDS = {
    "sets": "FIRST and FOLLOW",
    "ll1_table": "LL(1) decision and predictive table",
    "derivation": "Leftmost derivation by the LL(1) parser",
    "lr0": "LR(0) closure, number of states and SLR(1)",
}
FALLBACK = "3\nS -> AB\nA -> aA d\nB -> bBc e"        # grammar of the assignment's Example 2
MAX_PRODS = {1: 6, 2: 9, 3: 12}


def _rng(kind, seed, difficulty):
    return random.Random(f"{kind}:{seed}:{difficulty}")


def _random_grammar_text(rng, difficulty):
    nts = "SABC"[: {1: 2, 2: 3, 3: 4}[difficulty]]
    terms = "abc"[: 2 if difficulty == 1 else 3]
    lines = []
    for A in nts:
        alts, seen = [], set()
        for _ in range(rng.choice((2, 2, 3))):
            n = rng.choice((0, 1, 1, 2, 2, 3))
            pool = list(terms) * 3 + list(nts)
            alt = "".join(rng.choice(pool) for _ in range(n)) or EPS
            if alt not in seen:
                seen.add(alt)
                alts.append(alt)
        lines.append(f"{A} -> {' '.join(alts)}")
    return f"{len(nts)}\n" + "\n".join(lines)


def _acceptable(g, difficulty):
    """Every nonterminal productive and reachable (the assignment's assumptions), and small enough for paper."""
    if len(g.prods) > MAX_PRODS[difficulty]:
        return False
    prod, changed = set(), True
    while changed:
        changed = False
        for h, b in g.prods:
            if h not in prod and all(not is_nt(x) or x in prod for x in b):
                prod.add(h)
                changed = True
    reach, stack = {g.start}, [g.start]
    while stack:
        A = stack.pop()
        for h, b in g.prods:
            if h == A:
                for x in b:
                    if is_nt(x) and x not in reach:
                        reach.add(x)
                        stack.append(x)
    return prod == set(g.nonterminals) == reach


def _grammar_for(kind, rng, difficulty):
    for _ in range(4000):
        text = _random_grammar_text(rng, difficulty)
        try:
            g = parse_grammar(text)
        except GrammarError:
            continue
        if not _acceptable(g, difficulty):
            continue
        if kind == "sets" and not any(not b for _, b in g.prods):
            continue                                         # include at least one epsilon production
        if kind == "derivation" and not LL1(g).is_ll1:
            continue
        if kind == "lr0" and not 4 <= len(SLR1(g).states) <= 14:
            continue
        if kind == "ll1_table" and len(g.prods) < 4:
            continue
        return text, g
    return FALLBACK, parse_grammar(FALLBACK)


def _random_member(rng, g):
    for _ in range(200):
        form, steps = [g.start], 0
        while any(is_nt(x) for x in form) and steps < 40:
            k = next(i for i, x in enumerate(form) if is_nt(x))
            _, body = rng.choice([p for p in g.prods if p[0] == form[k]])
            form[k:k + 1] = list(body)
            steps += 1
        if not any(is_nt(x) for x in form) and 1 <= len(form) <= 8:
            return "".join(form)
    return g.terminals[0]


def new_exercise(kind, seed, difficulty):
    rng = _rng(kind, seed, difficulty)
    text, g = _grammar_for(kind, rng, difficulty)
    ex = {"kind": kind, "title": KINDS[kind], "seed": seed, "difficulty": difficulty, "grammar": text,
          "productions": g.productions_json(), "nonterminals": g.nonterminals, "terminals": g.terminals}
    if kind == "ll1_table":
        ex["columns"] = g.terminals + [END]
    if kind == "derivation":
        w = _random_member(rng, g)
        if rng.random() < 0.35 and len(w) > 0:               # sometimes make it (probably) not a member
            i = rng.randrange(len(w))
            w = w[:i] + rng.choice(g.terminals) + w[i + 1:] if rng.random() < 0.5 else w[:i] + w[i + 1:]
        ex["input"] = w or g.terminals[0]
    return ex


# ------------------------------------------------------------------- checking
def _tokens(text):
    if isinstance(text, list):
        text = " ".join(map(str, text))
    return {("e" if t == "ε" else t) for t in re.findall(r"[^\s,{}]+", str(text or ""))}


def _item(label, ok, message=""):
    return {"label": label, "ok": ok, "message": message}


def _fmt(s):
    out = sorted(x for x in s if x not in (EPS, END)) + ([EPS] if EPS in s else []) + ([END] if END in s else [])
    return "{" + ", ".join(out) + "}"


def _diff(yours, expected):
    miss, extra = sorted(expected - yours), sorted(yours - expected)
    parts = []
    if miss:
        parts.append("missing " + ", ".join(miss))
    if extra:
        parts.append("should not contain " + ", ".join(extra))
    return "; ".join(parts)


def check(kind, seed, difficulty, answer):
    ex = new_exercise(kind, seed, difficulty)
    g = parse_grammar(ex["grammar"])
    items, solution = [], {}
    if kind == "sets":
        first, follow = answer.get("first", {}), answer.get("follow", {})
        for name, mine, truth in (("First", first, g.first), ("Follow", follow, g.follow)):
            for A in g.nonterminals:
                y = _tokens(mine.get(A, ""))
                ok = y == truth[A]
                items.append(_item(f"{name}({A})", ok, "" if ok else _diff(y, truth[A])))
        solution = {"lines": sets_lines(g)}
    elif kind == "ll1_table":
        ll = LL1(g)
        cells = answer.get("cells", {})
        items.append(_item("Is the grammar LL(1)?", answer.get("isLL1") is ll.is_ll1,
                           "" if answer.get("isLL1") is ll.is_ll1 else f"it {'is' if ll.is_ll1 else 'is not'} LL(1)"))
        for A in g.nonterminals:
            for a in g.terminals + [END]:
                exp = set(ll.table.get((A, a), []))
                try:
                    mine = {int(t) for t in re.findall(r"\d+", str(cells.get(f"{A},{a}", "")))}
                except ValueError:
                    mine = set()
                if exp or mine:
                    ok = mine == exp
                    msg = "" if ok else ("this entry is an error (blank)" if not exp else
                                         "expected " + ", ".join(f"{i} ({prod_str(*g.prods[i])})" for i in sorted(exp)))
                    items.append(_item(f"M[{A},{a}]", ok, msg))
        solution = {"isLL1": ll.is_ll1, "lines": ll.table_lines(),
                    "violations": [v["message"] for v in ll.violations]}
    elif kind == "derivation":
        ll = LL1(g)
        r = ll.parse(ex["input"], trace=True)
        exp = [s["production"] for s in r["trace"] if "production" in s]
        mine = [int(x) for x in re.findall(r"\d+", " ".join(map(str, answer.get("productions", []))))] \
            if not isinstance(answer.get("productions"), str) else [int(x) for x in re.findall(r"\d+", answer["productions"])]
        if mine == exp:
            items.append(_item("Productions output, in order", True))
        else:
            k = next((i for i in range(min(len(mine), len(exp))) if mine[i] != exp[i]), min(len(mine), len(exp)))
            msg = (f"step {k + 1}: you wrote {mine[k]}, the parser outputs {exp[k]}" if k < min(len(mine), len(exp))
                   else (f"you stopped after {len(mine)} productions; the parser outputs {len(exp)}" if len(mine) < len(exp)
                         else f"the parser stops after {len(exp)} productions; you wrote {len(mine)}"))
            items.append(_item("Productions output, in order", False, msg))
        want = "yes" if r["accepted"] else "no"
        items.append(_item("Is the string accepted?", str(answer.get("result", "")).lower() == want,
                           "" if str(answer.get("result", "")).lower() == want else f"the answer is {want}"))
        solution = {"productions": exp, "result": want,
                    "steps": [f"{' '.join(s['stack']) or '-'} | {s['input']} | {s['action']}" for s in r["trace"]]}
    elif kind == "lr0":
        slr = SLR1(g)
        norm = lambda t: re.sub(r"\s+", "", str(t)).replace("→", "->")
        fix = lambda t: re.sub(r"->\.e$", "->.", t)
        truth = {norm(slr.item_str(p, d)) for p, d in slr.states[0]}
        raw = answer.get("closure", "")
        mine = {fix(norm(t)) for t in (re.split(r"[\n;]+", raw) if isinstance(raw, str) else raw) if norm(t)}
        items.append(_item("CLOSURE({S' -> .S})", mine == truth, "" if mine == truth else _diff(mine, truth)))
        try:
            n_ok = int(answer.get("numStates")) == len(slr.states)
        except (TypeError, ValueError):
            n_ok = False
        items.append(_item("Number of LR(0) states", n_ok, "" if n_ok else f"there are {len(slr.states)}"))
        items.append(_item("Is the grammar SLR(1)?", answer.get("isSLR1") is slr.is_slr1,
                           "" if answer.get("isSLR1") is slr.is_slr1 else f"it {'is' if slr.is_slr1 else 'is not'} SLR(1)"))
        solution = {"closure": sorted(truth), "numStates": len(slr.states), "isSLR1": slr.is_slr1,
                    "conflicts": [f"state {c['state']} on {c['symbol']}: {c['type']}" for c in slr.conflicts],
                    "states": [f"I{s['id']}: " + " | ".join(s["items"]) for s in slr.automaton_json()["states"]]}
    correct = sum(1 for i in items if i["ok"])
    return {"kind": kind, "seed": seed, "score": {"correct": correct, "total": len(items)}, "items": items, "solution": solution}
