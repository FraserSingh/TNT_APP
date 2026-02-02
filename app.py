from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'  # Change this
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rota.db'

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'volunteer' or 'admin'
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'))
    team = db.relationship('Team', backref='users')

class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class Store(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    address = db.Column(db.String(200))
    pickup_time = db.Column(db.String(50))
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'))
    team = db.relationship('Team', backref='stores')

class Shift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('store.id'), nullable=False)
    volunteer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    store = db.relationship('Store', backref='shifts')
    volunteer = db.relationship('User', backref='shifts')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

# Routes

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('rota'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('rota'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/rota')
@login_required
def rota():
    # Get current week
    today = datetime.today().date()
    start_of_week = today - timedelta(days=today.weekday())  # Monday
    dates = [start_of_week + timedelta(days=i) for i in range(7)]
    # Get stores for user's team
    stores = Store.query.filter_by(team_id=current_user.team_id).all()
    # Get shifts
    shifts = Shift.query.filter(Shift.date.in_(dates), Shift.store_id.in_([s.id for s in stores])).all()
    # Create grid: dict store -> dict date -> shift
    grid = {}
    for store in stores:
        grid[store] = {}
        for date in dates:
            shift = next((s for s in shifts if s.store_id == store.id and s.date == date), None)
            if not shift:
                shift = Shift(date=date, store_id=store.id)
                db.session.add(shift)
                db.session.commit()
            grid[store][date] = shift
    return render_template('rota.html', grid=grid, dates=dates, stores=stores)

@app.route('/assign/<int:shift_id>', methods=['POST'])
@login_required
def assign(shift_id):
    shift = Shift.query.get(shift_id)
    if shift and shift.store.team_id == current_user.team_id:
        if shift.volunteer == current_user:
            shift.volunteer = None
        elif not shift.volunteer:
            shift.volunteer = current_user
        db.session.commit()
    return redirect(url_for('rota'))
    with app.app_context():
        db.create_all()
    app.run(debug=True)