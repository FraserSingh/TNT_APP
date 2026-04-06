from datetime import datetime, timedelta, timezone

from .extensions import db
from .models import Shift

DEFAULT_SHIFT_DAYS = 7


def create_unassigned_shifts_for_store(store, days: int = DEFAULT_SHIFT_DAYS) -> None:
    """Create unassigned shifts for the given store for a contiguous range of days.

    Shifts are created starting from today (in UTC) for the given number of days.
    The caller is responsible for committing the session.
    """
    base_date = datetime.now(timezone.utc).date()

    for offset in range(days):
        shift_date = base_date + timedelta(days=offset)

        # Avoid creating duplicate shifts when this helper is called
        # multiple times or after adding a unique constraint.
        existing = Shift.query.filter_by(store_id=store.id, date=shift_date).first()
        if existing is None:
            db.session.add(
                Shift(
                    date=shift_date,
                    store_id=store.id,
                    volunteer_id=None,
                )
            )


def classify_coverage(assigned_shifts: int, total_shifts: int) -> str:
    """Return a RAG/grey status string based on coverage.

    - If there are no shifts on a day, return "grey".
    - Otherwise there are only two coverage states:
        * "green" when all shifts are covered (assigned == total > 0)
        * "red"   when at least one shift is uncovered (0 <= assigned < total)
    """

    if total_shifts <= 0:
        return "grey"

    if assigned_shifts >= total_shifts:
        return "green"

    return "red"
