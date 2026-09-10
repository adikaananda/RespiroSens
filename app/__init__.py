import os

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from app.api import register_blueprints
from app.config import CONFIG_MAP
from app.extensions import db

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))


def create_app(env: str = None):
    env = env or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__, static_folder=None)
    app.config.from_object(CONFIG_MAP.get(env, CONFIG_MAP["development"]))

    os.makedirs(os.path.join(app.config["MODEL_DIR"]), exist_ok=True)
    os.makedirs(app.config["OUTPUT_DIR"], exist_ok=True)
    instance_dir = os.path.join(os.path.dirname(app.instance_path), "instance")
    os.makedirs(instance_dir, exist_ok=True)

    db.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    register_blueprints(app)

    # Creates missing tables/columns automatically (see app/schema_sync.py) so
    # model changes (e.g. new Patient.age/height_cm/weight_kg fields) don't
    # require deleting the database or running a separate migration tool.
    from app.schema_sync import sync_schema
    sync_schema(app)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "device_mode": app.config["DEVICE_MODE"]})

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not_found", "message": str(e)}), 404

    # --- Serve the frontend as static files ---
    # frontend/index.html + frontend/css/*.css + frontend/js/**/*.js.
    # <path:filename> matches nested paths (e.g. "js/pages/admin.js"), so the
    # folder structure below is free to be reorganized without touching this route.
    @app.get("/")
    def serve_index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/<path:filename>")
    def serve_static(filename):
        if os.path.exists(os.path.join(FRONTEND_DIR, filename)):
            return send_from_directory(FRONTEND_DIR, filename)
        return jsonify({"error": "not_found"}), 404

    return app
