from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import Shift, Store, Team, User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users", methods=["GET", "POST"])
@login_required
def users():
    if current_user.role != "admin":
        return redirect(url_for("rota.rota"))

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


@admin_bp.route("/users/edit/<int:user_id>", methods=["GET", "POST"])
@login_required
def edit_user(user_id):
    if current_user.role != "admin":
        return redirect(url_for("rota.rota"))

    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        user.email = request.form["email"].lower().strip()
        user.role = request.form["role"]

        team_name = request.form["team"]
        team = Team.query.filter_by(name=team_name).first()
        if not team:
            team = Team(name=team_name)
            db.session.add(team)
            db.session.commit()
        user.team = team

        password = request.form.get("password", "").strip()
        if password:
            user.password = generate_password_hash(password)

        db.session.commit()
        flash("User updated")
        return redirect(url_for("admin.users"))

    teams = Team.query.all()
    return render_template("admin_edit_user.html", user=user, teams=teams)


@admin_bp.route("/users/delete/<int:user_id>", methods=["POST"])
@login_required
def delete_user(user_id):
    if current_user.role != "admin":
        return redirect(url_for("rota.rota"))

    user = User.query.get_or_404(user_id)

    # Unassign this user's shifts instead of deleting them
    for shift in list(user.shifts):
        shift.volunteer = None

    db.session.delete(user)
    db.session.commit()
    flash("User deleted")
    return redirect(url_for("admin.users"))


@admin_bp.route("/stores", methods=["GET", "POST"])
@login_required
def stores():
    if current_user.role != "admin":
        return redirect(url_for("rota.rota"))

    if request.method == "POST":
        # Add new store
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
                        db.session.flush()

                        # Create unassigned shifts for the new store
                        for i in range(7):  # Create shifts for a week
                            shift_date = datetime.utcnow().date() + timedelta(days=i)
                            db.session.add(
                                Shift(
                                    date=shift_date,
                                    store_id=store.id,
                                    volunteer_id=None,  # Ensure shifts are unassigned
                                )
                            )

                db.session.commit()
                flash("Stores imported from CSV")
        else:
            # Add store via form
            name = request.form["name"]
            description = request.form.get("description")
            address = request.form.get("address")
            pickup_time = request.form.get("pickup_time")
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
            db.session.flush()

            # Create unassigned shifts for the new store
            for i in range(7):  # Create shifts for a week
                shift_date = datetime.utcnow().date() + timedelta(days=i)
                db.session.add(
                    Shift(
                        date=shift_date,
                        store_id=store.id,
                        volunteer_id=None,  # Ensure shifts are unassigned
                    )
                )

            db.session.commit()
            flash("Store added")

    stores = Store.query.all()
    teams = Team.query.all()
    return render_template("admin_stores.html", stores=stores, teams=teams)


# --- Optional: Edit / Delete endpoint ---
@admin_bp.route("/stores/edit/<int:store_id>", methods=["GET", "POST"])
@login_required
def edit_store(store_id):
    if current_user.role != "admin":
        return redirect(url_for("rota.rota"))

    store = Store.query.get_or_404(store_id)
    if request.method == "POST":
        store.name = request.form["name"]
        store.description = request.form.get("description")
        store.address = request.form.get("address")
        store.pickup_time = request.form.get("pickup_time")
        team_name = request.form["team"]
        team = Team.query.filter_by(name=team_name).first()
        if not team:
            team = Team(name=team_name)
            db.session.add(team)
            db.session.commit()
        store.team = team
        db.session.commit()
        flash("Store updated")
        return redirect(url_for("admin.stores"))

    teams = Team.query.all()
    return render_template("edit_store.html", store=store, teams=teams)


@admin_bp.route("/stores/delete/<int:store_id>", methods=["POST"])
@login_required
def delete_store(store_id):
    if current_user.role != "admin":
        return redirect(url_for("rota.rota"))

    store = Store.query.get_or_404(store_id)

    # Delete associated shifts first to satisfy foreign key constraints
    for shift in list(store.shifts):
        db.session.delete(shift)

    db.session.delete(store)
    db.session.commit()
    flash("Store deleted")
    return redirect(url_for("admin.stores"))
