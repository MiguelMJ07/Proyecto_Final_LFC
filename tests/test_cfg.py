"""Items 1-2: FIRST/FOLLOW, LL(1) (4.4.3, Alg. 4.31, Alg. 4.34) and SLR(1). Includes a property test:
both parsers must agree with a brute-force enumeration of the language of random grammars."""
import itertools
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from functions.cfg_grammar import GrammarError, parse_grammar, sets_lines
from functions.cfg_ll1 import LL1
from functions.cfg_slr1 import SLR1

EX1 = "3\nS -> S+T T\nT -> T*F F\nF -> (S) i"
EX2 = "3\nS -> AB\nA -> aA d\nB -> bBc e"
EX3 = "1\nS -> SS a"


def parsers(text):
    g = parse_grammar(text)
    return g, LL1(g), SLR1(g)


def test_sets_example1():
    g = parse_grammar(EX1)
    assert sets_lines(g) == ["First(F) = {(, i}", "First(S) = {(, i}", "First(T) = {(, i}",
                             "Follow(F) = {), *, +, $}", "Follow(S) = {), +, $}", "Follow(T) = {), *, +, $}"]


def test_sets_example2_with_epsilon():
    g = parse_grammar(EX2)
    assert sets_lines(g) == ["First(A) = {a, d}", "First(B) = {b, e}", "First(S) = {a, d}",
                             "Follow(A) = {b, $}", "Follow(B) = {c, $}", "Follow(S) = {$}"]


def test_sets_book_grammar_4_28():
    # Example 4.30 of the book (non-left-recursive expression grammar), written with single letters:
    # E -> TX, X -> +TX | e, T -> FY, Y -> *FY | e, F -> (E) | i      (E is the start symbol; here named S)
    g = parse_grammar("5\nS -> TX\nX -> +TX e\nT -> FY\nY -> *FY e\nF -> (S) i")
    assert g.first["S"] == g.first["T"] == g.first["F"] == {"(", "i"}
    assert g.first["X"] == {"+", "e"} and g.first["Y"] == {"*", "e"}
    assert g.follow["S"] == g.follow["X"] == {")", "$"}
    assert g.follow["T"] == g.follow["Y"] == {"+", ")", "$"}
    assert g.follow["F"] == {"*", "+", ")", "$"}
    ll = LL1(g)
    assert ll.is_ll1 and not ll.violations and not ll.conflicts


def test_decisions_of_the_assignment_examples():
    _, ll, slr = parsers(EX1)
    assert not ll.is_ll1 and slr.is_slr1
    _, ll, slr = parsers(EX2)
    assert ll.is_ll1 and slr.is_slr1
    _, ll, slr = parsers(EX3)
    assert not ll.is_ll1 and not slr.is_slr1


def test_assignment_example_answers():
    _, ll, slr = parsers(EX1)
    assert [slr.parse(w)["accepted"] for w in ("i+i", "(i)", "(i+i)*i)")] == [True, True, False]
    _, ll, slr = parsers(EX2)
    for p in (ll, slr):
        assert [p.parse(w)["accepted"] for w in ("d", "adbc", "a")] == [True, True, False]


def test_empty_string_and_epsilon_productions():
    _, ll, slr = parsers("2\nS -> aSb A\nA -> e")
    for p in (ll, slr):
        assert p.parse("")["accepted"] and p.parse("aabb")["accepted"] and not p.parse("aab")["accepted"]


def test_ll1_condition_reports_which_condition_fails():
    g = parse_grammar("3\nS -> aA aB\nA -> b\nB -> c")
    ll = LL1(g)
    assert not ll.is_ll1 and ll.violations[0]["condition"] == 1 and ll.violations[0]["symbols"] == ["a"]
    g = parse_grammar("1\nS -> e a")           # derives the empty string and a: LL(1)
    assert LL1(g).is_ll1
    g = parse_grammar("2\nS -> A e\nA -> e")   # S -> A | e: both derive epsilon -> condition 2
    ll = LL1(g)
    assert not ll.is_ll1 and 2 in {v["condition"] for v in ll.violations}
    g = parse_grammar("2\nS -> Aa\nA -> a e")  # A -> a | e with a in FOLLOW(A): condition 3
    ll = LL1(g)
    assert not ll.is_ll1 and 3 in {v["condition"] for v in ll.violations}


def test_left_recursion_is_detected_and_never_ll1():
    g = parse_grammar(EX1)
    assert g.left_recursive() == ["S", "T"]
    assert not LL1(g).is_ll1


