# Shared HTTP helpers: strict body reading and uniform JSON errors for every controller.
from flask import jsonify, request

MAX_BODY_BYTES = 2 * 1024 * 1024


class BadRequest(Exception):
    def __init__(self, message, status=400, extra=None):
        super().__init__(message)
        self.status, self.extra = status, extra or {}


def json_error(message, status=400, **extra):
    return jsonify({"error": message, **extra}), status


def json_body(required=()):
    """The request body must be a JSON object. Raises BadRequest otherwise (never a 500)."""
    if request.content_length and request.content_length > MAX_BODY_BYTES:
        raise BadRequest(f"Request body is larger than {MAX_BODY_BYTES // (1024 * 1024)} MB.", 413)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise BadRequest("Request body must be a valid JSON object (Content-Type: application/json).")
    for f in required:
        if f not in data:
            raise BadRequest(f"Missing field: {f}")
    return data


def grammar_text():
    """A grammar may be sent as JSON {"grammar": "..."} or as a raw text/plain body."""
    if request.is_json:
        return json_body(["grammar"])["grammar"]
    text = request.get_data(as_text=True)
    if not text.strip():
        raise BadRequest("Empty body. Send JSON {\"grammar\": \"3\\nS -> ...\"} or the grammar as text/plain.")
    return text


def install_error_handlers(app):
    @app.errorhandler(BadRequest)
    def _bad(e):
        return json_error(str(e), e.status, **e.extra)

    @app.errorhandler(404)
    def _404(e):
        return json_error(f"Not found: {request.path}", 404)

    @app.errorhandler(405)
    def _405(e):
        return json_error(f"Method {request.method} not allowed for {request.path}", 405)

    @app.errorhandler(413)
    def _413(e):
        return json_error("Request body too large.", 413)

    @app.errorhandler(500)
    def _500(e):
        return json_error("Internal server error.", 500)
