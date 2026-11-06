# CAPA GATEWAY
# Responsabilidad: orquestar la ejecución del algoritmo (llamar a Functions)
# y traducir cualquier excepción interna en un error de negocio (ValueError)
# que el Controller sepa interpretar como respuesta HTTP.
import json
from collections import Counter

from functions.subset_construction import subset_construction, format_dfa_result
from functions.simulate import simulate_dfa

# Límite para que una petición no bloquee el servidor: un NFA de n estados
# puede dar hasta 2^n estados del DFA. /minimize acepta hasta 500.
MAX_DFA_STATES = 1000
MAX_INPUT = 10000


def _show(value):
    """Un valor JSON tal como lo escribió el cliente, para los mensajes de error."""
    return json.dumps(value, ensure_ascii=False)


def _check_state(q, field):
    # Un estado es un número entero o un nombre; true/false, null, listas u objetos no.
    if isinstance(q, bool) or not isinstance(q, (int, str)):
        raise ValueError(f"Invalid state {_show(q)} in '{field}': a state is a number or a name (string).")


def _state_list(value, field):
    if not isinstance(value, list):
        raise ValueError(f"Field '{field}' must be a list of states, e.g. [0, 1, 2] or [\"q0\", \"q1\"].")
    for q in value:
        _check_state(q, field)
    return value


def _transition_list(value):
    if not isinstance(value, list):
        raise ValueError("Field 'transitions' must be a list of objects {\"from\": q, \"symbol\": a, \"to\": p}.")
    for i, t in enumerate(value, start=1):
        if not isinstance(t, dict) or not {"from", "symbol", "to"} <= set(t):
            raise ValueError(f"Transition {i} must be an object with the fields 'from', 'symbol' and 'to', got {_show(t)}.")
        _check_state(t["from"], f"transition {i}")
        _check_state(t["to"], f"transition {i}")
        if t["symbol"] is not None and not isinstance(t["symbol"], str):
            raise ValueError(f"Transition {i}: 'symbol' must be a string (or null for epsilon), got {_show(t['symbol'])}.")
    return value


class AutomataGateway:

    def _validate_nfa(self, nfa_data):
        # Validación de forma: cada campo tiene el tipo esperado (si no, el mensaje dice cuál y cómo debe ser).
        states = _state_list(nfa_data["states"], "states")
        alphabet = nfa_data["alphabet"]
        if not isinstance(alphabet, list) or not all(isinstance(a, str) and a for a in alphabet):
            raise ValueError("Field 'alphabet' must be a list of symbols (non-empty strings), e.g. [\"a\", \"b\"].")
        initial = nfa_data["initial"]
        initial_list = _state_list(initial, "initial") if isinstance(initial, list) else [initial]
        for q in initial_list:
            _check_state(q, "initial")
        accepting = _state_list(nfa_data["accepting"], "accepting")
        transitions = _transition_list(nfa_data["transitions"])

        # Validación semántica: los datos del NFA son coherentes entre sí.
        if not states:
            raise ValueError("Field 'states' must contain at least one state.")
        repeated = sorted(_show(q) for q, n in Counter(states).items() if n > 1)
        if repeated:
            raise ValueError(f"Repeated states in 'states': {', '.join(repeated)}.")
        if len(set(alphabet)) != len(alphabet):
            raise ValueError("Repeated symbols in 'alphabet'.")
        if not initial_list:
            raise ValueError("Field 'initial' must be a state or a non-empty list of states.")
        state_set = set(states)
        missing = [q for q in initial_list if q not in state_set]
        if missing:
            raise ValueError(f"Initial state(s) {_show(missing)} are not in 'states'.")
        missing = [q for q in accepting if q not in state_set]
        if missing:
            raise ValueError(f"Accepting state(s) {_show(missing)} are not in 'states'.")
        for i, t in enumerate(transitions, start=1):
            if t["from"] not in state_set or t["to"] not in state_set:
                raise ValueError(f"Transition {i} {_show(t)} uses a state that is not in 'states'.")
            if t["symbol"] is not None and t["symbol"] not in alphabet:
                raise ValueError(f"Transition {i} {_show(t)} uses a symbol that is not in 'alphabet' "
                                 f"(write null for an epsilon transition).")

    def _validate_dfa(self, data):
        transitions = _transition_list(data["transitions"])
        _check_state(data["initial"], "initial")
        _state_list(data["accepting"], "accepting")
        if not isinstance(data["input"], str):
            raise ValueError("Field 'input' must be a string (\"\" is the empty string).")
        if len(data["input"]) > MAX_INPUT:
            raise ValueError(f"Field 'input' is longer than {MAX_INPUT} symbols.")
        first = {}                     # (estado, símbolo) -> (número de la transición, destino)
        for i, t in enumerate(transitions, start=1):
            key = (t["from"], t["symbol"])
            if key in first and first[key][1] != t["to"]:
                raise ValueError(f"Transitions {first[key][0]} and {i} both define delta({_show(t['from'])}, "
                                 f"{_show(t['symbol'])}): the automaton is not deterministic.")
            first.setdefault(key, (i, t["to"]))

    def convert_nfa_to_dfa(self, nfa_data):
        self._validate_nfa(nfa_data)

        try:
            # Ejecuta el algoritmo de subset construction.
            # Devuelve los estados del DFA como frozenset (representación matemática pura).
            dfa_states, transitions, accepting_states = subset_construction(
                states=nfa_data["states"],
                alphabet=nfa_data["alphabet"],
                initial=nfa_data["initial"],
                accepting=nfa_data["accepting"],
                nfa_transitions=nfa_data["transitions"],
                max_states=MAX_DFA_STATES,
            )
        except Exception as e:
            # Cualquier excepción interna del algoritmo (KeyError, etc.)
            # se traduce en un ValueError con mensaje claro para el usuario.
            raise ValueError(f"Error building DFA: {e}")

        # Convierte los frozenset a texto legible (ej. "0137"), para poder
        # serializar el resultado como JSON.
        formatted_states, formatted_transitions, formatted_accepting = format_dfa_result(
            dfa_states, transitions, accepting_states
        )

        return {
            "dfaStates": formatted_states,
            "transitions": formatted_transitions,
            "acceptingStates": formatted_accepting,
        }

    def simulate(self, data):
        self._validate_dfa(data)
        try:
            # Ejecuta la simulación del DFA con la cadena de entrada dada.
            path, accepted = simulate_dfa(
                dfa_transitions=data["transitions"],
                initial=data["initial"],
                accepting=data["accepting"],
                input_string=data["input"],
            )
        except Exception as e:
            raise ValueError(f"Error simulating input: {e}")

        return {"path": path, "accepted": accepted}
