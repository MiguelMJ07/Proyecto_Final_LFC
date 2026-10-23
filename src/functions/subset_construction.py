# CAPA FUNCTIONS
# Contiene la lógica pura del algoritmo de subset construction.
# No tiene ninguna dependencia de Flask ni de HTTP.


def epsilon_closure(states_set, nfa_transitions):
    """
    Dado un conjunto de estados del NFA, devuelve todos los estados
    alcanzables sin consumir ningún símbolo (transiciones con symbol=None).
    """
    closure = set(states_set)   # resultado acumulado, empieza con los estados de entrada
    pending = list(states_set)  # estados que aún faltan por revisar

    while pending:
        current_state = pending.pop()
        for transition in nfa_transitions:
            # Busca transiciones epsilon que salgan del estado actual.
            if transition["from"] == current_state and transition["symbol"] is None:
                next_state = transition["to"]
                if next_state not in closure:
                    # Estado nuevo: se agrega al resultado Y a la lista de
                    # pendientes, porque también hay que revisar sus propios
                    # vecinos epsilon.
                    closure.add(next_state)
                    pending.append(next_state)

    return closure


def move(states_set, symbol, nfa_transitions):
    """
    Dado un conjunto de estados del NFA y un símbolo, devuelve el conjunto
    de estados alcanzables consumiendo ese símbolo (sin aplicar clausura epsilon).
    """
    result = set()

    for state in states_set:
        for transition in nfa_transitions:
            if transition["from"] == state and transition["symbol"] == symbol:
                result.add(transition["to"])

    return result


def subset_construction(states, alphabet, initial, accepting, nfa_transitions):
    """
    Algoritmo de construcción de subconjuntos: convierte un NFA en su DFA
    equivalente. Cada estado del DFA es un frozenset de estados del NFA.

    Soporta que `initial` sea un único estado o un conjunto/lista de
    estados iniciales (S ⊆ Q, según la definición formal de NFA).

    La función de transición generada es TOTAL: para cada estado y cada
    símbolo del alfabeto siempre existe una transición, incluso si no hay
    destino real, en cuyo caso apunta al estado "muerto" (conjunto vacío).
    """
    if isinstance(initial, (list, set, tuple, frozenset)):
        start_states = set(initial)
    else:
        start_states = {initial}

    # Estado inicial del DFA = clausura epsilon del/los estado(s) inicial(es).
    start_state = frozenset(epsilon_closure(start_states, nfa_transitions))

    dfa_states = [start_state]
    pending = [start_state]
    transitions = []

    while pending:
        current_dfa_state = pending.pop()

        for symbol in alphabet:
            move_result = move(current_dfa_state, symbol, nfa_transitions)
            # Si move_result es vacío, epsilon_closure(vacío) también es vacío,
            # lo cual se convierte en el estado "dead" al formatear.
            new_dfa_state = frozenset(epsilon_closure(move_result, nfa_transitions))

            transitions.append({
                "from": current_dfa_state,
                "symbol": symbol,
                "to": new_dfa_state
            })

            if new_dfa_state not in dfa_states:
                dfa_states.append(new_dfa_state)
                pending.append(new_dfa_state)

    # Un estado del DFA es aceptante si su conjunto interseca con `accepting`.
    accepting_states = [s for s in dfa_states if s & set(accepting)]

    return dfa_states, transitions, accepting_states


def state_name(dfa_state):
    """
    Convierte un frozenset de estados del NFA en un nombre de texto legible,
    ej. frozenset({0,1,3,7}) -> "0-1-3-7". El conjunto vacío se llama "dead".
    """
    if not dfa_state:
        return "dead"
    sorted_states = sorted(dfa_state, key=str)
    return "-".join(str(s) for s in sorted_states)


def format_dfa_result(dfa_states, transitions, accepting_states):
    """
    Traduce el resultado "crudo" de subset_construction (con frozenset)
    al formato final de texto, listo para convertir a JSON.
    """
    formatted_states = [state_name(s) for s in dfa_states]

    formatted_transitions = [
        {
            "from": state_name(t["from"]),
            "symbol": t["symbol"],
            "to": state_name(t["to"])
        }
        for t in transitions
    ]

    formatted_accepting = [state_name(s) for s in accepting_states]

    return formatted_states, formatted_transitions, formatted_accepting