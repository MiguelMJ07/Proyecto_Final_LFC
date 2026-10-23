# CAPA CONTROLLER
# Responsabilidad: recibir peticiones HTTP, validar el formato de entrada,
# y devolver respuestas HTTP. NO contiene lógica del algoritmo de autómatas.
from flask import Blueprint, jsonify

from controllers.http_utils import json_body
from gateways.automata_gateway import AutomataGateway

# Blueprint agrupa las rutas relacionadas con "automata" en un solo módulo.
automata_bp = Blueprint("automata", __name__)

# Una sola instancia del Gateway, reutilizada en todas las peticiones
# (no guarda estado entre peticiones, así que es seguro compartirla).
gateway = AutomataGateway()


@automata_bp.route("/convert", methods=["POST"])
def convert():
    # Parsea el body JSON (400 si no es un objeto JSON válido) y confirma los campos obligatorios
    # antes de siquiera intentar ejecutar el algoritmo.
    data = json_body(["states", "alphabet", "initial", "accepting", "transitions"])

    try:
        # Delega la ejecución del algoritmo al Gateway.
        result = gateway.convert_nfa_to_dfa(data)
        return jsonify(result), 200
    except (TypeError, KeyError, AttributeError) as e:
        # Campos con tipo incorrecto (por ejemplo, "states" no es una lista): error de formato, no de servidor.
        return jsonify({"error": f"Malformed NFA: {e}"}), 400
    except ValueError as e:
        # Si el Gateway detecta un error de negocio (ej. estado inicial inválido),
        # lo traduce en una respuesta HTTP 400.
        return jsonify({"error": str(e)}), 400


@automata_bp.route("/simulate", methods=["POST"])
def simulate():
    # Validación de forma para /simulate: los campos que necesita simulate_dfa.
    data = json_body(["transitions", "initial", "accepting", "input"])

    try:
        result = gateway.simulate(data)
        return jsonify(result), 200
    except (TypeError, KeyError, AttributeError) as e:
        return jsonify({"error": f"Malformed DFA: {e}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400