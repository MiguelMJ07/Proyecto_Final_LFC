# CAPA FUNCTIONS
# Lectura de un AFD en los dos formatos aceptados. Cualquier problema en la
# entrada lanza DFAParseError (subclase de ValueError), con el número de línea
# cuando la entrada es texto. No tiene ninguna dependencia de Flask ni de HTTP.
#
# 1. Formato de texto del curso (Asignación 2, sección 5.1):
#
#        c               número de casos
#        n               número de estados del caso 1
#        a b             alfabeto
#        1 4 5           estados finales (la línea puede estar vacía)
#        0 1 2           n filas: estado seguido de δ(estado, símbolo) para cada símbolo
#        ...
#
# 2. JSON con los mismos nombres de campo de la Asignación 1. Los estados pueden
#    ser números o nombres, así que el AFD que devuelve /convert (con estados como
#    "0-1-3-7" o "dead", sin "alphabet" ni "initial") se acepta tal cual.
from __future__ import annotations

from .dfa import DFA, DFAError


class DFAParseError(ValueError):
    def __init__(self, message: str, line: int | None = None):
        self.line = line
        super().__init__(f"Line {line}: {message}" if line else message)


# =================================================== formato de texto del curso
def _to_int(token: str, what: str, line: int) -> int:
    try:
        value = int(token)
    except ValueError:
        raise DFAParseError(f"Expected an integer for {what}, got '{token}'.", line) from None
    if value < 0:
        raise DFAParseError(f"{what.capitalize()} must be a natural number, got {value}.", line)
    return value


class _Lines:
    """Cursor sobre las líneas de la entrada que recuerda el número de línea (base 1)."""

    def __init__(self, text: str):
        self.lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        self.i = 0

    def next_nonblank(self, what: str) -> tuple[list[str], int]:
        while self.i < len(self.lines) and not self.lines[self.i].strip():
            self.i += 1
        if self.i >= len(self.lines):
            raise DFAParseError(f"Unexpected end of input while reading {what}.")
        self.i += 1
        return self.lines[self.i - 1].split(), self.i

    def next_raw(self, what: str) -> tuple[list[str], int]:
        """Siguiente línea aunque esté vacía (la línea de estados finales puede estarlo)."""
        if self.i >= len(self.lines):
            raise DFAParseError(f"Unexpected end of input while reading {what}.")
        self.i += 1
        return self.lines[self.i - 1].split(), self.i

    def rest_is_blank(self) -> bool:
        return all(not ln.strip() for ln in self.lines[self.i:])


def parse_cases(text: str, max_states: int | None = None) -> list[DFA]:
    """Lee una entrada completa en el formato del curso y devuelve un AFD por caso."""
    cur = _Lines(text)
    tokens, ln = cur.next_nonblank("the number of cases")
    if len(tokens) != 1:
        raise DFAParseError("The first line must contain only the number of cases c.", ln)
    c = _to_int(tokens[0], "the number of cases", ln)
    if c <= 0:
        raise DFAParseError("The number of cases c must be greater than 0.", ln)

    cases = [_parse_case(cur, k + 1, max_states) for k in range(c)]
    if not cur.rest_is_blank():
        raise DFAParseError(f"Extra content after the {c} declared case(s).", cur.i + 1)
    return cases


def _parse_case(cur: _Lines, case_no: int, max_states: int | None) -> DFA:
    tokens, ln = cur.next_nonblank(f"the number of states (case {case_no})")
    if len(tokens) != 1:
        raise DFAParseError("Expected a single number n (number of states).", ln)
    n = _to_int(tokens[0], "the number of states", ln)
    if n <= 0:
        raise DFAParseError("The number of states n must be greater than 0.", ln)
    if max_states and n > max_states:
        raise DFAParseError(f"Case {case_no} has {n} states; the server accepts at most {max_states}.", ln)

    alphabet, ln_a = cur.next_nonblank(f"the alphabet (case {case_no})")
    for a in alphabet:
        if len(a) != 1 or not ("a" <= a <= "z"):
            raise DFAParseError(f"Invalid symbol '{a}': symbols must be lowercase letters a-z separated by spaces.", ln_a)
    if len(set(alphabet)) != len(alphabet):
        raise DFAParseError("Alphabet symbols must be unique.", ln_a)

    finals_tok, ln_f = cur.next_raw(f"the final states (case {case_no})")
    finals = [_to_int(t, "a final state", ln_f) for t in finals_tok]

    states: list[int] = []
    rows: dict[int, tuple[dict[str, int], int]] = {}
    for _ in range(n):
        row, ln_r = cur.next_nonblank(f"a transition row (case {case_no})")
        if len(row) != len(alphabet) + 1:
            raise DFAParseError(
                f"A transition row needs {len(alphabet) + 1} values (state + one per symbol), got {len(row)}.", ln_r)
        q = _to_int(row[0], "a state", ln_r)
        if q in rows:
            raise DFAParseError(f"Duplicate row for state {q}.", ln_r)
        states.append(q)
        rows[q] = ({a: _to_int(t, "a target state", ln_r) for a, t in zip(alphabet, row[1:])}, ln_r)

    # Validación semántica, reportada en la línea exacta donde está el problema.
    if 0 not in rows:
        raise DFAParseError(f"Case {case_no}: there is no row for state 0 (the initial state is always 0).")
    for f in finals:
        if f not in rows:
            raise DFAParseError(f"Final state {f} has no row in the table.", ln_f)
    for q, (targets, ln_r) in rows.items():
        for a, t in targets.items():
            if t not in rows:
                raise DFAParseError(f"delta({q}, {a}) = {t} is not a state of Q.", ln_r)

    try:
        return DFA.build(states, alphabet, {q: r for q, (r, _) in rows.items()}, start=0, finals=finals)
    except DFAError as e:  # defensivo: las validaciones de arriba ya deberían haberlo detectado
        raise DFAParseError(f"Case {case_no}: {e}") from None


