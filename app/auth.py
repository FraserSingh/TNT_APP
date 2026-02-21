from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from .extensions import db
from .models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].lower().strip()
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            db.session.refresh(
                user
            )  # Refresh the user to ensure the latest data is loaded
            return redirect(url_for("rota.rota"))

        flash("Invalid credentials")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    """Logs out the current user and redirects to the login page."""
    logout_user()
    return redirect(url_for("auth.login"))
