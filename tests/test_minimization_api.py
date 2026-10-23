"""
Pruebas del endpoint de minimización (capas Controller + Gateway) y de su
integración con el servidor de la Asignación 1 (/convert y /simulate).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import itertools
import json
import random

import pytest

from app import app
from controllers.minimization_controller import COMPARE_EXAMPLE, EXAMPLE_INPUT
from gateways.minimization_gateway import MAX_STATES, MAX_STATES_WITH_STEPS

EXAMPLE_JSON = {
    "states": [0, 1, 2, 3, 4, 5],
    "alphabet": ["a", "b"],
    "initial": 0,
    "accepting": [1, 4, 5],
    "transitions": [
        {"from": 0, "symbol": "a", "to": 1}, {"from": 0, "symbol": "b", "to": 2},
        {"from": 1, "symbol": "a", "to": 3}, {"from": 1, "symbol": "b", "to": 4},
        {"from": 2, "symbol": "a", "to": 4}, {"from": 2, "symbol": "b", "to": 3},
        {"from": 3, "symbol": "a", "to": 5}, {"from": 3, "symbol": "b", "to": 5},
        {"from": 4, "symbol": "a", "to": 5}, {"from": 4, "symbol": "b", "to": 5},
        {"from": 5, "symbol": "a", "to": 5}, {"from": 5, "symbol": "b", "to": 5},
    ],
}


@pytest.fixture
def client():
    return app.test_client()


def text_post(client, url, body, **kw):
    return client.post(url, data=body, content_type="text/plain", **kw)


# ---------------------------------------------------------------- minimize
def test_text_in_text_out(client):
    r = text_post(client, "/minimize?format=text", EXAMPLE_INPUT)
    assert r.status_code == 200 and r.mimetype == "text/plain"
    assert r.get_data(as_text=True) == "(4, 5)\n"


def test_accept_header_text(client):
    r = text_post(client, "/minimize", EXAMPLE_INPUT, headers={"Accept": "text/plain"})
    assert r.get_data(as_text=True) == "(4, 5)\n"


def test_text_in_json_out(client):
    body = text_post(client, "/minimize", EXAMPLE_INPUT).get_json()
    assert body["output"] == "(4, 5)"
    case = body["cases"][0]
    assert case["equivalentPairs"] == [[4, 5]]
    assert case["equivalenceClasses"] == [[0], [1], [2], [3], [4, 5]]
    assert case["minimizedDfa"]["accepting"] == [1, 4] and case["minimizedDfa"]["initial"] == 0
    rounds = case["steps"]["rounds"]
    assert [r["round"] for r in rounds] == [0, 1, 2, 3] and rounds[-1]["marked"] == []
    assert rounds[2]["marked"][0] == {"pair": [0, 2], "round": 2, "symbol": "a", "via": [1, 4], "witness": "aa",
                                      "reason": rounds[2]["marked"][0]["reason"]}


def test_steps_can_be_disabled(client):
    case = text_post(client, "/minimize?steps=false", EXAMPLE_INPUT).get_json()["cases"][0]
    assert "steps" not in case and case["equivalentPairs"] == [[4, 5]]


def test_json_in_assignment1_style(client):
    assert client.post("/minimize", json=EXAMPLE_JSON).get_json()["output"] == "(4, 5)"


def test_convert_output_can_be_minimized(client):
    convert_like = {"dfaStates": ["0137", "247", "8"], "alphabet": ["a", "b"], "acceptingStates": ["247", "8"],
                    "transitions": [{"from": "0137", "symbol": "a", "to": "247"}, {"from": "0137", "symbol": "b", "to": "8"},
                                    {"from": "247", "symbol": "a", "to": "247"}, {"from": "247", "symbol": "b", "to": "8"},
                                    {"from": "8", "symbol": "a", "to": "8"}, {"from": "8", "symbol": "b", "to": "8"}]}
    case = client.post("/minimize", json=convert_like).get_json()["cases"][0]
    assert case["equivalentPairs"] == [["247", "8"]]
    assert case["minimizedDfa"]["stateLabels"] == {"0": "{0137}", "1": "{247,8}"}


def test_minimized_dfa_round_trips(client):
    case = client.post("/minimize", json=EXAMPLE_JSON).get_json()["cases"][0]
    again = client.post("/minimize", json=case["minimizedDfa"]).get_json()
    assert again["cases"][0]["isMinimal"] is True
    again = text_post(client, "/minimize", case["minimizedDfa"]["courseFormat"]).get_json()
    assert again["output"] == ""


def test_json_cases_and_raw_input(client):
    dfa = {"states": 2, "alphabet": ["a"], "accepting": [0, 1], "transitions": [[1], [0]]}
    assert client.post("/minimize", json={"cases": [dfa, dfa]}).get_json()["output"] == "(0, 1)\n(0, 1)"
    assert client.post("/minimize", json={"input": EXAMPLE_INPUT}).get_json()["output"] == "(4, 5)"


def test_large_dfa_limits(client):
    n = MAX_STATES_WITH_STEPS + 1
    big = f"1\n{n}\na\n{n - 1}\n" + "".join(f"{i} {min(i + 1, n - 1)}\n" for i in range(n))
    case = text_post(client, "/minimize", big).get_json()["cases"][0]
    assert "steps" not in case and "stepsOmitted" in case
    n = MAX_STATES + 1
    too_big = f"1\n{n}\na\n\n" + "".join(f"{i} 0\n" for i in range(n))
    assert text_post(client, "/minimize", too_big).status_code == 400


# ----------------------------------------------------------------- compare
def test_compare_equivalent(client):
    body = text_post(client, "/minimize/compare", COMPARE_EXAMPLE).get_json()
    assert body["equivalent"] is True


def test_compare_counterexample(client):
    other = dict(EXAMPLE_JSON, accepting=[1, 4])            # state 5 no longer accepting
    body = client.post("/minimize/compare", json={"cases": [EXAMPLE_JSON, other]}).get_json()
    assert body["equivalent"] is False and body["counterexample"] == "aaa" and body["acceptedBy"] == "first"


def test_compare_needs_two(client):
    assert text_post(client, "/minimize/compare", EXAMPLE_INPUT).status_code == 400


# ------------------------------------------------------------------ errors
def test_errors_are_400(client):
    r = text_post(client, "/minimize", "1\n2\na\n1\n0 1\n1 9\n")
    assert r.status_code == 400 and r.get_json() == {"error": "Line 6: delta(1, a) = 9 is not a state of Q.", "line": 6}
    assert text_post(client, "/minimize", "").status_code == 400
    assert client.post("/minimize", json=[1, 2]).status_code == 400
    assert client.post("/minimize", data="{bad json", content_type="application/json").status_code == 400
    assert text_post(client, "/minimize?format=xml", EXAMPLE_INPUT).status_code == 400
    assert text_post(client, "/minimize?steps=maybe", EXAMPLE_INPUT).status_code == 400


def _mutate(rng, value):
    """Randomly corrupt a JSON value."""
    junk = [None, True, -1, 0, 3.5, "", "x", "a", [], {}, [1], {"a": 1}, [[0, 1]], "0"]
    if isinstance(value, dict) and value and rng.random() < 0.7:
        k = rng.choice(list(value))
        out = dict(value)
        if rng.random() < 0.2:
            del out[k]
        else:
            out[k] = _mutate(rng, value[k])
        return out
    if isinstance(value, list) and value and rng.random() < 0.7:
        out = list(value)
        i = rng.randrange(len(out))
        out[i] = _mutate(rng, out[i])
        return out
    return rng.choice(junk)


@pytest.mark.parametrize("seed", range(300))
def test_malformed_json_never_causes_500(client, seed):
    rng = random.Random(seed)
    body = _mutate(rng, json.loads(json.dumps(EXAMPLE_JSON)))
    for url in ("/minimize", "/minimize/compare"):
        payload = {"cases": [body, EXAMPLE_JSON]} if url.endswith("compare") else body
        assert client.post(url, json=payload).status_code in (200, 400)


@pytest.mark.parametrize("seed", range(200))
def test_malformed_text_never_causes_500(client, seed):
    rng = random.Random(seed)
    chars = list(EXAMPLE_INPUT)
    for _ in range(rng.randint(1, 4)):
        i = rng.randrange(len(chars))
        chars[i] = rng.choice(["", " ", "\n", "x", "9", "-", "a", "0"])
    assert text_post(client, "/minimize", "".join(chars)).status_code in (200, 400)


# --------------------------------------------------------------- example/ui
def test_example_and_ui(client):
    assert client.get("/minimize/example").get_json()["expectedOutput"] == "(4, 5)"
    r = client.get("/minimize/ui")
    assert r.status_code == 200 and b'"/minimize"' in r.data and b'"/convert"' in r.data


# ---------------------------------------------------------------------------
# Integración con la Asignación 1: NFA --/convert--> AFD --/minimize--> AFD mínimo
# ---------------------------------------------------------------------------
ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_convert_output_goes_straight_into_minimize(client):
    # NFA del enunciado de la Asignación 1 (test_request.json).
    with open(os.path.join(ROOT, "test_request.json")) as f:
        nfa = json.load(f)
    dfa = client.post("/convert", json=nfa).get_json()
    assert "alphabet" not in dfa and "initial" not in dfa        # /convert no los devuelve: se deducen

    body = client.post("/minimize", json=dfa).get_json()
    case = body["cases"][0]
    # 8, 5-8 y 6-8 aceptan exactamente b* desde ellos: se colapsan en un solo estado.
    assert body["output"] == "(5-8, 6-8) (5-8, 8) (6-8, 8)"
    assert case["originalDfa"]["initial"] == "0-1-3-7"
    assert case["stats"]["statesOriginal"] == 7 and case["stats"]["statesMinimized"] == 5
    assert ["8", "5-8", "6-8"] in case["equivalenceClasses"]


def test_minimized_dfa_works_with_simulate(client):
    with open(os.path.join(ROOT, "test_request.json")) as f:
        nfa = json.load(f)
    dfa = client.post("/convert", json=nfa).get_json()
    case = client.post("/minimize", json=dfa).get_json()["cases"][0]
    original, minimized = case["originalDfa"], case["minimizedDfa"]

    def run(d, x):
        return client.post("/simulate", json={"transitions": d["transitions"], "initial": d["initial"],
                                              "accepting": d["accepting"], "input": x}).get_json()["accepted"]

    for length in range(6):
        for w in itertools.product("ab", repeat=length):
            x = "".join(w)
            assert run(original, x) == run(minimized, x), x


def test_kozen_example_6_5_pipeline(client):
    # Ejemplo 6.5 (Asignación 1): el AFD de /convert para {b, bb, bbb} ya es mínimo.
    nfa = {"states": ["s", "t", "u", "p", "q", "r"], "alphabet": ["b"], "initial": "s", "accepting": ["p", "q", "r"],
           "transitions": [{"from": "s", "symbol": None, "to": "t"}, {"from": "t", "symbol": None, "to": "u"},
                           {"from": "p", "symbol": None, "to": "t"}, {"from": "q", "symbol": None, "to": "u"},
                           {"from": "s", "symbol": "b", "to": "p"}, {"from": "t", "symbol": "b", "to": "q"},
                           {"from": "u", "symbol": "b", "to": "r"}]}
    dfa = client.post("/convert", json=nfa).get_json()
    case = client.post("/minimize", json=dfa).get_json()["cases"][0]
    assert case["isMinimal"] is True and case["stats"]["statesMinimized"] == 5


def test_nfa_sent_to_minimize_is_rejected_clearly(client):
    with open(os.path.join(ROOT, "test_request.json")) as f:
        nfa = json.load(f)
    r = client.post("/minimize", json=nfa)
    assert r.status_code == 400
    assert "epsilon" in r.get_json()["error"] or "Nondeterminism" in r.get_json()["error"] \
        or "Missing transition" in r.get_json()["error"]


def test_sample_request_files(client):
    with open(os.path.join(ROOT, "test_minimize.txt")) as f:
        r = client.post("/minimize?format=text", data=f.read(), content_type="text/plain")
    assert r.get_data(as_text=True) == "(4, 5)\n"
    with open(os.path.join(ROOT, "test_minimize.json")) as f:
        assert client.post("/minimize", json=json.load(f)).get_json()["output"] == "(4, 5)"


def test_assignment1_endpoints_unchanged(client):
    with open(os.path.join(ROOT, "test_simulate.json")) as f:
        assert client.post("/simulate", json=json.load(f)).get_json() == {"path": ["0137", "247", "58"], "accepted": True}
