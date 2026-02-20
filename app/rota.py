from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template
from flask_login import login_required

from .extensions import db
from .models import Shift, Store, User

rota_bp = Blueprint("rota", __name__)


@rota_bp.route("/")
@login_required
def rota():
    today = datetime.now(timezone.utc).date()
    start_of_week = today - timedelta(days=today.weekday())
    dates = [start_of_week + timedelta(days=i) for i in range(7)]

    stores = Store.query.all()
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
        "rota.html", grid=grid, dates=dates, stores=stores, users=users
    )

# NOTE untested, copied from previous branch 
# allow drop down assignment in rota page (drop down from template html)
@rota_bp.route("/assign/<int:shift_id>", methods=["POST"])")
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

# Show a summary of unassigned shifts for the earliest date in the week 
@rota_bp.route("/summary", methods=["POST"])")
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
        db.session.query(Store, func.min(Shift.date).label("shift_date"))
            .join(Shift)
            .join(Team)
            .filter(Shift.date.is_(datetime.today().date()))
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
