# CAPA GATEWAY
# Responsabilidad: orquestar la ejecución del algoritmo (llamar a Functions)
# y traducir cualquier excepción interna en un error de negocio (ValueError)
# que el Controller sepa interpretar como respuesta HTTP.
from functions.subset_construction import subset_construction, format_dfa_result
from functions.simulate import simulate_dfa


class AutomataGateway:

    def _validate_nfa(self, nfa_data):
        # Validacion semantica: confirma que los datos del NFA sean coherentes
        # entre si (no solo que existan los campos, sino que tengan sentido).
        states = set(nfa_data["states"])
        alphabet = set(nfa_data["alphabet"])
        initial = nfa_data["initial"]
        accepting = nfa_data["accepting"]
        transitions = nfa_data["transitions"]

        initial_set = set(initial) if isinstance(initial, (list, set, tuple)) else {initial}
        if not initial_set.issubset(states):
            raise ValueError(f"Initial state(s) {initial_set - states} not in states")

        if not set(accepting).issubset(states):
            raise ValueError(f"Accepting states {set(accepting) - states} not in states")

        for t in transitions:
            if t["from"] not in states or t["to"] not in states:
                raise ValueError(f"Transition {t} references a state not in states")
            if t["symbol"] is not None and t["symbol"] not in alphabet:
                raise ValueError(f"Transition {t} uses symbol not in alphabet")

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