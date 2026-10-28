"""Bridge between the two worlds of the course: a right-linear (regular) grammar becomes an NFA in the
JSON format of POST /convert, which can then go to /minimize. Standard construction:
A -> aB gives A --a--> B ; A -> a gives A --a--> qf ; A -> e makes A accepting."""
from functions.cfg_grammar import is_nt

FINAL = "qf"


def right_linear_to_nfa(g):
    trans, accepting = [], [FINAL]
    for A, body in g.prods:
        if not body:
            accepting.append(A)
        elif len(body) == 1 and not is_nt(body[0]):
            trans.append({"from": A, "symbol": body[0], "to": FINAL})
        elif len(body) == 2 and not is_nt(body[0]) and is_nt(body[1]):
            trans.append({"from": A, "symbol": body[0], "to": body[1]})
        else:
            hint = " (it looks left-linear)" if is_nt(body[0]) else ""
            raise ValueError(f"The production {A} -> {''.join(body)} is not of the form A -> aB, A -> a or A -> e{hint}; "
                             f"only right-linear grammars convert to an NFA with this construction.")
    if FINAL in g.nonterminals:
        raise ValueError(f"The name {FINAL!r} is reserved for the final state.")
    states = list(g.nonterminals) + [FINAL]
    return {"states": states, "alphabet": list(g.terminals), "initial": g.start,
            "accepting": sorted(set(accepting), key=str), "transitions": trans}
