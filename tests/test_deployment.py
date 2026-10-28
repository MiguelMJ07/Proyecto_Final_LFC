"""Server configuration: development options of src/app.py and the Render deployment (render.yaml, DESPLIEGUE.md)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app import app, run_options

ROOT = os.path.join(os.path.dirname(__file__), "..")


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def test_debugger_only_on_this_machine_by_default():
    assert run_options({}) == {"host": "127.0.0.1", "port": 5000, "debug": True}
    assert run_options({"HOST": "0.0.0.0"})["debug"] is False             # other devices can connect
    assert run_options({"HOST": "0.0.0.0", "FLASK_DEBUG": "1"})["debug"] is True
    assert run_options({"FLASK_DEBUG": "0", "PORT": "8080"}) == {"host": "127.0.0.1", "port": 8080, "debug": False}


def test_render_blueprint_matches_the_app():
    blueprint = read("render.yaml")
    assert "gunicorn --chdir src app:app --bind 0.0.0.0:$PORT" in blueprint      # `app` object of src/app.py
    assert "healthCheckPath: /health" in blueprint
    assert app.test_client().get("/health").get_json()["status"] == "ok"
    assert "pip install -r requirements.txt" in blueprint
    assert 'gunicorn==23.0.0; sys_platform != "win32"' in read("requirements.txt")
    assert "render.yaml" in read("DESPLIEGUE.md") and "DESPLIEGUE.md" in read("README.md")
