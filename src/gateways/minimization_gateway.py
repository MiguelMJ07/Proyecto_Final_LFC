# CAPA GATEWAY
# Responsabilidad: orquestar la ejecución del algoritmo de minimización (llamar a
# Functions) y traducir cualquier excepción interna en un error de negocio
# (ValueError) que el Controller sepa interpretar como respuesta HTTP 400.
# Mismo patrón que AutomataGateway (Asignación 1).
from functions.dfa_parser import DFAParseError, dfa_from_json, parse_cases
from functions.minimization import compare, minimize
from functions.minimization_format import equivalence_to_dict, format_output, result_to_dict

ALGORITHM = "Kozen (1997), Lecture 14 - table-filling (marking) minimization"

# Límites para que una petición no bloquee el servidor. El peor caso del algoritmo
# (una cadena de |Q| estados) tarda unos pocos segundos con 500 estados.
MAX_STATES = 500
MAX_CASES = 50
MAX_STATES_WITH_STEPS = 150  # la traza paso a paso crece con |Q|², solo se envía para AFD pequeños


class MinimizationGateway:

    # ------------------------------------------------------------- lectura
    def _load_text(self, text):
        return parse_cases(text, max_states=MAX_STATES)

    def _load_json(self, data):
        # Formas aceptadas: {"input": "<texto del curso>"}, {"cases": [AFD, ...]} o un solo AFD.
        if "input" in data:
            if not isinstance(data["input"], str):
                raise DFAParseError("'input' must be a string in the course text format.")
            return self._load_text(data["input"])
        if "cases" in data:
            if not isinstance(data["cases"], list) or not data["cases"]:
                raise DFAParseError("'cases' must be a non-empty list of DFA objects.")
            dfas = []
            for i, case in enumerate(data["cases"], start=1):
                try:
                    dfas.append(dfa_from_json(case, max_states=MAX_STATES))
                except DFAParseError as e:
                    raise DFAParseError(f"Case {i}: {e}") from None
            return dfas
        return [dfa_from_json(data, max_states=MAX_STATES)]

    def _run(self, action):
        try:
            return action()
        except ValueError:
            # DFAParseError y DFAError ya son ValueError con un mensaje claro para el usuario.
            raise
        except Exception as e:
            # Cualquier otra excepción interna del algoritmo se traduce en un ValueError,
            # igual que en AutomataGateway.
            raise ValueError(f"Error minimizing DFA: {e}")

    # ---------------------------------------------------------- minimizar
    def minimize_text(self, text, include_steps=True):
        return self._run(lambda: self._minimize(self._load_text(text), include_steps))

    def minimize_json(self, data, include_steps=True):
        return self._run(lambda: self._minimize(self._load_json(data), include_steps))

    def _minimize(self, dfas, include_steps):
        if len(dfas) > MAX_CASES:
            raise ValueError(f"At most {MAX_CASES} cases per request.")
        results = [minimize(d) for d in dfas]

        cases = []
        for i, r in enumerate(results, start=1):
            steps = include_steps and len(r.dfa.states) <= MAX_STATES_WITH_STEPS
            case = result_to_dict(r, i, include_steps=steps)
            if include_steps and not steps:
                case["stepsOmitted"] = (f"The step trace is only returned for DFAs with at most "
                                        f"{MAX_STATES_WITH_STEPS} states.")
            cases.append(case)

        return {
            "algorithm": ALGORITHM,
            "numCases": len(results),
            "output": format_output(results),   # salida exacta del enunciado (sección 5.2)
            "cases": cases,
        }

    # ----------------------------------------------------------- comparar
    def compare_text(self, text):
        return self._run(lambda: self._compare(self._load_text(text)))

    def compare_json(self, data):
        return self._run(lambda: self._compare(self._load_json(data)))

    def _compare(self, dfas):
        if len(dfas) != 2:
            raise ValueError(f"Exactly 2 DFAs are needed to compare, got {len(dfas)}.")
        return {"algorithm": ALGORITHM + " on the disjoint union of both DFAs",
                **equivalence_to_dict(compare(*dfas))}
