import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import asc, desc, func

from .extensions import db
from .models import Shift, Store, Team, User
from .shift_utils import classify_coverage, create_unassigned_shifts_for_store

logger = logging.getLogger(__name__)

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
        store = Store(
            name=store_name,
            description="Demo store",
            pickup_time=pickup_time,
            team=default_team,
        )
        db.session.add(store)
        db.session.flush()

        # Create unassigned dummy shifts for the store
        create_unassigned_shifts_for_store(store)

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

    # Build 14-day coverage from today using existing Shift rows only.
    window_days = 14
    window_start = today
    window_end = window_start + timedelta(days=window_days)

    window_dates = [window_start + timedelta(days=i) for i in range(window_days)]

    coverage_query = (
        db.session.query(
            Shift.date.label("date"),
            func.count(Shift.id).label("total"),
            func.count(Shift.volunteer_id).label("assigned"),
        )
        .filter(Shift.date >= window_start, Shift.date < window_end)
        .group_by(Shift.date)
        .all()
    )

    coverage_map = {}
    for row in coverage_query:
        coverage_map[row.date] = {"total": row.total, "assigned": row.assigned}

    coverage_days = []
    for date in window_dates:
        stats = coverage_map.get(date, {"total": 0, "assigned": 0})
        status = classify_coverage(stats["assigned"], stats["total"])
        coverage_days.append(
            {
                "date": date,
                "total": stats["total"],
                "assigned": stats["assigned"],
                "status": status,
            }
        )

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
        coverage_days=coverage_days,
    )


# Show a summary of unassigned shifts for the earliest date in the week
@rota_bp.route("/summary")
@login_required
def admin_summary():
    logger.debug(f"Current user role: {current_user.role}")  # Log the current user role
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

    # Overall counts for dashboard header
    users = User.query.all()
    stores = Store.query.all()

    # 14-day coverage summary from today for the admin dashboard.
    today = datetime.now(timezone.utc).date()
    window_days = 14
    window_start = today
    window_end = window_start + timedelta(days=window_days)

    window_dates = [window_start + timedelta(days=i) for i in range(window_days)]

    coverage_query = (
        db.session.query(
            Shift.date.label("date"),
            func.count(Shift.id).label("total"),
            func.count(Shift.volunteer_id).label("assigned"),
        )
        .filter(Shift.date >= window_start, Shift.date < window_end)
        .group_by(Shift.date)
        .all()
    )

    coverage_map = {}
    for row in coverage_query:
        coverage_map[row.date] = {"total": row.total, "assigned": row.assigned}

    coverage_days = []
    total_unassigned_14d = 0

    for date in window_dates:
        stats = coverage_map.get(date, {"total": 0, "assigned": 0})
        status = classify_coverage(stats["assigned"], stats["total"])
        unassigned = stats["total"] - stats["assigned"]
        total_unassigned_14d += max(unassigned, 0)
        coverage_days.append(
            {
                "date": date,
                "total": stats["total"],
                "assigned": stats["assigned"],
                "unassigned": unassigned,
                "status": status,
            }
        )

    return render_template(
        "admin_summary.html",
        shifts=shifts_uncovered,
        stores_uncovered=stores_uncovered,
        users=users,
        stores=stores,
        dir=next_dir,
        coverage_days=coverage_days,
        total_unassigned_14d=total_unassigned_14d,
    )


@rota_bp.route("/toggle_shift/<int:shift_id>", methods=["POST"])
@login_required
def toggle_shift(shift_id):
    shift = Shift.query.get_or_404(shift_id)

    logger.debug(f"Current user role: {current_user.role}")  # Log the current user role

    if current_user.role == "admin":
        # Admin can assign or unassign any user to/from the shift
        user_id = request.form.get("user_id")
        if user_id:
            try:
                user_id_int = int(user_id)
            except (TypeError, ValueError):
                logger.warning(
                    f"Invalid user_id provided for shift {shift_id}: {user_id}"
                )
                return "Invalid user specified.", 400
            user = User.query.get(user_id_int)
            if user is None:
                logger.warning(
                    f"Nonexistent user_id provided for shift {shift_id}: {user_id_int}"
                )
                return "User not found.", 404
            shift.volunteer = user
        else:
            shift.volunteer = None
    else:
        # General user can only assign/unassign themselves, and only on their own shifts
        user_id = request.form.get("user_id")

        # If the shift is already assigned to someone else, deny the action
        if shift.volunteer and shift.volunteer != current_user:
            return "Shift is already assigned to another volunteer.", 403

        desired_volunteer = None

        if user_id is not None:
            user_id = user_id.strip()

        if user_id:
            # Non-admins may only select themselves
            try:
                user_id_int = int(user_id)
            except (TypeError, ValueError):
                logger.warning(
                    f"Invalid user_id provided for shift {shift_id}: {user_id}"
                )
                return "Invalid user specified.", 400

            if user_id_int != current_user.id:
                # Attempt to assign a different user is not allowed
                return "You may only assign or unassign yourself.", 403

            desired_volunteer = current_user

        # If user_id is empty or not provided, we treat it as "Unassigned"
        shift.volunteer = desired_volunteer

    db.session.commit()
    return redirect(url_for("rota.rota"))
