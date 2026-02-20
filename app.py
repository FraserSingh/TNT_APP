import os
from datetime import datetime, timedelta

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

# -----------------------------------------------------------------------------
# App Configuration
# -----------------------------------------------------------------------------

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

# Default to SQLite for local dev, PostgreSQL in production
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    # Fly/Render sometimes require this fix for postgres URLs
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///rota.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'volunteer' or 'admin'
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"))
    active = db.Column(db.Boolean, default=True)

    team = db.relationship("Team", backref="users")
    shifts = db.relationship("Shift", backref="volunteer")

    def is_active(self):
        return self.active


class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)


class Store(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    address = db.Column(db.String(200))
    pickup_time = db.Column(db.String(50))
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"))

    team = db.relationship("Team", backref="stores")
    shifts = db.relationship("Shift", backref="store")


class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False)
    volunteer_id = db.Column(db.Integer, db.ForeignKey("user.id"))


# -----------------------------------------------------------------------------
# Login Loader
# -----------------------------------------------------------------------------


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------


@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("rota"))
    return redirect(url_for("login"))


# ---------------------------------------------------------------------


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].lower().strip()
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("rota"))

        flash("Invalid credentials")

    return render_template("login.html")


# ---------------------------------------------------------------------


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------


@app.route("/rota")
@login_required
def rota():
    today = datetime.utcnow().date()
    start_of_week = today - timedelta(days=today.weekday())
    dates = [start_of_week + timedelta(days=i) for i in range(7)]

    stores = Store.query.all()

    shifts = Shift.query.filter(
        Shift.date.in_(dates),
        Shift.store_id.in_([s.id for s in stores]),
    ).all()

    grid = {}

    for store in stores:
        grid[store] = {}

        for date in dates:
            shift = next(
                (s for s in shifts if s.store_id == store.id and s.date == date),
                None,
            )

            if not shift:
                shift = Shift(date=date, store_id=store.id)
                db.session.add(shift)

            grid[store][date] = shift

    db.session.commit()

    users = User.query.all()

    return render_template(
        "rota.html",
        grid=grid,
        dates=dates,
        stores=stores,
        users=users,
    )


# ---------------------------------------------------------------------


@app.route("/assign/<int:shift_id>", methods=["POST"])
@login_required
def assign(shift_id):
    shift = db.session.get(Shift, shift_id)

    if not shift:
        return redirect(url_for("rota"))

    if current_user.role == "admin":
        user_id = request.form.get("user_id")

        if user_id:
            shift.volunteer_id = int(user_id)
        else:
            shift.volunteer_id = None

    else:
        if shift.volunteer_id == current_user.id:
            shift.volunteer_id = None
        elif not shift.volunteer_id:
            shift.volunteer_id = current_user.id

    db.session.commit()

    return redirect(url_for("rota"))


# ---------------------------------------------------------------------


@app.route("/admin/users", methods=["GET", "POST"])
@login_required
def admin_users():
    if current_user.role != "admin":
        return redirect(url_for("rota"))

    if request.method == "POST":
        email = request.form["email"].lower().strip()
        password = request.form["password"]
        role = request.form["role"]
        team_name = request.form["team"]

        team = Team.query.filter_by(name=team_name).first()
        if not team:
            team = Team(name=team_name)
            db.session.add(team)

        user = User(
            email=email,
            password=generate_password_hash(password),
            role=role,
            team=team,
        )

        db.session.add(user)
        db.session.commit()

        flash("User added")

    users = User.query.all()
    teams = Team.query.all()

    return render_template("admin_users.html", users=users, teams=teams)


# -----------------------------------------------------------------------------
# CLI Setup Command (Optional)
# -----------------------------------------------------------------------------


@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("Database initialised.")
