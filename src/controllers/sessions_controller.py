# CONTROLLER layer for saved sessions (grammars and SDDs kept in a SQLite file).
#   GET    /sessions?kind=grammar|sdd   list (without payload)
#   POST   /sessions                    {kind, name, payload}  create or replace by (kind, name)
#   GET    /sessions/<id>               one session with its payload
#   DELETE /sessions/<id>
import os

from flask import Blueprint, current_app, jsonify, request

from controllers.http_utils import json_body, json_error
from functions.sessions_store import SessionError, SessionStore

sessions_bp = Blueprint("sessions", __name__)
DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "sessions.db")


def store():
    path = current_app.config.get("SESSIONS_DB") or os.environ.get("SESSIONS_DB") or DEFAULT_DB
    return SessionStore(path)


@sessions_bp.errorhandler(SessionError)
def _session_error(e):
    return jsonify({"error": str(e)}), 400


@sessions_bp.route("/sessions", methods=["GET"])
def list_sessions():
    return jsonify(store().list(request.args.get("kind")))


@sessions_bp.route("/sessions", methods=["POST"])
def save_session():
    d = json_body(["kind", "name", "payload"])
    return jsonify(store().save(d["kind"], d["name"], d["payload"])), 201


@sessions_bp.route("/sessions/<int:sid>", methods=["GET"])
def get_session(sid):
    try:
        return jsonify(store().get(sid))
    except KeyError:
        return json_error(f"No session with id {sid}.", 404)


@sessions_bp.route("/sessions/<int:sid>", methods=["DELETE"])
def delete_session(sid):
    try:
        store().delete(sid)
        return jsonify({"deleted": sid})
    except KeyError:
        return json_error(f"No session with id {sid}.", 404)
