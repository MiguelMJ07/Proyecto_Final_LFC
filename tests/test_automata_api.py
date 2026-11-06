"""
Errores de entrada de /convert y /simulate (Asignación 1): siempre HTTP 400 con
un mensaje que dice qué campo está mal y cómo debe ser, nunca un error de Python.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from app import app
from gateways.automata_gateway import MAX_DFA_STATES

NFA = {"states": [0, 1], "alphabet": ["a"], "initial": 0, "accepting": [1],
       "transitions": [{"from": 0, "symbol": "a", "to": 1}]}
DFA = {"transitions": [{"from": "p", "symbol": "a", "to": "q"}], "initial": "p", "accepting": ["q"], "input": "a"}


@pytest.fixture()
def client():
    return app.test_client()


@pytest.mark.parametrize("change,message", [
    ({"states": 5}, "Field 'states' must be a list of states"),
    ({"states": [[0]]}, "Invalid state [0] in 'states'"),
    ({"states": []}, "at least one state"),
    ({"states": [0, 1, 1]}, "Repeated states in 'states': 1"),
    ({"alphabet": "ab"}, "Field 'alphabet' must be a list of symbols"),
    ({"alphabet": [None]}, "Field 'alphabet' must be a list of symbols"),
    ({"alphabet": ["a", "a"]}, "Repeated symbols"),
    ({"initial": True}, "Invalid state true in 'initial'"),
    ({"initial": []}, "non-empty list of states"),
    ({"initial": 99}, "Initial state(s) [99] are not in 'states'"),
    ({"accepting": 7}, "Field 'accepting' must be a list of states"),
    ({"accepting": [5]}, "Accepting state(s) [5] are not in 'states'"),
    ({"transitions": {}}, "Field 'transitions' must be a list"),
    ({"transitions": [1]}, "Transition 1 must be an object"),
    ({"transitions": [{"from": 0, "symbol": "a"}]}, "fields 'from', 'symbol' and 'to'"),
    ({"transitions": [{"from": 0, "symbol": ["a"], "to": 1}]}, "'symbol' must be a string"),
    ({"transitions": [{"from": 0, "symbol": "b", "to": 1}]}, "not in 'alphabet'"),
    ({"transitions": [{"from": 0, "symbol": "a", "to": 9}]}, "uses a state that is not in 'states'"),
])
def test_convert_explains_what_is_wrong(client, change, message):
    r = client.post("/convert", json={**NFA, **change})
    assert r.status_code == 400 and message in r.get_json()["error"], r.get_json()


def test_convert_stops_before_the_dfa_explodes(client):
    # (a+b)*a(a+b)^(n-1): el DFA mínimo tiene 2^n estados.
    n = 14
    nfa = {"states": list(range(n + 1)), "alphabet": ["a", "b"], "initial": 0, "accepting": [n],
           "transitions": [{"from": 0, "symbol": s, "to": 0} for s in "ab"] + [{"from": 0, "symbol": "a", "to": 1}]
           + [{"from": i, "symbol": s, "to": i + 1} for i in range(1, n) for s in "ab"]}
    r = client.post("/convert", json=nfa)
    assert r.status_code == 400 and f"more than {MAX_DFA_STATES} states" in r.get_json()["error"]
    nfa["states"], nfa["accepting"] = list(range(5)), [4]          # con n = 4 sí cabe: 16 estados
    nfa["transitions"] = [t for t in nfa["transitions"] if t["to"] <= 4 and t["from"] < 4]
    assert len(client.post("/convert", json=nfa).get_json()["dfaStates"]) == 16


@pytest.mark.parametrize("change,message", [
    ({"input": 5}, "Field 'input' must be a string"),
    ({"input": "a" * 10001}, "longer than"),
    ({"transitions": "x"}, "Field 'transitions' must be a list"),
    ({"accepting": 5}, "Field 'accepting' must be a list of states"),
    ({"initial": None}, "Invalid state null in 'initial'"),
    ({"transitions": [{"from": "p", "symbol": "a", "to": "q"}, {"from": "p", "symbol": "a", "to": "p"}]},
     "not deterministic"),
])
def test_simulate_explains_what_is_wrong(client, change, message):
    r = client.post("/simulate", json={**DFA, **change})
    assert r.status_code == 400 and message in r.get_json()["error"], r.get_json()


def test_valid_requests_are_unchanged(client):
    assert client.post("/simulate", json=DFA).get_json() == {"path": ["p", "q"], "accepted": True}
    # Una transición repetida con el mismo destino no rompe el determinismo.
    same = {**DFA, "transitions": DFA["transitions"] * 2}
    assert client.post("/simulate", json=same).get_json()["accepted"] is True
    assert client.post("/convert", json=NFA).get_json()["acceptingStates"] == ["1"]
    assert client.post("/convert", json={**NFA, "initial": [0]}).status_code == 200
