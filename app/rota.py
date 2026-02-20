from datetime import datetime, timedelta, timezone

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import asc, desc, func

from .extensions import db
from .models import Shift, Store, Team, User

rota_bp = Blueprint("rota", __name__)

DUMMY_STORE_NAMES = {
    "Store Alpha",
    "Store Bravo",
    "Store Charlie",
    "Store Delta",
    "Store Echo",
}


def is_dummy_store(store):
    return store.name in DUMMY_STORE_NAMES


def ensure_dummy_stores():
    if Store.query.first():
        return

    default_team = Team.query.filter_by(name="COLLECTION").first()
    if not default_team:
        default_team = Team(name="COLLECTION")
        db.session.add(default_team)
        db.session.flush()

    dummy_stores = [
        ("Store Alpha", "08:30 PM"),
        ("Store Bravo", "09:00 PM"),
        ("Store Charlie", "09:30 PM"),
        ("Store Delta", "10:00 PM"),
        ("Store Echo", "10:30 PM"),
    ]

    for store_name, pickup_time in dummy_stores:
        db.session.add(
            Store(
                name=store_name,
                description="Demo store",
                pickup_time=pickup_time,
                team=default_team,
            )
        )

    db.session.commit()


@rota_bp.route("/")
@login_required
def rota():
    ensure_dummy_stores()

    today = datetime.now(timezone.utc).date()
    start_of_week = today - timedelta(days=today.weekday())
    dates = [start_of_week + timedelta(days=i) for i in range(7)]
    weekday_names = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    show_dummy_stores = request.args.get("show_dummy", "1") == "1"

    all_stores = Store.query.order_by(Store.name.asc()).all()
    dummy_count = len([store for store in all_stores if is_dummy_store(store)])
    real_count = len(all_stores) - dummy_count

    if show_dummy_stores:
        stores = all_stores
    else:
        stores = [store for store in all_stores if not is_dummy_store(store)]

    shifts = Shift.query.filter(Shift.date.in_(dates)).all()

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
        store_count=len(all_stores),
        dummy_store_count=dummy_count,
        real_store_count=real_count,
        show_dummy_stores=show_dummy_stores,
        users=users,
        week_start=dates[0],
        week_end=dates[-1],
        weekday_names=weekday_names,
    )


# NOTE untested, copied from previous branch
# allow drop down assignment in rota page (drop down from template html)
@rota_bp.route("/assign/<int:shift_id>", methods=["POST"])
@login_required
def assign(shift_id):
    shift = Shift.query.get_or_404(shift_id)

    if current_user.role == "admin":
        user_id = request.form.get("user_id")

        if user_id:
            user = User.query.get(int(user_id))
            shift.volunteer = user
        else:
            shift.volunteer = None

    else:
        # normal user behaviour
        if shift.volunteer == current_user:
            shift.volunteer = None
        elif not shift.volunteer:
            shift.volunteer = current_user

    db.session.commit()
    return redirect(url_for("rota.rota"))


# Show a summary of unassigned shifts for the earliest date in the week
@rota_bp.route("/summary")
@login_required
def admin_summary():
    if current_user.role != "admin":
        return redirect(url_for("rota.rota"))

    sort = request.args.get("sort", "date")
    direction = request.args.get("dir", "asc")

    sort_columns = {
        "date": func.min(Shift.date),
        "store": Store.name,
        "team": Team.name,
    }

    order_col = sort_columns.get(sort, func.min(Shift.date))
    order_dir = asc if direction == "asc" else desc

    shifts_uncovered = (
        Shift.query.filter(Shift.volunteer_id.is_(None))
        .order_by(Shift.date.asc())
        .all()
    )

    stores_uncovered = (
        db.session.query(Store, func.min(Shift.date).label("shift_date"))
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
        shifts=shifts_uncovered,
        stores_uncovered=stores_uncovered,
        dir=next_dir,
    )
