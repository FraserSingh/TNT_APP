import os

from flask import Flask

from .admin import *  # noqa: F401, F403
from .auth import *  # noqa: F401, F403
from .extensions import db, login_manager
from .models import User
from .rota import *  # noqa: F401, F403


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///rota.db"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    app.register_blueprint(auth_bp)  # noqa: F405
    app.register_blueprint(rota_bp)  # noqa: F405
    app.register_blueprint(admin_bp)  # noqa: F405

    with app.app_context():
        db.create_all()

    return app
