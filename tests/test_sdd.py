"""Item 3: SDD validation, classification, dependency graph, evaluation order, circularity, safe expressions."""
import copy
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from functions.cfg_sdd import SDD, SDDError, evaluate, with_circular_variant
from functions.cfg_sdd_presets import LUHN, WEIGHTED
from functions.safe_expr import ExprError, compile_expr


def luhn_ref(s):
    total = 0
    for k, ch in enumerate(reversed(s)):
        d = int(ch)
        if k % 2 == 1:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
    return total, total % 10 == 0


def weighted_ref(s):
    total = sum(int(c) * (i + 1) for i, c in enumerate(s))
    return total, total % 11 == 0


def test_luhn_matches_reference_on_random_strings():
    sdd = SDD(LUHN)
    rng = random.Random(1)
    for _ in range(120):
        s = "".join(rng.choice("0123456789") for _ in range(rng.randint(1, 25)))
        r = evaluate(sdd, s)
        total, valid = luhn_ref(s)
        assert r["accepted"] and r["main"]["value"] is valid
        assert r["tree"]["attrs"]["sum"] == total


def test_weighted_matches_reference_and_is_l_attributed():
    sdd = SDD(WEIGHTED)
    assert sdd.classify()["lAttributed"] and not sdd.classify()["sAttributed"]
    rng = random.Random(2)
    for _ in range(120):
        s = "".join(rng.choice("0123456789") for _ in range(rng.randint(1, 25)))
        r = evaluate(sdd, s)
        total, valid = weighted_ref(s)
        assert r["main"]["value"] is valid and r["tree"]["attrs"]["sum"] == total


def test_luhn_is_neither_s_nor_l_attributed_with_reason():
    c = SDD(LUHN).classify()
    assert not c["sAttributed"] and not c["lAttributed"]
    assert any("D.k" in x and "right" in x for x in c["reasons"])


def test_known_valid_number_and_rejections():
    sdd = SDD(LUHN)
    assert evaluate(sdd, "79927398713")["main"]["value"] is True
    assert evaluate(sdd, "49927398716")["main"]["value"] is True
    assert evaluate(sdd, "12a")["accepted"] is False
    assert evaluate(sdd, "")["accepted"] is False          # the language has no empty string
    assert evaluate(sdd, "0")["main"]["value"] is True      # shortest string


def test_deep_recursion_does_not_hit_the_python_stack():
    r = evaluate(SDD(LUHN), "7" * 400)
    assert r["accepted"] and r["stats"]["treeNodes"] > 1500


def test_evaluation_order_is_topological():
    r = evaluate(SDD(LUHN), "79927398713")
    pos = {s["vertex"]: i for i, s in enumerate(r["order"])}
    for e in r["edges"]:
        if e["from"] in pos:                                # edges from terminals (lexval) are always satisfied
            assert pos[e["from"]] < pos[e["to"]], e
    assert len(pos) == r["stats"]["attributeInstances"]


def test_inherited_attribute_comes_from_the_right_sibling():
    # The evaluation order cannot be a left-to-right traversal: D.k (inherited) needs M.cnt of its right sibling.
    r = evaluate(SDD(LUHN), "18")
    names = [s["vertex"] for s in r["order"]]
    assert names.index("M#4.cnt") < names.index("D#2.k")


@pytest.mark.parametrize("p", [LUHN, WEIGHTED])
def test_circular_variant_is_detected_with_cycle(p):
    r = evaluate(SDD(with_circular_variant(p)), "18")
    assert r["circular"] is True
    assert r["cycle"][0] == r["cycle"][-1] and len(r["cycle"]) >= 3
    assert "order" not in r and "main" not in r


def test_validation_errors():
    def with_rules(mut):
        d = copy.deepcopy(LUHN)
        mut(d)
        return d
    with pytest.raises(SDDError, match="never defined"):
        SDD(with_rules(lambda d: d["rules"].__setitem__("M -> e", ["M.cnt = 0"])))
    with pytest.raises(SDDError, match="defined 2 times"):
        SDD(with_rules(lambda d: d["rules"].__setitem__("M -> e", ["M.cnt = 0", "M.cnt = 1", "M.sum = 0"])))
    with pytest.raises(SDDError, match="not allowed"):
        # an inherited attribute of the HEAD cannot be defined in its own production
        w = copy.deepcopy(WEIGHTED)
        w["rules"]["L -> DM"] = w["rules"]["L -> DM"] + ["L.pos = 1"]
        SDD(w)
    with pytest.raises(SDDError, match="inherited"):
        SDD(with_rules(lambda d: d["attributes"]["S"].__setitem__("inh", ["x"])))
    with pytest.raises(SDDError, match="no attribute"):
        SDD(with_rules(lambda d: d["rules"].__setitem__("M -> e", ["M.cnt = 0", "M.sum = 0", "M.zzz = 1"])))
    with pytest.raises(SDDError, match="main"):
        SDD(with_rules(lambda d: d.__setitem__("main", "L.sum")))
    with pytest.raises(SDDError, match="Unknown name"):
        SDD(with_rules(lambda d: d["rules"].__setitem__("M -> e", ["M.cnt = foo", "M.sum = 0"])))


def test_repeated_symbol_needs_positional_references():
    d = {"grammar": "2\nS -> P\nP -> (P)P e", "attributes": {"S": {"syn": ["m"]}, "P": {"inh": ["d"], "syn": ["m"]}},
         "main": "S.m", "rules": {"S -> P": ["P.d = 0", "S.m = P.m"],
                                  "P -> (P)P": ["$2.d = $0.d + 1", "$4.d = $0.d", "$0.m = max($2.m, $4.m)"],
                                  "P -> e": ["P.m = P.d"]}}
    with pytest.raises(SDDError, match="more than once"):
        bad = copy.deepcopy(d)
        bad["rules"]["P -> (P)P"][0] = "P.d = 1"
        SDD(bad)
    r = evaluate(SDD(d), "(()())")
    assert r["main"]["value"] == 2


def test_safe_expressions():
    f = compile_expr("max(a, 3) + (b if a > 1 else 0)", {"a", "b"})
    assert f({"a": 5, "b": 7}) == 12
    for bad in ("__import__('os')", "a.__class__", "[x for x in a]", "open('f')", "a ** 9", "lambda: 1", "a[0]", "exec('1')"):
        with pytest.raises(ExprError):
            compile_expr(bad, {"a"})
    with pytest.raises(ExprError):
        compile_expr("'a' * 100000000", set())({})
    with pytest.raises(ExprError):
        compile_expr("1 // 0", set())({})
