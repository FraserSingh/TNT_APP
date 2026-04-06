from flask_login import UserMixin

from .extensions import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"))
    active = db.Column(db.Boolean, default=True)

    team = db.relationship("Team", backref="users")
    shifts = db.relationship("Shift", backref="volunteer")

    def is_active(self):
        return self.active


class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)


class Store(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    address = db.Column(db.String(200))
    pickup_time = db.Column(db.String(50))
    team_id = db.Column(db.Integer, db.ForeignKey("team.id"))

    # Days of week when this store has collections. Defaults to every day
    # for backward compatibility; admins can refine this in the Stores panel.
    collects_monday = db.Column(db.Boolean, nullable=False, default=True)
    collects_tuesday = db.Column(db.Boolean, nullable=False, default=True)
    collects_wednesday = db.Column(db.Boolean, nullable=False, default=True)
    collects_thursday = db.Column(db.Boolean, nullable=False, default=True)
    collects_friday = db.Column(db.Boolean, nullable=False, default=True)
    collects_saturday = db.Column(db.Boolean, nullable=False, default=True)
    collects_sunday = db.Column(db.Boolean, nullable=False, default=True)

    team = db.relationship("Team", backref="stores")
    shifts = db.relationship("Shift", backref="store")


class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False)
    volunteer_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    __table_args__ = (
        # Speed up common lookups and aggregations by date/store/volunteer
        db.Index("ix_shift_date_store_vol", "date", "store_id", "volunteer_id"),
        # Ensure at most one shift per store per day
        db.UniqueConstraint("date", "store_id", name="uq_shift_date_store"),
    )
