# CONTROLLER layer for the API documentation.
#   GET /openapi.json   the OpenAPI 3 description (data in controllers/openapi_spec.py)
#   GET /docs           Swagger UI (bundled in static/vendor/swagger, no internet needed)
from flask import Blueprint, jsonify, render_template

from controllers.openapi_spec import build_spec

docs_bp = Blueprint("docs", __name__)


@docs_bp.route("/openapi.json", methods=["GET"])
def openapi():
    return jsonify(build_spec())


@docs_bp.route("/docs", methods=["GET"])
def docs():
    return render_template("docs.html")
