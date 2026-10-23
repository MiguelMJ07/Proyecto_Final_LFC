# Application entry point.
# Its only responsibility is to create the Flask server and connect the routes of every stage:
#   Assignment 1  /convert, /simulate
#   Assignment 2  /minimize, /minimize/compare, /minimize/example, /minimize/ui
#   Final project /grammar/*, /sdd/*   (First/Follow, LL(1), SLR(1), SDD evaluation)
#   Pages         /, /health, /api
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


if __name__ == "__main__":
    # HOST / PORT can be changed with environment variables; debug reload is for development only.
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")),
            debug=os.environ.get("FLASK_DEBUG", "1") == "1")
