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
    # Default to a 2-week "from today" view for general users.
    window_mode = request.args.get("window", "from_today")
    is_admin = current_user.role == "admin"

    # For admins, default to the extended admin view when no explicit
    # admin_view parameter is provided. When admin_view is set via the
    # query string, respect that choice.
    admin_view_param = request.args.get("admin_view")
    if is_admin:
        if admin_view_param is None:
            admin_view = True
        else:
            admin_view = admin_view_param == "1"
    else:
        admin_view = False

    if admin_view:
        # Admin view shows a longer horizon (up to ~2 months) in the grid.
        start_date = today
        span_days = 60
    else:
        # Standard volunteer view can show either the current calendar
        # week or a rolling 14-day window from today.
        if window_mode == "from_today":
            start_date = today
            span_days = 14
        else:
            # Calendar week (Monday-Sunday containing today)
            start_date = today - timedelta(days=today.weekday())
            span_days = 7

    dates = [start_date + timedelta(days=i) for i in range(span_days)]
    weekday_names = [d.strftime("%A") for d in dates]
    show_dummy_stores = request.args.get("show_dummy", "1") == "1"

    all_stores = Store.query.order_by(Store.name.asc()).all()
    dummy_count = len([store for store in all_stores if is_dummy_store(store)])
    real_count = len(all_stores) - dummy_count

    if show_dummy_stores:
        stores = all_stores
    else:
        stores = [store for store in all_stores if not is_dummy_store(store)]

    # Load all existing shifts for the visible window in a single query and
    # build a dictionary for O(1) lookup by (store_id, date).
    store_ids = [s.id for s in stores]
    shifts = Shift.query.filter(
        Shift.date.in_(dates), Shift.store_id.in_(store_ids)
    ).all()

    shift_map = {(s.store_id, s.date): s for s in shifts}

    def store_collects_on_date(store, date):
        """Return True if this store is configured to collect on the given day."""

        weekday = date.weekday()  # Monday=0, Sunday=6
        flags = [
            getattr(store, "collects_monday", True),
            getattr(store, "collects_tuesday", True),
            getattr(store, "collects_wednesday", True),
            getattr(store, "collects_thursday", True),
            getattr(store, "collects_friday", True),
            getattr(store, "collects_saturday", True),
            getattr(store, "collects_sunday", True),
        ]
        return bool(flags[weekday])

    grid = {}
    for store in stores:
        grid[store] = {}
        for date in dates:
            if store_collects_on_date(store, date):
                grid[store][date] = shift_map.get((store.id, date))
            else:
                # No collection on this day for this store
                grid[store][date] = None

    # Build coverage summaries from today using existing Shift rows only.
    # Always compute 60 days so admins can see an extended view; the first
    # 14 days are used for the standard widget.
    coverage_window_days = 60
    coverage_start = today
    coverage_end = coverage_start + timedelta(days=coverage_window_days)

    coverage_dates_full = [
        coverage_start + timedelta(days=i) for i in range(coverage_window_days)
    ]

    coverage_query = (
        db.session.query(
            Shift.date.label("date"),
            func.count(Shift.id).label("total"),
            func.count(Shift.volunteer_id).label("assigned"),
        )
        .filter(Shift.date >= coverage_start, Shift.date < coverage_end)
        .group_by(Shift.date)
        .all()
    )

    coverage_map = {}
    for row in coverage_query:
        coverage_map[row.date] = {"total": row.total, "assigned": row.assigned}

    # First 14 days for the standard widget
    coverage_days_user = []
    user_window_days = 14
    for date in coverage_dates_full[:user_window_days]:
        stats = coverage_map.get(date, {"total": 0, "assigned": 0})
        status = classify_coverage(stats["assigned"], stats["total"])
        coverage_days_user.append(
            {
                "date": date,
                "total": stats["total"],
                "assigned": stats["assigned"],
                "status": status,
            }
        )

    # Full 60-day view chunked into rows of seven for admins.
    coverage_rows_admin = []
    if is_admin:
        coverage_days_full = []
        for date in coverage_dates_full:
            stats = coverage_map.get(date, {"total": 0, "assigned": 0})
            status = classify_coverage(stats["assigned"], stats["total"])
            coverage_days_full.append(
                {
                    "date": date,
                    "total": stats["total"],
                    "assigned": stats["assigned"],
                    "status": status,
                }
            )

        for i in range(0, len(coverage_days_full), 7):
            coverage_rows_admin.append(coverage_days_full[i : i + 7])

    # Only admins need the full user list for assignment; volunteers can
    # work with just their own identity.
    users = User.query.all() if is_admin else []

    return render_template(
        "rota.html",
        grid=grid,
        dates=dates,
        stores=stores,
        store_count=len(all_stores),
        dummy_store_count=dummy_count,
        real_store_count=real_count,
        show_dummy_stores=show_dummy_stores,
        admin_view=admin_view,
        window_mode=window_mode,
        users=users,
        week_start=dates[0],
        week_end=dates[-1],
        weekday_names=weekday_names,
        coverage_days_user=coverage_days_user,
        coverage_rows_admin=coverage_rows_admin,
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

    # Only consider shifts from today forwards for uncovered statistics
    today = datetime.now(timezone.utc).date()

    shifts_uncovered = (
        Shift.query.filter(Shift.volunteer_id.is_(None), Shift.date >= today)
        .order_by(Shift.date.asc())
        .all()
    )

    stores_uncovered = (
        db.session.query(Store, func.min(Shift.date).label("shift_date"))
        .join(Shift)
        .join(Team)
        .filter(Shift.volunteer_id.is_(None), Shift.date >= today)
        .group_by(Store.id)
        .order_by(order_dir(order_col))
        .all()
    )

    next_dir = "desc" if direction == "asc" else "asc"

    # Overall counts for dashboard header
    users = User.query.all()
    stores = Store.query.all()

    # Coverage summary from today for the admin dashboard (approx. next 2 months).
    window_days = 60
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

    # Chunk coverage days into rows of 7 for calendar-like display.
    coverage_rows = []
    for i in range(0, len(coverage_days), 7):
        coverage_rows.append(coverage_days[i : i + 7])

    return render_template(
        "admin_summary.html",
        shifts=shifts_uncovered,
        stores_uncovered=stores_uncovered,
        users=users,
        stores=stores,
        dir=next_dir,
        coverage_days=coverage_days,
        coverage_rows=coverage_rows,
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
