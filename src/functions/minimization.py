# CAPA FUNCTIONS
# Minimización de AFD — Kozen (1997), Lecture 14. Lógica pura, sin Flask ni HTTP.
#
# Algoritmo (Kozen, Lecture 14):
#   1. Escribir una tabla con todos los pares {p, q}, inicialmente sin marcar.
#   2. Marcar {p, q} si p ∈ F y q ∉ F, o viceversa.
#   3. Repetir hasta que no haya cambios: si existe un par {p, q} sin marcar tal que
#      {δ(p, a), δ(q, a)} está marcado para algún a ∈ Σ, entonces marcar {p, q}.
#   4. Al terminar: p ≈ q  si y solo si  {p, q} NO está marcado.
#
# Decisiones de implementación:
#   * El paso 3 se ejecuta por RONDAS SÍNCRONAS: un par marcado en la ronda k solo
#     se justifica con pares marcados en rondas anteriores. La tabla final es
#     exactamente la de Kozen, y además la ronda k coincide con el refinamiento ≈k
#     de la Lecture 13: {p, q} se marca por primera vez en la ronda k  si y solo si
#     la cadena más corta que los distingue tiene longitud k.
#   * Cada par marcado recuerda el símbolo a y el par {δ(p,a), δ(q,a)} que lo causó.
#     Siguiendo esa cadena de causas se reconstruye un TESTIGO: la cadena más corta
#     x tal que exactamente uno de δ̂(p,x), δ̂(q,x) es de aceptación.
#   * Cada ronda solo revisa los pares que siguen sin marcar.
#     Peor caso O(|Q|³·|Σ|) (una cadena que necesita |Q|-1 rondas); en la práctica
#     bastan pocas rondas.
#   * Los pares sin marcar forman la relación ≈; sus clases son los estados del
#     autómata cociente M/≈ (Lecture 13).
from __future__ import annotations

from dataclasses import dataclass, field

from .dfa import DFA, DFAError

Pair = tuple[int, int]  # siempre se guarda con p < q


@dataclass(frozen=True)
class Mark:
    pair: Pair
    round: int                 # 0 = marcado en el paso 2 (aceptación vs. no aceptación)
    symbol: str | None         # símbolo a usado en el paso 3 (None en la ronda 0)
    via: Pair | None           # el par {δ(p,a), δ(q,a)} que ya estaba marcado


@dataclass
class Marking:
    """Resultado de los pasos 1-4 de Kozen sobre un AFD."""
    dfa: DFA
    all_pairs: list[Pair]
    marks: dict[Pair, Mark]
    rounds: list[list[Pair]]          # rounds[k] = pares marcados por primera vez en la ronda k
    unmarked: list[Pair]              # paso 4: exactamente los pares equivalentes (ordenados)

    def is_marked(self, p: int, q: int) -> bool:
        return (min(p, q), max(p, q)) in self.marks

    def witness(self, pair: Pair) -> str:
        """Cadena más corta x tal que exactamente uno de δ̂(p,x), δ̂(q,x) es de aceptación."""
        out = []
        m = self.marks[pair]
        while m.via is not None:
            out.append(m.symbol)
            m = self.marks[m.via]
        return "".join(out)


def mark_pairs(dfa: DFA) -> Marking:
    """Kozen, Lecture 14, pasos 1-4 (algoritmo de llenado de tabla, literal)."""
    states, sigma = dfa.states, dfa.alphabet
    n = len(states)
    index = {q: i for i, q in enumerate(states)}
    # δ por posiciones: D[i][k] = posición de δ(states[i], sigma[k])
    D = [[index[dfa.delta[q][a]] for a in sigma] for q in states]
    accepting = [q in dfa.finals for q in states]

    # Pasos 1 y 2: tabla de todos los pares; se marcan los que difieren en aceptación.
    # Cada par {i, j} con i < j se representa con la llave entera i*n + j.
    round_of: dict[int, int] = {}          # llave -> ronda en que se marcó
    cause: dict[int, tuple[int, int]] = {}  # llave -> (índice del símbolo, llave del par causante)
    base, unmarked = [], []
    for i in range(n):
        for j in range(i + 1, n):
            if accepting[i] != accepting[j]:
                round_of[i * n + j] = 0
                base.append(i * n + j)
            else:
                unmarked.append(i * n + j)
    round_keys = [base]

    # Paso 3: repetir hasta que una ronda completa no marque nada.
    k = 0
    while unmarked:
        k += 1
        newly, still = [], []
        for key in unmarked:
            i, j = divmod(key, n)
            Di, Dj = D[i], D[j]
            for s in range(len(sigma)):
                r, t = Di[s], Dj[s]
                target = r * n + t if r < t else t * n + r
                if r != t and target in round_of:
                    newly.append((key, s, target))
                    break
            else:
                still.append(key)
        if not newly:
            break
        for key, s, target in newly:       # las marcas de la ronda k solo se "ven" desde la ronda k+1
            round_of[key] = k
            cause[key] = (s, target)
        round_keys.append([key for key, _, _ in newly])
        unmarked = still

    def to_pair(key: int) -> Pair:
        i, j = divmod(key, n)
        return states[i], states[j]

    marks: dict[Pair, Mark] = {}
    for key, r in round_of.items():
        if r == 0:
            marks[to_pair(key)] = Mark(to_pair(key), 0, None, None)
        else:
            s, target = cause[key]
            marks[to_pair(key)] = Mark(to_pair(key), r, sigma[s], to_pair(target))

    # Paso 4: los pares que quedaron sin marcar son exactamente los equivalentes.
    return Marking(
        dfa=dfa,
        all_pairs=[(states[i], states[j]) for i in range(n) for j in range(i + 1, n)],
        marks=marks,
        rounds=[[to_pair(key) for key in keys] for keys in round_keys],
        unmarked=sorted(to_pair(key) for key in unmarked),
    )


