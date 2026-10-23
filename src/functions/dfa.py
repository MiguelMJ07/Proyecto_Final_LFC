# CAPA FUNCTIONS
# Modelo de un autómata finito determinista M = (Q, Σ, δ, s, F).
# No tiene ninguna dependencia de Flask ni de HTTP.
#
# Internamente los estados siempre son enteros. Si el AFD llega con estados con
# nombre (por ejemplo "0-1-3-7" o "dead", como los devuelve /convert), esos
# nombres se guardan en `names` y se usan en todo lo que se le muestra al cliente.
from __future__ import annotations

from collections import deque
from dataclasses import dataclass


class DFAError(ValueError):
    """El AFD está mal construido (no es completo, referencia estados que no existen, etc.)."""


# Colores para resaltar grupos de estados equivalentes en el grafo (DOT).
_GROUP_COLORS = ["#fde68a", "#bfdbfe", "#bbf7d0", "#fbcfe8", "#ddd6fe", "#fed7aa", "#99f6e4", "#e5e7eb"]


def _dot_escape(text) -> str:
    return str(text).replace("\\", "\\\\").replace('"', '\\"')


@dataclass(frozen=True, eq=False)
class DFA:
    states: tuple[int, ...]
    alphabet: tuple[str, ...]
    delta: dict[int, dict[str, int]]
    start: int
    finals: frozenset[int]
    names: dict[int, str] | None = None   # nombres opcionales de los estados

    # ------------------------------------------------------------ construcción
    @classmethod
    def build(cls, states, alphabet, delta, start, finals, names=None) -> "DFA":
        dfa = cls(
            states=tuple(sorted(states)),
            alphabet=tuple(alphabet),
            delta={q: dict(row) for q, row in delta.items()},
            start=start,
            finals=frozenset(finals),
            names=dict(names) if names else None,
        )
        dfa.validate()
        return dfa

    def validate(self) -> None:
        """Verifica que M sea un AFD bien definido: δ debe ser TOTAL y cerrada en Q."""
        if not self.states:
            raise DFAError("The DFA must have at least one state.")
        if len(set(self.states)) != len(self.states):
            raise DFAError("State identifiers must be unique.")
        if not self.alphabet:
            raise DFAError("The alphabet must contain at least one symbol.")
        for a in self.alphabet:
            if not isinstance(a, str) or len(a) != 1 or not ("a" <= a <= "z"):
                raise DFAError(f"Invalid symbol {a!r}: symbols must be lowercase Latin letters (a-z).")
        if len(set(self.alphabet)) != len(self.alphabet):
            raise DFAError("Alphabet symbols must be unique.")
        qset = set(self.states)
        if self.start not in qset:
            raise DFAError(f"Initial state {self.name(self.start)} is not in Q.")
        bad_finals = sorted(self.finals - qset)
        if bad_finals:
            raise DFAError(f"Accepting states {bad_finals} are not in Q.")
        for q in self.states:
            row = self.delta.get(q)
            if row is None:
                raise DFAError(f"Missing transitions for state {self.name(q)}.")
            for a in self.alphabet:
                if a not in row:
                    raise DFAError(f"Missing transition delta({self.name(q)}, {a}): the DFA must be complete.")
                if row[a] not in qset:
                    raise DFAError(f"delta({self.name(q)}, {a}) = {row[a]} is not a state of Q.")
            extra = sorted(set(row) - set(self.alphabet))
            if extra:
                raise DFAError(f"State {self.name(q)} has transitions on symbols not in the alphabet: {extra}.")

    # -------------------------------------------------------------- semántica
    def name(self, q: int):
        """Nombre visible de un estado: el nombre que dio el cliente, o el mismo número."""
        return self.names[q] if self.names else q

    def run(self, q: int, x) -> int:
        """Función de transición extendida δ̂(q, x)."""
        for a in x:
            if a not in self.delta[q]:
                raise DFAError(f"Symbol {a!r} is not in the alphabet.")
            q = self.delta[q][a]
        return q

    def accepts(self, x) -> bool:
        return self.run(self.start, x) in self.finals

    def accessible_states(self) -> set[int]:
        """Estados alcanzables desde s (recorrido en anchura sobre δ)."""
        seen = {self.start}
        queue = deque([self.start])
        while queue:
            q = queue.popleft()
            for a in self.alphabet:
                r = self.delta[q][a]
                if r not in seen:
                    seen.add(r)
                    queue.append(r)
        return seen

    def restrict_to(self, keep: set[int]) -> "DFA":
        return DFA(
            states=tuple(q for q in self.states if q in keep),
            alphabet=self.alphabet,
            delta={q: dict(self.delta[q]) for q in self.states if q in keep},
            start=self.start,
            finals=frozenset(q for q in self.finals if q in keep),
            names={q: n for q, n in self.names.items() if q in keep} if self.names else None,
        )

    # ---------------------------------------------------------- serialización
    def to_dict(self) -> dict:
        """Mismo formato JSON que usan /convert y /simulate (Asignación 1)."""
        n = self.name
        return {
            "states": [n(q) for q in self.states],
            "alphabet": list(self.alphabet),
            "initial": n(self.start),
            "accepting": [n(q) for q in self.states if q in self.finals],
            "transitions": [{"from": n(q), "symbol": a, "to": n(self.delta[q][a])}
                            for q in self.states for a in self.alphabet],
        }

    def to_text(self) -> str:
        """Un caso en el formato de texto del curso (estados numéricos, estado inicial 0)."""
        lines = [str(len(self.states)), " ".join(self.alphabet), " ".join(map(str, sorted(self.finals)))]
        for q in self.states:
            lines.append(" ".join([str(q)] + [str(self.delta[q][a]) for a in self.alphabet]))
        return "\n".join(lines)

    def to_dot(self, title: str = "M", labels: dict[int, str] | None = None,
               groups: list[list[int]] | None = None) -> str:
        """Código Graphviz (DOT). Los estados de un mismo grupo (tamaño > 1) comparten color."""
        fill: dict[int, str] = {}
        color_idx = 0
        for group in groups or []:
            if len(group) > 1:
                for q in group:
                    fill[q] = _GROUP_COLORS[color_idx % len(_GROUP_COLORS)]
                color_idx += 1

        out = [f'digraph "{_dot_escape(title)}" {{', "  rankdir=LR;", '  node [fontname="Helvetica"];',
               '  edge [fontname="Helvetica"];', '  __start [shape=point, width=0.1, label=""];']
        for q in self.states:
            label = labels[q] if labels and q in labels else self.name(q)
            attrs = ["shape=doublecircle" if q in self.finals else "shape=circle", f'label="{_dot_escape(label)}"']
            if q in fill:
                attrs += ["style=filled", f'fillcolor="{fill[q]}"']
            out.append(f"  q{q} [{', '.join(attrs)}];")
        out.append(f"  __start -> q{self.start};")
        for q in self.states:   # une aristas paralelas en una sola con etiqueta "a,b"
            targets: dict[int, list[str]] = {}
            for a in self.alphabet:
                targets.setdefault(self.delta[q][a], []).append(a)
            for r, syms in targets.items():
                out.append(f'  q{q} -> q{r} [label="{",".join(syms)}"];')
        out.append("}")
        return "\n".join(out)
