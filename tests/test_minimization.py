"""
Pruebas de la minimización (capa Functions) contra la teoría de Kozen,
*Lecture 14: A Minimization Algorithm* y *Lecture 13: Myhill-Nerode / cociente M/≈*.

Además del ejemplo del enunciado, se comparan los resultados con una
evaluación por fuerza bruta de la DEFINICIÓN de estados equivalentes sobre
cientos de AFD aleatorios.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import itertools
import random

import pytest

from functions.dfa import DFA, DFAError
from functions.dfa_parser import DFAParseError, dfa_from_json, parse_cases
from functions.minimization import compare, mark_pairs, minimize
from functions.minimization_format import format_output, marking_table_text

EXAMPLE = """1
6
a b
1 4 5
0 1 2
1 3 4
2 4 3
3 5 5
4 5 5
5 5 5
"""


# ----------------------------------------------------------------- helpers
def words(sigma, max_len):
    for length in range(max_len + 1):
        yield from ("".join(w) for w in itertools.product(sigma, repeat=length))


def brute_force_equivalent(dfa: DFA, p: int, q: int) -> bool:
    """Definition from the statement: p ~ q iff for all x, delta^(p,x) in F <=> delta^(q,x) in F.
    Strings of length <= |Q| are enough (Lecture 13: the refinement stabilises before that)."""
    return all((dfa.run(p, x) in dfa.finals) == (dfa.run(q, x) in dfa.finals)
               for x in words(dfa.alphabet, len(dfa.states)))


def random_accessible_dfa(rng: random.Random, n: int, sigma: str) -> DFA:
    # A spanning path 0 -> 1 -> ... -> n-1 guarantees every state is accessible.
    delta = {q: {a: rng.randrange(n) for a in sigma} for q in range(n)}
    for q in range(1, n):
        delta[q - 1][rng.choice(sigma)] = q
    finals = {q for q in range(n) if rng.random() < 0.4}
    return DFA.build(range(n), sigma, delta, 0, finals)


def chain(n: int) -> DFA:
    """Worst case for the number of rounds: rounds 0, 1, ..., |Q| - 2 all mark something."""
    return DFA.build(range(n), "ab", {i: {"a": min(i + 1, n - 1), "b": 0} for i in range(n)}, 0, {n - 1})


# ------------------------------------------------------ statement example
def test_statement_example():
    result = minimize(parse_cases(EXAMPLE)[0])
    assert result.equivalent_pairs == [(4, 5)]
    assert format_output([result]) == "(4, 5)"
    assert len(result.minimized.states) == 5
    assert result.classes == [[0], [1], [2], [3], [4, 5]]


def test_same_table_with_other_final_states():
    # Misma tabla del enunciado pero con F = {1, 2, 5}: el caso clásico donde 1 ≈ 2 y 3 ≈ 4.
    # Verificable a mano: {1,2} y {3,4} nunca llevan a un par marcado.
    text = EXAMPLE.replace("1 4 5\n0 1 2", "1 2 5\n0 1 2")
    r = minimize(parse_cases(text)[0])
    assert format_output([r]) == "(1, 2) (3, 4)"
    assert r.classes == [[0], [1, 2], [3, 4], [5]]
    assert r.marking.marks[(0, 3)].round == 2 and r.marking.witness((0, 3)) == "aa"


def test_rounds_match_hand_computation():
    m = minimize(parse_cases(EXAMPLE)[0]).marking
    assert [len(r) for r in m.rounds] == [9, 4, 1]
    assert m.marks[(0, 3)].round == 1 and m.marks[(0, 2)].round == 2
    assert m.marks[(0, 2)].symbol == "a" and m.marks[(0, 2)].via == (1, 4)
    assert m.witness((0, 2)) == "aa" and m.witness((0, 1)) == ""


def test_marking_table_text():
    table = marking_table_text(minimize(parse_cases(EXAMPLE)[0]))
    assert table.splitlines()[-3].split("|")[1].split() == ["X0", "X1", "X0", "X0", "="]


# -------------------------------------------------------------- edge cases
def test_multiple_cases_and_lexicographic_order():
    text = "2\n4\na\n2 3\n0 1\n1 2\n2 3\n3 3\n3\na b\n\n0 1 2\n1 2 0\n2 0 1\n"
    results = [minimize(d) for d in parse_cases(text)]
    # Case 1: 2 ~ 3 (both final, absorbing). Case 2: no final states -> all equivalent.
    assert format_output(results) == "(2, 3)\n(0, 1) (0, 2) (1, 2)"
    assert len(results[1].minimized.states) == 1


def test_numeric_not_string_order():
    # 12 states: pairs must be ordered 2 < 10 numerically, as in "(2, 10)".
    n = 12
    delta = {q: {"a": q} for q in range(n)}
    delta[0]["a"] = 1
    for q in range(1, n - 1):
        delta[q]["a"] = q + 1
    dfa = DFA.build(range(n), "a", delta, 0, {2, 10})
    r = minimize(dfa)
    assert r.equivalent_pairs == sorted(r.equivalent_pairs)


def test_already_minimal_gives_empty_line():
    r = minimize(parse_cases("1\n2\na\n1\n0 1\n1 0\n")[0])
    assert r.equivalent_pairs == [] and r.is_minimal and format_output([r]) == ""


def test_single_state():
    r = minimize(parse_cases("1\n1\na b\n0\n0 0 0\n")[0])
    assert r.equivalent_pairs == [] and len(r.minimized.states) == 1


def test_inaccessible_states_are_removed():
    r = minimize(parse_cases("1\n3\na\n1\n0 1\n1 1\n2 0\n")[0])
    assert r.removed_inaccessible == [2] and not r.is_minimal


def test_chain_reaches_the_n_minus_2_bound():
    # Pair {0, 1} is only told apart by a^(n-2): the longest possible shortest witness (Lecture 13/14).
    r = minimize(chain(40))
    assert r.equivalent_pairs == [] and len(r.marking.rounds) == 39
    assert r.marking.witness((0, 1)) == "a" * 38


@pytest.mark.parametrize("bad, msg, line", [
    ("0\n", "greater than 0", 1),
    ("1\n2\na\n1\n0 1\n", "end of input", None),
    ("1\n1\na\n0\n0 7\n", "not a state", 5),
    ("1\n1\nA\n0\n0 0\n", "lowercase", 3),
    ("1\n1\na\n0\n0 0 0\n", "needs 2 values", 5),
    ("1\n2\na\n1\n1 0\n2 1\n", "no row for state 0", None),
    ("1\n2\na\n5\n0 1\n1 0\n", "Final state 5", 4),
    ("1\n2\na\n1\n0 1\n0 0\n", "Duplicate row", 6),
    ("1\n1\na\n0\n0 0\nextra\n", "Extra content", 6),
])
def test_invalid_text_inputs(bad, msg, line):
    with pytest.raises(DFAParseError, match=msg) as err:
        parse_cases(bad)
    assert err.value.line == line


def test_max_states_limit():
    with pytest.raises(DFAParseError, match="at most 3"):
        parse_cases("1\n4\na\n\n0 1\n1 2\n2 3\n3 3\n", max_states=3)


# ------------------------------------------------------------------- JSON
def test_json_named_states_like_convert_output():
    dfa = dfa_from_json({
        "dfaStates": ["0137", "247", "58", "8"],
        "alphabet": ["a", "b"],
        "acceptingStates": ["247", "58", "8"],
        "transitions": [{"from": "0137", "symbol": "a", "to": "247"}, {"from": "0137", "symbol": "b", "to": "8"},
                        {"from": "247", "symbol": "a", "to": "247"}, {"from": "247", "symbol": "b", "to": "58"},
                        {"from": "58", "symbol": "a", "to": "58"}, {"from": "58", "symbol": "b", "to": "8"},
                        {"from": "8", "symbol": "a", "to": "8"}, {"from": "8", "symbol": "b", "to": "8"}],
    })
    assert dfa.name(dfa.start) == "0137"          # first listed state is the initial one
    r = minimize(dfa)
    assert format_output([r]) == "(247, 58) (247, 8) (58, 8)"


def test_json_subset_lists_as_states():
    dfa = dfa_from_json({"states": [[0, 1], [2]], "alphabet": ["a"], "accepting": [[2]],
                         "transitions": [{"from": [1, 0], "symbol": "a", "to": [2]},
                                         {"from": [2], "symbol": "a", "to": [2]}]})
    assert dfa.name(dfa.start) == "{0,1}" and [dfa.name(q) for q in dfa.finals] == ["{2}"]


@pytest.mark.parametrize("obj, msg", [
    ({"states": 2, "alphabet": [1, 2], "accepting": [], "transitions": [[1, 0], [0, 1]]}, "Invalid symbol"),
    ({"states": 2, "alphabet": ["a"], "accepting": [], "transitions": {"0": 5}}, "must be an object"),
    ({"states": 2, "alphabet": ["a"], "accepting": [], "transitions": [[1]]}, "one row per state"),
    ({"states": 2, "alphabet": ["a"], "accepting": [], "transitions": [[1], [[0, 1]]]}, "exactly one state"),
    ({"states": 2, "alphabet": ["a"], "accepting": [7], "transitions": [[1], [0]]}, "unknown state"),
    ({"states": 2, "alphabet": ["a", "b"], "accepting": [], "transitions": [[1, 0], [0]]}, "targets"),
    ({"states": [1, 2], "alphabet": ["a"], "accepting": [], "transitions": [[1], [2]]}, "Missing 'initial'"),
    ({"states": 2, "alphabet": ["a"], "transitions": [{"from": 0, "symbol": "a", "to": 1}]}, "Missing transition"),
    ({"states": 2, "alphabet": ["a"], "transitions": [{"from": 0, "symbol": "a", "to": 1},
                                                      {"from": 0, "symbol": "a", "to": 0}]}, "Nondeterminism"),
])
def test_invalid_json_inputs(obj, msg):
    with pytest.raises(DFAParseError, match=msg):
        dfa_from_json(obj)


# ------------------------------------------------------ randomised checks
@pytest.mark.parametrize("seed", range(200))
def test_random_dfas_against_definition(seed):
    rng = random.Random(seed)
    dfa = random_accessible_dfa(rng, rng.randint(1, 7), "ab" if seed % 3 else "abc")
    result = minimize(dfa)
    marking = result.marking

    # 1. Unmarked pairs are exactly the equivalent pairs of the definition.
    expected = [(p, q) for p, q in itertools.combinations(dfa.states, 2) if brute_force_equivalent(dfa, p, q)]
    assert result.equivalent_pairs == expected

    # 2. Every witness distinguishes its pair and is a shortest one (length = round).
    for pair, m in marking.marks.items():
        x = marking.witness(pair)
        assert (dfa.run(pair[0], x) in dfa.finals) != (dfa.run(pair[1], x) in dfa.finals)
        assert len(x) == m.round
        assert all((dfa.run(pair[0], y) in dfa.finals) == (dfa.run(pair[1], y) in dfa.finals)
                   for y in words(dfa.alphabet, m.round - 1)) if m.round else True

    # 3. The minimized DFA accepts the same language and is itself minimal.
    assert all(dfa.accepts(x) == result.minimized.accepts(x) for x in words(dfa.alphabet, 6))
    assert mark_pairs(result.minimized).unmarked == []
    assert compare(dfa, result.minimized).equivalent


@pytest.mark.parametrize("seed", range(150))
def test_compare_against_brute_force(seed):
    rng = random.Random(1000 + seed)
    a = random_accessible_dfa(rng, rng.randint(1, 5), "ab")
    b = random_accessible_dfa(rng, rng.randint(1, 5), "ab")
    res = compare(a, b)
    diffs = [x for x in words("ab", 10) if a.accepts(x) != b.accepts(x)]
    assert res.equivalent == (not diffs)
    if diffs:
        assert len(res.counterexample) == len(diffs[0])          # shortest
        assert a.accepts(res.counterexample) != b.accepts(res.counterexample)
        assert (res.accepted_by == "first") == a.accepts(res.counterexample)


def test_compare_needs_same_alphabet():
    with pytest.raises(DFAError, match="same alphabet"):
        compare(DFA.build([0], "a", {0: {"a": 0}}, 0, []), DFA.build([0], "b", {0: {"b": 0}}, 0, []))