# ================================================================ minimización
@dataclass
class MinimizationResult:
    original: DFA                     # AFD tal como llegó
    dfa: DFA                          # AFD que realmente se minimizó (parte accesible)
    removed_inaccessible: list[int]
    marking: Marking
    classes: list[list[int]]          # clases de equivalencia [q]
    class_of: dict[int, int]          # estado -> índice de su clase = estado de M/≈
    minimized: DFA
    stats: dict = field(default_factory=dict)

    @property
    def equivalent_pairs(self) -> list[Pair]:
        return self.marking.unmarked

    @property
    def is_minimal(self) -> bool:
        return not self.marking.unmarked and not self.removed_inaccessible


def minimize(dfa: DFA) -> MinimizationResult:
    # El algoritmo de Kozen supone que no hay estados inaccesibles. El enunciado lo
    # garantiza, pero si llegan se eliminan primero (y se reporta) para que el
    # resultado siempre sea mínimo.
    accessible = dfa.accessible_states()
    removed = [q for q in dfa.states if q not in accessible]
    work = dfa.restrict_to(accessible) if removed else dfa

    marking = mark_pairs(work)
    classes, class_of = _equivalence_classes(work, marking.unmarked)
    minimized = _quotient(work, classes, class_of)

    return MinimizationResult(
        original=dfa,
        dfa=work,
        removed_inaccessible=removed,
        marking=marking,
        classes=classes,
        class_of=class_of,
        minimized=minimized,
        stats={
            "statesOriginal": len(dfa.states),
            "statesMinimized": len(classes),
            "pairsTotal": len(marking.all_pairs),
            "pairsMarked": len(marking.marks),
            "pairsEquivalent": len(marking.unmarked),
            "rounds": len(marking.rounds),
        },
    )


def _equivalence_classes(dfa: DFA, equivalent_pairs: list[Pair]) -> tuple[list[list[int]], dict[int, int]]:
    """Agrupa los estados en las clases [q] de ≈ con union-find sobre los pares sin marcar."""
    parent = {q: q for q in dfa.states}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for p, q in equivalent_pairs:
        rp, rq = find(p), find(q)
        if rp != rq:
            parent[max(rp, rq)] = min(rp, rq)

    groups: dict[int, list[int]] = {}
    for q in dfa.states:
        groups.setdefault(find(q), []).append(q)

    # La clase del estado inicial es el estado 0; las demás se ordenan por su menor elemento.
    start_root = find(dfa.start)
    ordered = sorted(groups.values(), key=lambda g: (find(g[0]) != start_root, g[0]))
    class_of = {q: i for i, g in enumerate(ordered) for q in g}
    return ordered, class_of


def _quotient(dfa: DFA, classes: list[list[int]], class_of: dict[int, int]) -> DFA:
    """Autómata cociente M/≈ (Kozen, Lecture 13):
    Q' = {[p]},  δ'([p], a) = [δ(p, a)],  s' = [s],  F' = {[p] | p ∈ F}.
    δ' está bien definida porque ≈ es una congruencia: p ≈ q implica δ(p,a) ≈ δ(q,a)."""
    delta = {i: {a: class_of[dfa.delta[g[0]][a]] for a in dfa.alphabet} for i, g in enumerate(classes)}
    finals = {class_of[q] for q in dfa.finals}
    return DFA.build(range(len(classes)), dfa.alphabet, delta, class_of[dfa.start], finals)


# ======================================================= equivalencia de 2 AFD
@dataclass
class EquivalenceResult:
    first: DFA
    second: DFA
    equivalent: bool
    counterexample: str | None        # cadena más corta que acepta solo uno de los dos
    accepted_by: str | None           # "first" o "second"
    rounds: int


def compare(first: DFA, second: DFA) -> EquivalenceResult:
    """L(M1) = L(M2)  si y solo si  los dos estados iniciales son equivalentes en la
    unión disjunta M1 + M2.

    El mismo algoritmo de marcado lo decide, y el testigo del par {s1, s2} es la
    cadena más corta que un autómata acepta y el otro rechaza."""
    if set(first.alphabet) != set(second.alphabet):
        raise DFAError(f"Both DFAs must have the same alphabet: {sorted(first.alphabet)} vs {sorted(second.alphabet)}.")
    a = first.restrict_to(first.accessible_states())
    b = second.restrict_to(second.accessible_states())

    # Unión disjunta: los estados de M1 van en 0..n1-1 y los de M2 a continuación.
    ia = {q: i for i, q in enumerate(a.states)}
    ib = {q: len(ia) + i for i, q in enumerate(b.states)}
    delta = {ia[q]: {x: ia[a.delta[q][x]] for x in a.alphabet} for q in a.states}
    delta.update({ib[q]: {x: ib[b.delta[q][x]] for x in a.alphabet} for q in b.states})
    finals = {ia[q] for q in a.finals} | {ib[q] for q in b.finals}
    union = DFA.build(range(len(ia) + len(ib)), a.alphabet, delta, ia[a.start], finals)

    marking = mark_pairs(union)
    pair = (ia[a.start], ib[b.start])
    if not marking.is_marked(*pair):
        return EquivalenceResult(first, second, True, None, None, len(marking.rounds))
    x = marking.witness(pair)
    return EquivalenceResult(first, second, False, x, "first" if a.accepts(x) else "second", len(marking.rounds))