# ======================================================================= JSON
def _first_key(obj: dict, *keys):
    for k in keys:
        if k in obj:
            return obj[k]
    return None


def _label(value) -> str:
    """Nombre canónico de un estado dado como texto, número o lista (subconjunto)."""
    if isinstance(value, (list, tuple)):
        try:
            items = sorted(value)
        except TypeError:
            items = sorted(value, key=str)
        return "{" + ",".join(map(str, items)) + "}"
    if isinstance(value, (dict, bool)) or value is None:
        raise DFAParseError(f"Invalid state {value!r}.")
    return str(value)


def _infer_alphabet(trans) -> list | None:
    """Si falta "alphabet" (la salida de /convert no lo trae), se deduce de las
    transiciones, en el orden en que aparecen los símbolos."""
    symbols: list = []
    if isinstance(trans, list) and all(isinstance(t, dict) for t in trans):
        for t in trans:
            if "symbol" in t and t["symbol"] not in symbols:
                symbols.append(t["symbol"])
    elif isinstance(trans, dict):
        for row in trans.values():
            if isinstance(row, dict):
                symbols += [a for a in row if a not in symbols]
    return symbols or None


def dfa_from_json(obj, max_states: int | None = None) -> DFA:
    """Construye un AFD a partir de un objeto JSON.

    {
      "states":      [0, 1, 2]  o una cantidad (3)  o nombres ["0-1-3-7", "dead", ...]  (alias: "dfaStates"),
      "alphabet":    ["a", "b"]    (opcional: si falta, se deduce de las transiciones),
      "initial":     0             (opcional: 0 si los estados son números; si no, el primero de la lista),
      "accepting":   [1, 2]                                                    (alias: "acceptingStates"),
      "transitions": [{"from": 0, "symbol": "a", "to": 1}, ...]
                     o {"0": {"a": 1, "b": 2}, ...}
                     o [[1, 2], [0, 2], ...]   (fila i = i-ésimo estado, columnas en el orden del alfabeto)
    }
    """
    if not isinstance(obj, dict):
        raise DFAParseError("Each DFA must be a JSON object.")

    # ---- alfabeto
    alphabet = obj.get("alphabet")
    if alphabet is None:
        alphabet = _infer_alphabet(obj.get("transitions"))
    if isinstance(alphabet, str):
        alphabet = alphabet.split() if " " in alphabet else list(alphabet)
    if not isinstance(alphabet, list) or not alphabet:
        raise DFAParseError("'alphabet' must be a non-empty list of symbols, e.g. [\"a\", \"b\"].")
    for a in alphabet:
        if a is None:
            raise DFAParseError("A DFA cannot have epsilon transitions (symbol null). "
                                "Convert the NFA with POST /convert first.")
        if not isinstance(a, str) or len(a) != 1 or not ("a" <= a <= "z"):
            raise DFAParseError(f"Invalid symbol {a!r} in 'alphabet': symbols must be lowercase letters a-z.")
    if len(set(alphabet)) != len(alphabet):
        raise DFAParseError("Alphabet symbols must be unique.")

    # ---- estados: números o nombres
    raw_states = _first_key(obj, "states", "dfaStates")
    if raw_states is None:
        raise DFAParseError("Missing field 'states' (or 'dfaStates').")
    if isinstance(raw_states, int) and not isinstance(raw_states, bool):
        raw_states = list(range(raw_states))
    if not isinstance(raw_states, list) or not raw_states:
        raise DFAParseError("'states' must be a positive count or a non-empty list.")
    if max_states and len(raw_states) > max_states:
        raise DFAParseError(f"The DFA has {len(raw_states)} states; the server accepts at most {max_states}.")

    numeric = all(isinstance(q, int) and not isinstance(q, bool) for q in raw_states)
    if numeric:
        ids = {q: q for q in raw_states}
        names = None
    else:
        labels = [_label(q) for q in raw_states]
        ids = {lab: i for i, lab in enumerate(labels)}
        names = {i: lab for i, lab in enumerate(labels)}
    if len(ids) != len(raw_states):
        raise DFAParseError("State identifiers must be unique.")
    order = list(ids.values())

    def ref(value, what: str) -> int:
        """Traduce una referencia a un estado (número o nombre) a su id interno."""
        if isinstance(value, list) and (numeric or not isinstance(raw_states[0], list)):
            if len(value) != 1:          # p. ej. "to": [1, 2] sería una transición de AFN
                raise DFAParseError(f"{what} must be exactly one state in a DFA, got {value}.")
            value = value[0]
        if numeric:
            if isinstance(value, str) and value.strip().lstrip("-").isdigit():
                value = int(value)
            if not isinstance(value, int) or isinstance(value, bool) or value not in ids:
                raise DFAParseError(f"{what}: unknown state {value!r}.")
            return value
        key = _label(value)
        if key not in ids:
            raise DFAParseError(f"{what}: unknown state {value!r}.")
        return ids[key]

    # ---- estado inicial y estados de aceptación
    initial_raw = _first_key(obj, "initial", "initialState", "start")
    if initial_raw is None:
        if numeric and 0 not in ids:
            raise DFAParseError("Missing 'initial' (states are numeric and 0 is not one of them).")
        start = 0 if numeric else order[0]   # /convert pone el estado inicial de primero
    else:
        start = ref(initial_raw, "'initial'")

    accepting_raw = _first_key(obj, "accepting", "acceptingStates", "finals")
    if accepting_raw is None:
        accepting_raw = []
    if not isinstance(accepting_raw, list):
        raise DFAParseError("'accepting' must be a list of states.")
    finals = {ref(q, "'accepting'") for q in accepting_raw}

    # ---- transiciones
    delta = _parse_transitions(obj.get("transitions"), order, alphabet, ref, names)

    try:
        return DFA.build(order, alphabet, delta, start=start, finals=finals, names=names)
    except DFAError as e:
        raise DFAParseError(str(e)) from None


