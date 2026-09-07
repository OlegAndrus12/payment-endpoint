from flask import Flask
from flask_migrate import Migrate

from app.config import settings
from app.errors import register_error_handlers
from app.main import payments_bp
from app.models import db


def create_app(database_url: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url or settings.database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    Migrate(app, db, render_as_batch=False)

    app.register_blueprint(payments_bp)
    register_error_handlers(app)

    return app
