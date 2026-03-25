"""Flask web application factory."""

import os
from flask import Flask


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY") or "unraid-backup-default-key"
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    from .routes import bp
    app.register_blueprint(bp)

    @app.after_request
    def no_cache(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    return app
