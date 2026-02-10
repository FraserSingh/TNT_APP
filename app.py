from datetime import datetime, timedelta

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import asc, desc, func
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "your-secret-key"  # Change this
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///rota.db"

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)


# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'volunteer' or 'admin'
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"))
    team = db.relationship("Team", backref="users")
    is_active = db.Column(db.Boolean, default=True)

    def get_id(self):
        return str(self.id)

    def is_authenticated(self):
        return self.is_active

    def is_anonymous(self):
        return False

    def return_role(self):
        return self.role

    def return_team(self):
        return self.team


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


class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False)
    volunteer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    store = db.relationship("Store", backref="shifts")
    volunteer = db.relationship("User", backref="shifts")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def load_stores():
    return Store.query.all()


# Routes


@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("rota"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("rota"))
        flash("Invalid credentials")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/rota")
@login_required
def rota():
    # Get current week
    today = datetime.today().date()
    start_of_week = today - timedelta(days=today.weekday())  # Monday
    dates = [start_of_week + timedelta(days=i) for i in range(7)]
    # Get stores
    stores = load_stores()

    # Get shifts
    shifts = Shift.query.filter(
        Shift.date.in_(dates), Shift.store_id.in_([s.id for s in stores])
    ).all()
    # Create grid: dict store -> dict date -> shift
    grid = {}
    for store in stores:
        grid[store] = {}
        for date in dates:
            shift = next(
                (s for s in shifts if s.store_id == store.id and s.date == date), None
            )
            if not shift:
                shift = Shift(date=date, store_id=store.id)
                db.session.add(shift)
                db.session.commit()
            grid[store][date] = shift
    users = User.query.all()
    return render_template(
        "rota.html", grid=grid, dates=dates, stores=stores, users=users
    )


@app.route("/assign/<int:shift_id>", methods=["POST"])
@login_required
def assign(shift_id):
    shift = Shift.query.get(shift_id)
    if shift:
        if current_user.role == "admin":
            user_id = request.form.get("user_id")
            if user_id:
                user = User.query.get(int(user_id))
                if shift.volunteer:
                    shift.volunteer = None  # unassign if assigned
                else:
                    shift.volunteer = user  # assign selected user
            else:
                if shift.volunteer:
                    shift.volunteer = None  # unassign
        else:
            if shift.volunteer == current_user:
                shift.volunteer = None
            elif not shift.volunteer:
                shift.volunteer = current_user
    db.session.commit()
    return redirect(url_for("rota"))


@app.route("/admin/stores", methods=["GET", "POST"])
@login_required
def admin_stores():
    if current_user.role != "admin":
        return redirect(url_for("rota"))
    if request.method == "POST":
        if "csv" in request.files:
            file = request.files["csv"]
            if file and file.filename.endswith(".csv"):
                import csv
                import io

                stream = io.StringIO(file.read().decode("UTF8"), newline=None)
                csv_input = csv.reader(stream)
                for row in csv_input:
                    if len(row) >= 5:
                        team = Team.query.filter_by(name=row[4]).first()
                        if not team:
                            team = Team(name=row[4])
                            db.session.add(team)
                            db.session.commit()
                        store = Store(
                            name=row[0],
                            description=row[1],
                            address=row[2],
                            pickup_time=row[3],
                            team=team,
                        )
                        db.session.add(store)
                db.session.commit()
                flash("Stores imported from CSV")
        else:
            name = request.form["name"]
            description = request.form["description"]
            address = request.form["address"]
            pickup_time = request.form["pickup_time"]
            team_name = request.form["team"]
            team = Team.query.filter_by(name=team_name).first()
            if not team:
                team = Team(name=team_name)
                db.session.add(team)
                db.session.commit()
            store = Store(
                name=name,
                description=description,
                address=address,
                pickup_time=pickup_time,
                team=team,
            )
            db.session.add(store)
            db.session.commit()
            flash("Store added")
    stores = Store.query.all()
    teams = Team.query.all()
    return render_template("admin_stores.html", stores=stores, teams=teams)


@app.route("/admin/users", methods=["GET", "POST"])
@login_required
def admin_users():
    if current_user.role != "admin":
        return redirect(url_for("rota"))
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]
        team_name = request.form["team"]
        team = Team.query.filter_by(name=team_name).first()
        if not team:
            team = Team(name=team_name)
            db.session.add(team)
            db.session.commit()
        user = User(
            email=email, password=generate_password_hash(password), role=role, team=team
        )
        db.session.add(user)
        db.session.commit()
        flash("User added")
    users = User.query.all()
    teams = Team.query.all()
    return render_template("admin_users.html", users=users, teams=teams)


@app.route("/admin/summary")
@login_required
def admin_summary():
    if current_user.role != "admin":
        return redirect(url_for("rota"))

    sort = request.args.get("sort", "date")
    direction = request.args.get("dir", "asc")

    sort_columns = {
        "date": func.min(Shift.date),
        "store": Store.name,
        "team": Team.name,
    }

    order_col = sort_columns.get(sort, func.min(Shift.date))
    order_dir = asc if direction == "asc" else desc

    users = User.query.all()
    stores = Store.query.all()

    shifts_uncovered = (
        Shift.query
            .filter(Shift.volunteer_id.is_(None))
            .order_by(Shift.date.asc())
            .all()
    )

    stores_uncovered = (
        db.session.query(Store, func.min(Shift.date).label("next_date"))
            .join(Shift)
            .join(Team)
            .filter(Shift.volunteer_id.is_(None))
            .group_by(Store.id)
            .order_by(order_dir(order_col))
            .all()
    )

    next_dir = "desc" if direction == "asc" else "asc"

    return render_template(
        "admin_summary.html",
        users=users,
        stores=stores,
        shifts=shifts_uncovered,
        stores_uncovered=stores_uncovered,
        dir=next_dir,
    )



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        # Seed data
        if not Team.query.first():
            team1 = Team(name="Collection")
            team2 = Team(name="Hub")
            db.session.add(team1)
            db.session.add(team2)
            db.session.commit()

            import csv
            import os

            if os.path.exists("stores/store_data.csv"):
                with open("stores/store_data.csv", "r") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if len(row) >= 5:
                            team = Team.query.filter_by(name=row[4]).first()
                            if not team:
                                team = Team(name=row[4])
                                db.session.add(team)
                                db.session.commit()
                            store = Store(
                                name=row[0],
                                description=row[1],
                                address=row[2],
                                pickup_time=row[3],
                                team=team,
                            )
                            db.session.add(store)
                db.session.commit()

            user1 = User(
                email="volunteer@example.com",
                password=generate_password_hash("password"),
                role="volunteer",
                team=team1,
            )
            user2 = User(
                email="admin@example.com",
                password=generate_password_hash("password"),
                role="admin",
                team=team1,
            )
            db.session.add(user1)
            db.session.add(user2)
            db.session.commit()
    app.run(debug=True)
