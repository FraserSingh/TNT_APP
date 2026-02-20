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
