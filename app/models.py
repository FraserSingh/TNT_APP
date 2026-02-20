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

    team = db.relationship("Team", backref="stores")
    shifts = db.relationship("Shift", backref="store")


class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("store.id"), nullable=False)
    volunteer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
