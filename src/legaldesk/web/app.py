"""Flask-приложение LegalDesk."""

from __future__ import annotations

from flask import Flask, render_template


def create_app() -> Flask:
    """Фабрика Flask-приложения."""
    app = Flask(__name__)

    @app.route("/")
    def index() -> str:
        return render_template("input.html")

    return app
