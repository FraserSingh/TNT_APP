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
        db.session.add(
            Shift(
                date=shift_date,
                store_id=store.id,
                volunteer_id=None,
            )
        )
