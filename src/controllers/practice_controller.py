# CONTROLLER layer for practice mode.
#   GET  /practice/kinds                                  exercise types
#   GET  /practice/new?kind=sets&seed=42&difficulty=2     a reproducible exercise (the same seed gives the same grammar)
#   POST /practice/check {kind, seed, difficulty, answer} item-by-item correction and the solution
#   GET  /practice/ui                                     page
import random

from flask import Blueprint, jsonify, render_template, request

from controllers.http_utils import json_body
from gateways.practice_gateway import PracticeGateway

practice_bp = Blueprint("practice", __name__)
gateway = PracticeGateway()


@practice_bp.errorhandler(ValueError)
def _value_error(e):
    return jsonify({"error": str(e)}), 400


@practice_bp.route("/practice/kinds", methods=["GET"])
def kinds():
    return jsonify(gateway.kinds())


@practice_bp.route("/practice/new", methods=["GET"])
def new():
    seed = request.args.get("seed")
    if seed is None:
        seed = random.randint(1, 99999)
    return jsonify(gateway.new(request.args.get("kind", "sets"), seed, request.args.get("difficulty", 2)))


@practice_bp.route("/practice/check", methods=["POST"])
def check():
    d = json_body(["kind", "seed", "answer"])
    return jsonify(gateway.check(d["kind"], d["seed"], d.get("difficulty", 2), d["answer"]))


@practice_bp.route("/practice/ui", methods=["GET"])
def ui():
    return render_template("practice.html")
