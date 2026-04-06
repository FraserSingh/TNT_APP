from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import Store, Team, User
from .shift_utils import create_unassigned_shifts_for_store

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def parse_pickup_time(raw_value):
    value = (raw_value or "").strip()
    if not value:
        return None

    for time_format in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.strptime(value, time_format).time()
        except ValueError:
            continue

    raise ValueError("Collection time must be in HH:MM or H:MM AM/PM format.")


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

        try:
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
        except SQLAlchemyError:
            db.session.rollback()
            flash("An error occurred while adding the user. Please try again.")

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
        try:
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
        except SQLAlchemyError:
            db.session.rollback()
            flash("An error occurred while updating the user. Please try again.")

    teams = Team.query.all()
    return render_template("admin_edit_user.html", user=user, teams=teams)


@admin_bp.route("/users/delete/<int:user_id>", methods=["POST"])
@login_required
def delete_user(user_id):
    if current_user.role != "admin":
        return redirect(url_for("rota.rota"))

    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("You cannot delete your own account.")
        return redirect(url_for("admin.users"))

    try:
        # Unassign this user's shifts instead of deleting them
        for shift in list(user.shifts):
            shift.volunteer = None

        db.session.delete(user)
        db.session.commit()
        flash("User deleted")
    except SQLAlchemyError:
        db.session.rollback()
        flash("An error occurred while deleting the user. Please try again.")
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

                try:
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
                                pickup_time=parse_pickup_time(row[3]),
                                team=team,
                            )
                            db.session.add(store)
                            db.session.flush()

                            # Create unassigned shifts for the new store
                            create_unassigned_shifts_for_store(store)

                    db.session.commit()
                    flash("Stores imported from CSV")
                except ValueError as exc:
                    db.session.rollback()
                    flash(str(exc))
                except SQLAlchemyError:
                    db.session.rollback()
                    flash(
                        "An error occurred while importing stores. "
                        "Please check your file and try again."
                    )
        else:
            # Add store via form
            name = request.form["name"]
            description = request.form.get("description")
            address = request.form.get("address")
            pickup_time_raw = request.form.get("pickup_time")
            team_name = request.form["team"]

            try:
                pickup_time = parse_pickup_time(pickup_time_raw)

                team = Team.query.filter_by(name=team_name).first()
                if not team:
                    team = Team(name=team_name)
                    db.session.add(team)
                    db.session.commit()

                # Days of week this store collects on; default to all days
                collects_monday = bool(request.form.get("collects_monday", True))
                collects_tuesday = bool(request.form.get("collects_tuesday", True))
                collects_wednesday = bool(request.form.get("collects_wednesday", True))
                collects_thursday = bool(request.form.get("collects_thursday", True))
                collects_friday = bool(request.form.get("collects_friday", True))
                collects_saturday = bool(request.form.get("collects_saturday", True))
                collects_sunday = bool(request.form.get("collects_sunday", True))

                store = Store(
                    name=name,
                    description=description,
                    address=address,
                    pickup_time=pickup_time,
                    team=team,
                    collects_monday=collects_monday,
                    collects_tuesday=collects_tuesday,
                    collects_wednesday=collects_wednesday,
                    collects_thursday=collects_thursday,
                    collects_friday=collects_friday,
                    collects_saturday=collects_saturday,
                    collects_sunday=collects_sunday,
                )
                db.session.add(store)
                db.session.flush()

                # Create unassigned shifts for the new store
                create_unassigned_shifts_for_store(store)

                db.session.commit()
                flash("Store added")
            except ValueError as exc:
                db.session.rollback()
                flash(str(exc))
            except SQLAlchemyError:
                db.session.rollback()
                flash("An error occurred while adding the store. Please try again.")

    # Simple server-side sorting for the stores table.
    sort_key = request.args.get("sort", "name")
    sort_columns = {
        "name": Store.name,
        "address": Store.address,
        "pickup_time": Store.pickup_time,
    }
    sort_column = sort_columns.get(sort_key, Store.name)

    stores = Store.query.order_by(sort_column.asc()).all()
    teams = Team.query.all()
    return render_template(
        "admin_stores.html", stores=stores, teams=teams, sort=sort_key
    )


# --- Optional: Edit / Delete endpoint ---
@admin_bp.route("/stores/edit/<int:store_id>", methods=["GET", "POST"])
@login_required
def edit_store(store_id):
    if current_user.role != "admin":
        return redirect(url_for("rota.rota"))

    store = Store.query.get_or_404(store_id)
    if request.method == "POST":
        try:
            store.name = request.form["name"]
            store.description = request.form.get("description")
            store.address = request.form.get("address")
            store.pickup_time = parse_pickup_time(request.form.get("pickup_time"))

            # Update collection days; unchecked boxes will be absent
            store.collects_monday = bool(request.form.get("collects_monday"))
            store.collects_tuesday = bool(request.form.get("collects_tuesday"))
            store.collects_wednesday = bool(request.form.get("collects_wednesday"))
            store.collects_thursday = bool(request.form.get("collects_thursday"))
            store.collects_friday = bool(request.form.get("collects_friday"))
            store.collects_saturday = bool(request.form.get("collects_saturday"))
            store.collects_sunday = bool(request.form.get("collects_sunday"))
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
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc))
        except SQLAlchemyError:
            db.session.rollback()
            flash("An error occurred while updating the store. Please try again.")

    teams = Team.query.all()
    return render_template("edit_store.html", store=store, teams=teams)


@admin_bp.route("/stores/delete/<int:store_id>", methods=["POST"])
@login_required
def delete_store(store_id):
    if current_user.role != "admin":
        return redirect(url_for("rota.rota"))

    store = Store.query.get_or_404(store_id)

    try:
        # Delete associated shifts first to satisfy foreign key constraints
        for shift in list(store.shifts):
            db.session.delete(shift)

        db.session.delete(store)
        db.session.commit()
        flash("Store deleted")
    except SQLAlchemyError:
        db.session.rollback()
        flash("An error occurred while deleting the store. Please try again.")
    return redirect(url_for("admin.stores"))


@admin_bp.route("/generate-shifts", methods=["POST"])
@login_required
def generate_shifts():
    if current_user.role != "admin":
        return redirect(url_for("rota.rota"))

    start_date_raw = request.form.get("start_date", "").strip()
    days_raw = request.form.get("days", "28").strip()

    try:
        if start_date_raw:
            start_date = datetime.strptime(start_date_raw, "%Y-%m-%d").date()
        else:
            start_date = datetime.now(timezone.utc).date()

        days = int(days_raw)
        if days < 1 or days > 84:
            raise ValueError("Shift generation window must be between 1 and 84 days.")

        total_created = 0
        stores = Store.query.order_by(Store.name.asc()).all()
        for store in stores:
            total_created += create_unassigned_shifts_for_store(
                store,
                days=days,
                start_date=start_date,
            )

        db.session.commit()
        flash(
            f"Generated {total_created} shifts starting from {start_date.isoformat()}."
        )
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc))
    except SQLAlchemyError:
        db.session.rollback()
        flash("An error occurred while generating shifts. Please try again.")

    return redirect(url_for("rota.admin_summary"))
