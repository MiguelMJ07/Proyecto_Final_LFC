# Application entry point.
# Its only responsibility is to create the Flask server and connect the routes of every stage:
#   Assignment 1  /convert, /simulate
#   Assignment 2  /minimize, /minimize/compare, /minimize/example, /minimize/ui
#   Final project /grammar/*, /sdd/*   (First/Follow, LL(1), SLR(1), SDD evaluation)
#   Pages         /, /health, /api
# Development: `python src/app.py`. Production (Render, see DESPLIEGUE.md): `gunicorn --chdir src app:app`,
# which imports `app` from this file and never runs the block at the end.
import os

from flask import Flask

from controllers.automata_controller import automata_bp
from controllers.grammar_controller import grammar_bp
from controllers.http_utils import MAX_BODY_BYTES, install_error_handlers
from controllers.minimization_controller import minimization_bp
from controllers.pages_controller import pages_bp
from controllers.sdd_controller import sdd_bp

app = Flask(__name__)
# Keep the key order of the JSON responses instead of sorting alphabetically.
app.json.sort_keys = False
app.json.ensure_ascii = False
app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES
app.config["TEMPLATES_AUTO_RELOAD"] = True

for bp in (pages_bp, automata_bp, minimization_bp, grammar_bp, sdd_bp):
    app.register_blueprint(bp)
install_error_handlers(app)


def run_options(env):
    """HOST, PORT and FLASK_DEBUG for the development server. The debugger lets whoever opens an error page run
    Python code, so by default it is on only when the server listens on this machine (127.0.0.1); with
    HOST=0.0.0.0 other devices can connect and it is off unless FLASK_DEBUG=1 is set explicitly."""
    host = env.get("HOST", "127.0.0.1")
    local = host in ("127.0.0.1", "localhost", "::1")
    return {"host": host, "port": int(env.get("PORT", "5000")),
            "debug": env.get("FLASK_DEBUG", "1" if local else "0") == "1"}


if __name__ == "__main__":
    app.run(**run_options(os.environ))