def _parse_transitions(trans, order: list[int], alphabet: list, ref, names) -> dict[int, dict[str, int]]:
    delta: dict[int, dict[str, int]] = {q: {} for q in order}
    shown = (lambda q: names[q]) if names else (lambda q: q)

    def put(q: int, a, t: int):
        if a is None:
            raise DFAParseError("A DFA cannot have epsilon transitions (symbol null). "
                                "Convert the NFA with POST /convert first.")
        if not isinstance(a, str):
            raise DFAParseError(f"Invalid symbol {a!r} in a transition.")
        if a in delta[q]:
            raise DFAParseError(f"Nondeterminism: the transition from state {shown(q)!r} on '{a}' is defined twice.")
        delta[q][a] = t

    if isinstance(trans, dict):                                   # {"0": {"a": 1, "b": 2}, ...}
        for q_raw, row in trans.items():
            if not isinstance(row, dict):
                raise DFAParseError(f"Transitions of state {q_raw!r} must be an object like {{\"a\": 1}}.")
            q = ref(q_raw, "Transition source")
            for a, t in row.items():
                put(q, a, ref(t, f"Target of ({q_raw}, {a})"))
        return delta

    if not isinstance(trans, list):
        raise DFAParseError("'transitions' must be a list or an object.")

    if trans and all(isinstance(t, dict) for t in trans):         # [{"from":0,"symbol":"a","to":1}, ...]
        for t in trans:
            missing = [k for k in ("from", "symbol", "to") if k not in t]
            if missing:
                raise DFAParseError(f"Each transition needs 'from', 'symbol' and 'to' (missing {missing}).")
            q = ref(t["from"], "Transition source")
            put(q, t["symbol"], ref(t["to"], f"Target of ({t['from']}, {t['symbol']})"))
        return delta

    if len(trans) != len(order):                                  # [[1, 2], [3, 4], ...] tabla por filas
        raise DFAParseError("'transitions' as a table must have one row per state.")
    for q, row in zip(order, trans):
        if not isinstance(row, list) or len(row) != len(alphabet):
            raise DFAParseError(f"Each table row must list {len(alphabet)} targets (one per symbol).")
        for a, t in zip(alphabet, row):
            put(q, a, ref(t, "Table target"))
    return delta
