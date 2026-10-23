"""
Pruebas de subset_construction contra la teoría de Kozen,
*Lecture 6: The Subset Construction*.

Cada caso referencia el ejemplo del PDF del que sale, para que quien
lea el test pueda volver a la lectura y verificar el resultado a mano.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from functions.subset_construction import (
    epsilon_closure,
    move,
    subset_construction,
    format_dfa_result,
    state_name,
)
from functions.simulate import simulate_dfa


def build_dfa(states, alphabet, initial, accepting, nfa_transitions):
    dfa_states, transitions, accepting_states = subset_construction(
        states, alphabet, initial, accepting, nfa_transitions
    )
    f_states, f_transitions, f_accepting = format_dfa_result(
        dfa_states, transitions, accepting_states
    )
    return f_states, f_transitions, f_accepting


def accepts(f_transitions, initial_name, f_accepting, input_string):
    _, accepted = simulate_dfa(f_transitions, initial_name, f_accepting, input_string)
    return accepted


# ---------------------------------------------------------------------------
# Ejemplo 6.5 del PDF (pág. 37): NFA con ε-transiciones.
#
#   s --ε--> t --ε--> u
#   p --ε--> t        q --ε--> u
#   s --b--> p   t --b--> q   u --b--> r
#
# "El conjunto de cadenas aceptadas por este autómata es {b, bb, bbb}."
# ---------------------------------------------------------------------------
EXAMPLE_6_5_TRANSITIONS = [
    {"from": "s", "symbol": None, "to": "t"},
    {"from": "t", "symbol": None, "to": "u"},
    {"from": "p", "symbol": None, "to": "t"},
    {"from": "q", "symbol": None, "to": "u"},
    {"from": "s", "symbol": "b", "to": "p"},
    {"from": "t", "symbol": "b", "to": "q"},
    {"from": "u", "symbol": "b", "to": "r"},
]
EXAMPLE_6_5_STATES = ["s", "t", "u", "p", "q", "r"]
EXAMPLE_6_5_ALPHABET = ["b"]
EXAMPLE_6_5_INITIAL = "s"
EXAMPLE_6_5_ACCEPTING = ["p", "q", "r"]


def test_example_6_5_epsilon_closure_of_start_state():
    # Δ̂({s}, ε) debe incluir a s, t y u (encadenando las dos ε-transiciones).
    closure = epsilon_closure({"s"}, EXAMPLE_6_5_TRANSITIONS)
    assert closure == {"s", "t", "u"}


def test_example_6_5_accepts_exactly_b_bb_bbb():
    f_states, f_transitions, f_accepting = build_dfa(
        EXAMPLE_6_5_STATES,
        EXAMPLE_6_5_ALPHABET,
        EXAMPLE_6_5_INITIAL,
        EXAMPLE_6_5_ACCEPTING,
        EXAMPLE_6_5_TRANSITIONS,
    )
    initial_name = state_name(frozenset(
        epsilon_closure({EXAMPLE_6_5_INITIAL}, EXAMPLE_6_5_TRANSITIONS)
    ))

    accepted_strings = {"b", "bb", "bbb"}
    rejected_strings = {"", "a", "bbbb", "bbbbb", "ba"}

    for s in accepted_strings:
        assert accepts(f_transitions, initial_name, f_accepting, s), f"'{s}' debería ser aceptada"

    for s in rejected_strings:
        assert not accepts(f_transitions, initial_name, f_accepting, s), f"'{s}' debería ser rechazada"


# ---------------------------------------------------------------------------
# δ_M debe ser TOTAL: para cada estado del DFA y cada símbolo del alfabeto
# debe existir una transición (posiblemente hacia el estado ∅ / "dead").
# ---------------------------------------------------------------------------
def test_dfa_transition_function_is_total():
    f_states, f_transitions, f_accepting = build_dfa(
        EXAMPLE_6_5_STATES,
        EXAMPLE_6_5_ALPHABET,
        EXAMPLE_6_5_INITIAL,
        EXAMPLE_6_5_ACCEPTING,
        EXAMPLE_6_5_TRANSITIONS,
    )
    defined = {(t["from"], t["symbol"]) for t in f_transitions}
    for s in f_states:
        for a in EXAMPLE_6_5_ALPHABET:
            assert (s, a) in defined, f"falta δ({s}, {a})"

    # El estado 'dead' (∅) debe ser absorbente: dead --b--> dead.
    assert {"from": "dead", "symbol": "b", "to": "dead"} in f_transitions


# ---------------------------------------------------------------------------
# S como CONJUNTO de estados iniciales (N = (Q, Σ, Δ, S, F)):
# un NFA con dos estados iniciales debe equivaler a la unión de sus
# autómatas (Lema 6.2: Δ̂ conmuta con la unión).
# ---------------------------------------------------------------------------
def test_multiple_initial_states_behaves_as_union():
    # Dos NFAs independientes: uno acepta "a", otro acepta "b".
    transitions = [
        {"from": "s1", "symbol": "a", "to": "f1"},
        {"from": "s2", "symbol": "b", "to": "f2"},
    ]
    states = ["s1", "f1", "s2", "f2"]
    alphabet = ["a", "b"]
    accepting = ["f1", "f2"]

    f_states, f_transitions, f_accepting = build_dfa(
        states, alphabet, ["s1", "s2"], accepting, transitions
    )
    initial_name = state_name(frozenset(
        epsilon_closure({"s1", "s2"}, transitions)
    ))

    assert accepts(f_transitions, initial_name, f_accepting, "a")
    assert accepts(f_transitions, initial_name, f_accepting, "b")
    assert not accepts(f_transitions, initial_name, f_accepting, "c")


# ---------------------------------------------------------------------------
# Caso ya cubierto por test_manual.py: NFA sin ε desde un solo estado inicial.
# ---------------------------------------------------------------------------
def test_manual_example_regression():
    nfa_transitions = [
        {"from": 0, "symbol": None, "to": 1},
        {"from": 0, "symbol": None, "to": 3},
        {"from": 3, "symbol": None, "to": 7},
        {"from": 1, "symbol": "a", "to": 2},
        {"from": 3, "symbol": "a", "to": 4},
        {"from": 7, "symbol": "a", "to": 7},
        {"from": 0, "symbol": "b", "to": 8},
        {"from": 4, "symbol": "b", "to": 5},
        {"from": 7, "symbol": "b", "to": 8},
        {"from": 5, "symbol": "b", "to": 6},
        {"from": 8, "symbol": "b", "to": 8},
    ]
    states = [0, 1, 2, 3, 4, 5, 6, 7, 8]
    alphabet = ["a", "b"]
    accepting = [4, 8]

    f_states, f_transitions, f_accepting = build_dfa(
        states, alphabet, 0, accepting, nfa_transitions
    )
    initial_name = state_name(frozenset(epsilon_closure({0}, nfa_transitions)))

    assert accepts(f_transitions, initial_name, f_accepting, "ab")
    assert accepts(f_transitions, initial_name, f_accepting, "b")
    assert not accepts(f_transitions, initial_name, f_accepting, "aa")
