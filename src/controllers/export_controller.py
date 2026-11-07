# CONTROLLER layer for the LaTeX export.
#   POST /export/latex/grammar  {grammar, inputs?, parser?, title?}      -> {filename, tex}
#   POST /export/latex/sdd      {preset|definition, circular?, input?}   -> {filename, tex}
# Add ?download=1 to receive the .tex file itself (Content-Disposition: attachment).
from flask import Blueprint, Response, jsonify, request

from controllers.http_utils import json_body
from gateways.export_gateway import ExportGateway

export_bp = Blueprint("export", __name__)
gateway = ExportGateway()


@export_bp.errorhandler(ValueError)
def _value_error(e):
    return jsonify({"error": str(e)}), 400


def _reply(result):
    if request.args.get("download") in ("1", "true"):
        return Response(result["tex"], mimetype="application/x-tex",
                        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'})
    return jsonify(result)


@export_bp.route("/export/latex/grammar", methods=["POST"])
def grammar():
    return _reply(gateway.grammar(json_body(["grammar"])))


@export_bp.route("/export/latex/sdd", methods=["POST"])
def sdd():
    return _reply(gateway.sdd(json_body()))
