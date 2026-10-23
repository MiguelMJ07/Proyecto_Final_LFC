# CAPA CONTROLLER
# Responsabilidad: recibir peticiones HTTP, validar el formato de entrada y
# devolver respuestas HTTP. NO contiene lógica del algoritmo de minimización.
# Mismo patrón que automata_controller.py (Asignación 1).
#
#   POST /minimize           minimiza uno o varios AFD (texto del curso o JSON)
#   POST /minimize/compare   decide si dos AFD aceptan el mismo lenguaje
#   GET  /minimize/example   el ejemplo del enunciado, ya resuelto
#   GET  /minimize/ui        página para probar todo el servidor de forma visual
from flask import Blueprint, Response, jsonify, render_template, request

from gateways.minimization_gateway import MinimizationGateway

minimization_bp = Blueprint("minimization", __name__)

# Una sola instancia del Gateway (no guarda estado entre peticiones).
gateway = MinimizationGateway()

MAX_BODY_BYTES = 2 * 1024 * 1024

# Ejemplo del enunciado (sección 5.1).
EXAMPLE_INPUT = """1
6
a b
1 4 5
0 1 2
1 3 4
2 4 3
3 5 5
4 5 5
5 5 5
"""

# El ejemplo junto a su AFD minimizado: deben ser equivalentes.
COMPARE_EXAMPLE = """2
6
a b
1 4 5
0 1 2
1 3 4
2 4 3
3 5 5
4 5 5
5 5 5
5
a b
1 4
0 1 2
1 3 4
2 4 3
3 4 4
4 4 4
"""


# NFA del enunciado de la Asignación 1 (mismo contenido que test_request.json), para
# mostrar en la página el recorrido completo NFA -> /convert -> /minimize.
NFA_EXAMPLE = """{
  "states": [0, 1, 2, 3, 4, 5, 6, 7, 8],
  "alphabet": ["a", "b"],
  "initial": 0,
  "accepting": [4, 8],
  "transitions": [
    {"from": 0, "symbol": null, "to": 1}, {"from": 0, "symbol": null, "to": 3},
    {"from": 3, "symbol": null, "to": 7}, {"from": 1, "symbol": "a", "to": 2},
    {"from": 3, "symbol": "a", "to": 4},  {"from": 7, "symbol": "a", "to": 7},
    {"from": 0, "symbol": "b", "to": 8},  {"from": 4, "symbol": "b", "to": 5},
    {"from": 7, "symbol": "b", "to": 8},  {"from": 5, "symbol": "b", "to": 6},
    {"from": 8, "symbol": "b", "to": 8}
  ]
}"""


class BadRequest(Exception):
    pass


@minimization_bp.errorhandler(BadRequest)
def _bad_request(e):
    return jsonify({"error": str(e)}), 400


def _error(e: ValueError):
    # El Gateway lanza ValueError; aquí se traduce en HTTP 400. Si el error viene de
    # una entrada de texto, se incluye también el número de línea.
    body = {"error": str(e)}
    if getattr(e, "line", None):
        body["line"] = e.line
    return jsonify(body), 400


def _flag(name: str, default: bool) -> bool:
    value = request.args.get(name)
    if value is None:
        return default
    if value.lower() in ("1", "true", "yes"):
        return True
    if value.lower() in ("0", "false", "no"):
        return False
    raise BadRequest(f"Query parameter '{name}' must be true or false.")


def _wants_text() -> bool:
    fmt = request.args.get("format", "").lower()
    if fmt not in ("", "json", "text"):
        raise BadRequest("Query parameter 'format' must be 'json' or 'text'.")
    if fmt:
        return fmt == "text"
    # JSON por defecto; texto plano solo si el cliente lo prefiere explícitamente.
    return request.accept_mimetypes.best_match(["application/json", "text/plain"]) == "text/plain"


def _read_body():
    """Validación de forma del body. Devuelve ('json', dict) o ('text', str)."""
    if request.content_length and request.content_length > MAX_BODY_BYTES:
        raise BadRequest(f"Request body is larger than {MAX_BODY_BYTES // (1024 * 1024)} MB.")
    if request.is_json:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise BadRequest("Request body must be a valid JSON object.")
        return "json", data
    text = request.get_data(as_text=True)
    if not text.strip():
        raise BadRequest("Empty request body. Send the DFA as text/plain (course format) or as JSON.")
    return "text", text


@minimization_bp.route("/minimize", methods=["POST"])
def minimize():
    as_text = _wants_text()
    include_steps = _flag("steps", default=not as_text)
    kind, body = _read_body()

    try:
        # Delega la ejecución del algoritmo al Gateway.
        if kind == "json":
            result = gateway.minimize_json(body, include_steps)
        else:
            result = gateway.minimize_text(body, include_steps)
    except ValueError as e:
        return _error(e)

    if as_text:
        # Formato de salida del enunciado: una línea por caso con los pares equivalentes.
        return Response(result["output"] + "\n", mimetype="text/plain")
    return jsonify(result), 200


@minimization_bp.route("/minimize/compare", methods=["POST"])
def compare():
    kind, body = _read_body()
    try:
        result = gateway.compare_json(body) if kind == "json" else gateway.compare_text(body)
        return jsonify(result), 200
    except ValueError as e:
        return _error(e)


@minimization_bp.route("/minimize/example", methods=["GET"])
def example():
    result = gateway.minimize_text(EXAMPLE_INPUT, include_steps=False)
    return jsonify({"input": EXAMPLE_INPUT, "expectedOutput": result["output"],
                    "compareInput": COMPARE_EXAMPLE})


@minimization_bp.route("/minimize/ui", methods=["GET"])
def ui():
    return render_template("minimization.html", example=EXAMPLE_INPUT, compare_example=COMPARE_EXAMPLE,
                           nfa_example=NFA_EXAMPLE)
