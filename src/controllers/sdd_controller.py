# CONTROLLER layer for Item 3 (syntax-directed definitions).
#
#   GET  /sdd/presets        the ready-made SDDs
#   GET  /sdd/presets/<id>   one SDD as data (editable JSON)
#   POST /sdd/describe       attribute table, semantic rules, S/L-attributed classification
#   POST /sdd/evaluate       parse tree + dependency graph + order + main attribute
#                            ("circular": true applies the preset's circular variant, Step 6)
#   GET  /sdd/ui             interactive page
from flask import Blueprint, jsonify, render_template

from controllers.http_utils import json_body, json_error
from gateways.sdd_gateway import SDDGateway

sdd_bp = Blueprint("sdd", __name__)
gateway = SDDGateway()


@sdd_bp.errorhandler(ValueError)       # SDDError and GrammarError are ValueErrors
def _value_error(e):
    return jsonify({"error": str(e)}), 400


@sdd_bp.route("/sdd/presets", methods=["GET"])
def presets():
    return jsonify(gateway.presets())


@sdd_bp.route("/sdd/presets/<pid>", methods=["GET"])
def preset(pid):
    try:
        return jsonify(gateway.preset(pid))
    except KeyError:
        return json_error(f"Unknown preset {pid!r}.", 404)


@sdd_bp.route("/sdd/describe", methods=["POST"])
def describe():
    return jsonify(gateway.describe(json_body()))


@sdd_bp.route("/sdd/evaluate", methods=["POST"])
def evaluate():
    return jsonify(gateway.evaluate(json_body()))


@sdd_bp.route("/sdd/ui", methods=["GET"])
def ui():
    return render_template("sdd.html")
