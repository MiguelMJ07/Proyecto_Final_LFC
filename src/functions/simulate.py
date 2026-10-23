# CAPA FUNCTIONS
# Lógica pura para simular el recorrido de un DFA con una cadena de entrada.


def simulate_dfa(dfa_transitions, initial, accepting, input_string):
    """
    Recorre el DFA consumiendo input_string símbolo a símbolo.
    Devuelve (path, accepted):
      - path: lista de estados visitados, en orden.
      - accepted: True si la cadena termina en un estado de aceptación.
    """
    # Diccionario para buscar transiciones en O(1): llave = (estado, símbolo).
    transition_map = {}
    for t in dfa_transitions:
        transition_map[(t["from"], t["symbol"])] = t["to"]

    current_state = initial
    path = [current_state]

    for symbol in input_string:
        key = (current_state, symbol)
        if key not in transition_map:
            # No existe transición para este símbolo: la cadena es rechazada.
            return path, False
        current_state = transition_map[key]
        path.append(current_state)

    accepted = current_state in accepting
    return path, accepted