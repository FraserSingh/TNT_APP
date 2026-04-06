from datetime import date, datetime, timedelta, timezone

from .extensions import db
from .models import Shift

DEFAULT_SHIFT_DAYS = 7


def store_collects_on_date(store, shift_date: date) -> bool:
    """Return True when a store collects on the given date."""

    flags = [
        getattr(store, "collects_monday", True),
        getattr(store, "collects_tuesday", True),
        getattr(store, "collects_wednesday", True),
        getattr(store, "collects_thursday", True),
        getattr(store, "collects_friday", True),
        getattr(store, "collects_saturday", True),
        getattr(store, "collects_sunday", True),
    ]
    return bool(flags[shift_date.weekday()])


def create_unassigned_shifts_for_store(
    store,
    days: int = DEFAULT_SHIFT_DAYS,
    start_date: date | None = None,
) -> int:
    """Create unassigned shifts for the given store for a contiguous range of days.

    Shifts are created starting from today (in UTC) for the given number of days.
    The caller is responsible for committing the session.
    """
    if days <= 0:
        return 0

    base_date = start_date or datetime.now(timezone.utc).date()
    end_date = base_date + timedelta(days=days - 1)

    existing_dates = {
        shift.date
        for shift in Shift.query.filter(
            Shift.store_id == store.id,
            Shift.date >= base_date,
            Shift.date <= end_date,
        ).all()
    }

    created = 0

    for offset in range(days):
        shift_date = base_date + timedelta(days=offset)
        if not store_collects_on_date(store, shift_date):
            continue

        # Avoid creating duplicate shifts when this helper is called
        # multiple times or after adding a unique constraint.
        if shift_date not in existing_dates:
            db.session.add(
                Shift(
                    date=shift_date,
                    store_id=store.id,
                    volunteer_id=None,
                )
            )
            created += 1

    return created


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
