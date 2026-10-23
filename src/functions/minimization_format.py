# CAPA FUNCTIONS
# Presentación del resultado: la salida de texto que pide el enunciado y la vista
# JSON de cada paso. No tiene ninguna dependencia de Flask ni de HTTP.
#
# Todos los estados se muestran con el nombre que dio el cliente (dfa.name), así
# que un AFD que llega de /convert con estados "0-1-3-7", "dead", ... recibe la
# respuesta con esos mismos nombres.
from __future__ import annotations

from .dfa import DFA
from .minimization import EquivalenceResult, Mark, MinimizationResult


def named_pairs(dfa: DFA, pairs) -> list[tuple]:
    """Pares con los nombres del cliente: cada par ordenado y la lista en orden lexicográfico."""
    return sorted(tuple(sorted((dfa.name(p), dfa.name(q)))) for p, q in pairs)


def format_pairs(pairs) -> str:
    """'(1, 2) (3, 4)' — cadena vacía si no hay pares."""
    return " ".join(f"({p}, {q})" for p, q in pairs)


def format_output(results: list[MinimizationResult]) -> str:
    """Salida del enunciado (sección 5.2): una línea por caso con sus pares equivalentes."""
    return "\n".join(format_pairs(named_pairs(r.dfa, r.equivalent_pairs)) for r in results)


def class_label(dfa: DFA, group: list[int]) -> str:
    return "{" + ",".join(str(dfa.name(q)) for q in group) + "}"


def _mark_to_dict(result: MinimizationResult, m: Mark) -> dict:
    dfa, n = result.dfa, result.dfa.name
    p, q = m.pair
    if m.via is None:
        reason = f"exactly one of {n(p)}, {n(q)} is accepting"
    else:
        r, s = m.via
        reason = f"delta({n(p)},{m.symbol}) = {n(dfa.delta[p][m.symbol])}, delta({n(q)},{m.symbol}) = " \
                 f"{n(dfa.delta[q][m.symbol])}, and {{{n(r)},{n(s)}}} was already marked"
    return {
        "pair": [n(p), n(q)],
        "round": m.round,
        "symbol": m.symbol,
        "via": [n(x) for x in m.via] if m.via else None,
        "witness": result.marking.witness(m.pair),
        "reason": reason,
    }


def marking_table(result: MinimizationResult) -> dict:
    """Tabla triangular de Kozen: fila q, columna p (p antes que q). Cada celda guarda la
    ronda en que se marcó {p, q}, o null si quedó sin marcar (p ≈ q)."""
    dfa, marks = result.dfa, result.marking.marks
    states = list(dfa.states)
    rows = []
    for i, q in enumerate(states[1:], start=1):
        cells = []
        for p in states[:i]:
            m = marks.get((p, q))
            cells.append({"p": dfa.name(p), "q": dfa.name(q), "round": m.round if m else None,
                          "witness": result.marking.witness((p, q)) if m else None})
        rows.append({"state": dfa.name(q), "cells": cells})
    return {"columns": [dfa.name(p) for p in states[:-1]], "rows": rows}


def marking_table_text(result: MinimizationResult) -> str:
    """Versión en texto de la tabla triangular ('Xk' = marcado en la ronda k, '=' = sin marcar)."""
    table = marking_table(result)
    if not table["rows"]:
        return "(single state: no pairs)"
    width = max(3, max(len(str(result.dfa.name(s))) for s in result.dfa.states) + 1)
    lines = []
    for row in table["rows"]:
        cells = [("X" + str(c["round"])) if c["round"] is not None else "=" for c in row["cells"]]
        lines.append(str(row["state"]).rjust(width) + " | " + " ".join(c.center(width) for c in cells))
    lines.append(" " * width + " +-" + "-" * ((width + 1) * len(table["columns"])))
    lines.append(" " * width + "   " + " ".join(str(p).center(width) for p in table["columns"]))
    return "\n".join(lines)


def _steps(result: MinimizationResult) -> dict:
    marks = result.marking.marks
    return {
        "rounds": [
            {
                "round": k,
                "description": "Step 2: mark every pair where exactly one state is accepting (witness: empty string)"
                if k == 0 else f"Step 3, pass {k}: mark pairs whose shortest distinguishing string has length {k}",
                "marked": [_mark_to_dict(result, marks[pq]) for pq in pairs],
            }
            for k, pairs in enumerate(result.marking.rounds)
        ] + [{"round": len(result.marking.rounds), "description": "No new pairs marked: the algorithm stops",
              "marked": []}],
        "markingTable": marking_table(result),
        "markingTableText": marking_table_text(result),
    }


def result_to_dict(result: MinimizationResult, case_no: int, include_steps: bool = True) -> dict:
    """Vista JSON de un caso (llaves en camelCase, como las respuestas de la Asignación 1)."""
    dfa = result.dfa
    labels = {i: class_label(dfa, g) for i, g in enumerate(result.classes)}
    pairs = named_pairs(dfa, result.equivalent_pairs)
    body = {
        "case": case_no,
        "equivalentPairs": [list(p) for p in pairs],
        "output": format_pairs(pairs),
        "isMinimal": result.is_minimal,
        "equivalenceClasses": [[dfa.name(q) for q in g] for g in result.classes],
        "removedInaccessibleStates": [result.original.name(q) for q in result.removed_inaccessible],
        "stats": result.stats,
        "originalDfa": result.original.to_dict(),
        "minimizedDfa": {
            **result.minimized.to_dict(),
            "stateLabels": {str(i): lbl for i, lbl in labels.items()},
            "stateMap": {str(dfa.name(q)): c for q, c in sorted(result.class_of.items())},
            "courseFormat": "1\n" + result.minimized.to_text(),
        },
        "dot": {
            "original": dfa.to_dot("original", groups=result.classes),
            "minimized": result.minimized.to_dot("minimized", labels=labels),
        },
    }
    if include_steps:
        body["steps"] = _steps(result)
    return body


def equivalence_to_dict(res: EquivalenceResult) -> dict:
    body = {"equivalent": res.equivalent, "rounds": res.rounds}
    if res.equivalent:
        body["explanation"] = "The initial states are equivalent in the disjoint union, so L(M1) = L(M2)."
    else:
        x = res.counterexample
        body["counterexample"] = x
        body["acceptedBy"] = res.accepted_by
        shown = "the empty string ε" if x == "" else f"the string '{x}'"
        body["explanation"] = (f"{shown[0].upper() + shown[1:]} is accepted by the {res.accepted_by} DFA only "
                               f"(no shorter string tells them apart), so L(M1) ≠ L(M2).")
    return body