def test_slr_conflict_is_reported_not_hidden():
    _, _, slr = parsers(EX3)
    assert not slr.is_slr1 and slr.conflicts and slr.conflicts[0]["type"] == "shift/reduce"


def test_ll1_error_positions():
    _, ll, _ = parsers(EX2)
    r = ll.parse("ab")
    assert not r["accepted"] and r["error"]["position"] >= 1


@pytest.mark.parametrize("bad", ["", "x", "0\nS -> a", "1\nS -> a\nS -> b", "1\ns -> a", "1\nS -> aA", "2\nS -> a", "1\nS -> a$",
                                 "1\nS -> ae", "1\nA -> a"])
def test_invalid_grammars_raise(bad):
    with pytest.raises(GrammarError):
        parse_grammar(bad)


# ------------------------------------------------------------------ property test
def language_upto(g, maxlen):
    """Reference semantics: all terminal strings of length <= maxlen, as the least fixed point of
    L(A) = union of L(X1) L(X2) ... L(Xn) over the productions of A (strings longer than maxlen are dropped)."""
    from functions.cfg_grammar import is_nt
    L = {A: set() for A in g.nonterminals}
    changed = True
    while changed:
        changed = False
        for A, body in g.prods:
            acc = {""}
            for X in body:
                part = L[X] if is_nt(X) else {X}
                acc = {u + v for u in acc for v in part if len(u) + len(v) <= maxlen}
                if not acc:
                    break
            if not acc <= L[A]:
                L[A] |= acc
                changed = True
    return L[g.start]


def random_grammar(rng):
    nts = "SAB"[: rng.randint(1, 3)]
    syms = list("ab") + list(nts)
    lines = []
    for A in nts:
        alts = []
        for _ in range(rng.randint(1, 3)):
            n = rng.randint(0, 3)
            alts.append("".join(rng.choice(syms) for _ in range(n)) or "e")
        lines.append(f"{A} -> {' '.join(alts)}")
    return f"{len(nts)}\n" + "\n".join(lines)


def productive(g):
    from functions.cfg_grammar import is_nt
    prod = set()
    changed = True
    while changed:
        changed = False
        for h, b in g.prods:
            if h not in prod and all((not is_nt(x)) or x in prod for x in b):
                prod.add(h)
                changed = True
    return prod


def test_parsers_agree_with_brute_force_language():
    rng = random.Random(2026)
    checked = both = 0
    for _ in range(400):
        text = random_grammar(rng)
        try:
            g = parse_grammar(text)
        except GrammarError:
            continue
        if productive(g) != set(g.nonterminals):
            continue                                  # the assignment guarantees every nonterminal is productive
        ll, slr = LL1(g), SLR1(g)
        if not (ll.is_ll1 or slr.is_slr1):
            continue
        checked += 1
        lang = language_upto(g, 4)
        for n in range(0, 5):
            for w in map("".join, itertools.product("ab", repeat=n)):
                for p, ok in ((ll, ll.is_ll1), (slr, slr.is_slr1)):
                    if ok:
                        assert p.parse(w)["accepted"] == (w in lang), (text, w, type(p).__name__)
        both += ll.is_ll1 and slr.is_slr1
    assert checked > 60 and both > 5


def test_ll1_conditions_match_table_conflicts_on_reachable_grammars():
    rng = random.Random(7)
    n = 0
    for _ in range(500):
        try:
            g = parse_grammar(random_grammar(rng))
        except GrammarError:
            continue
        if productive(g) != set(g.nonterminals) or any(not g.follow[A] for A in g.nonterminals):
            continue                                  # FOLLOW(A) = {} means A is unreachable; the book assumes reachable
        ll = LL1(g)
        assert ll.is_ll1 == (not ll.conflicts), random_grammar
        n += 1
    assert n > 100


def test_kozen_lecture_21_grammars():
    """Grammars (21.1) and (21.2) of Kozen's Lecture 21 (nonnull balanced brackets)."""
    _, ll, slr = parsers("2\nS -> [B [SB [BS [SBS\nB -> ]")          # (21.2) Greibach normal form
    assert not ll.is_ll1 and slr.is_slr1                                # common prefix '[' breaks condition 1
    for w, ok in (("[]", True), ("[[]]", True), ("[][]", True), ("[[][]]", True), ("[[]", False), ("][", False), ("", False)):
        assert slr.parse(w)["accepted"] is ok, w
    _, ll, slr = parsers("4\nS -> AB AC SS\nC -> SB\nA -> [\nB -> ]")  # (21.1) Chomsky normal form: ambiguous, S -> SS
    assert not ll.is_ll1 and not slr.is_slr1
