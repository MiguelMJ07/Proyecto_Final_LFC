"""The plain-language explanations of LL(1) violations and SLR(1) conflicts (extra). They only read the results of
the real algorithms, so these tests check the facts they state, not the wording."""
from gateways.grammar_gateway import GrammarGateway

gw = GrammarGateway()


def test_example3_left_recursion_and_shift_reduce():
    r = gw.analyze("1\nS -> SS a")
    ll = r["ll1"]["explanations"]
    assert len(ll) == 1 and "left-recursive" in ll[0]["text"] and "M[S, a]" in ll[0]["text"]
    slr = r["slr1"]["explanations"]
    assert [(e["type"], e["symbol"], e["prefix"]) for e in slr] == [("shift/reduce", "a", "SS")]
    assert "FOLLOW(S) = {a, $}" in slr[0]["text"] and "S -> SS" in slr[0]["text"]


def test_reduce_reduce_names_both_productions():
    r = gw.analyze("3\nS -> A B\nA -> a\nB -> a")
    e = [x for x in r["slr1"]["explanations"] if x["type"] == "reduce/reduce"]
    assert e and "A -> a" in e[0]["text"] and "B -> a" in e[0]["text"] and e[0]["prefix"] == "a"


def test_llk_without_left_recursion_asks_for_left_factoring():
    r = gw.analyze("2\nS -> aA ab\nA -> b")      # S -> aA | ab share FIRST {a}
    assert any("left-factored" in e["text"] for e in r["ll1"]["explanations"])


def test_slr_but_not_ll1_explains_only_the_ll1_side():
    r = gw.analyze("3\nS -> S+T T\nT -> T*F F\nF -> (S) i")
    assert r["ll1"]["explanations"] and r["slr1"]["explanations"] == []


def test_endpoints_carry_them():
    assert "explanations" in gw.ll1("1\nS -> SS a") and "explanations" in gw.slr1("1\nS -> SS a")
