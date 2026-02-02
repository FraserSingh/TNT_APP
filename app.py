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
    is_active = db.Column(db.Boolean, default=True)

    def get_id(self):
        return str(self.id)
    def is_authenticated(self):
        return self.is_active
    def is_anonymous(self):
        return False
    def is_active(self):
        return self.is_active
    def return_role(self):
        return self.role
    def return_team(self):
        return self.team

class Admin(User):
    __tablename__ = 'admin'
    id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    role = db.Column(db.String(50), nullable=False, default='admin')

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
    # Get stores for user's team or all for admin
    if current_user.role == 'admin':
        stores = Store.query.all()
    else:
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
    if shift and (current_user.role == 'admin' or shift.store.team_id == current_user.team_id):
        if shift.volunteer == current_user:
            shift.volunteer = None
        elif not shift.volunteer:
            shift.volunteer = current_user
        db.session.commit()
    return redirect(url_for('rota'))

@app.route('/admin/stores', methods=['GET', 'POST'])
@login_required
def admin_stores():
    if current_user.role != 'admin':
        return redirect(url_for('rota'))
    if request.method == 'POST':
        if 'csv' in request.files:
            file = request.files['csv']
            if file and file.filename.endswith('.csv'):
                import csv, io
                stream = io.StringIO(file.read().decode("UTF8"), newline=None)
                csv_input = csv.reader(stream)
                for row in csv_input:
                    if len(row) >= 5:
                        team = Team.query.filter_by(name=row[4]).first()
                        if not team:
                            team = Team(name=row[4])
                            db.session.add(team)
                            db.session.commit()
                        store = Store(name=row[0], description=row[1], address=row[2], pickup_time=row[3], team=team)
                        db.session.add(store)
                db.session.commit()
                flash('Stores imported from CSV')
        else:
            name = request.form['name']
            description = request.form['description']
            address = request.form['address']
            pickup_time = request.form['pickup_time']
            team_name = request.form['team']
            team = Team.query.filter_by(name=team_name).first()
            if not team:
                team = Team(name=team_name)
                db.session.add(team)
                db.session.commit()
            store = Store(name=name, description=description, address=address, pickup_time=pickup_time, team=team)
            db.session.add(store)
            db.session.commit()
            flash('Store added')
    stores = Store.query.all()
    teams = Team.query.all()
    return render_template('admin_stores.html', stores=stores, teams=teams)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Seed data
        if not Team.query.first():
            team1 = Team(name='Collection')
            team2 = Team(name='Hub')
            db.session.add(team1)
            db.session.add(team2)
            db.session.commit()
            
            store1 = Store(name='Store A', description='Pick up food donations', address='123 Main St', pickup_time='10:00 AM', team=team1)
            store2 = Store(name='Store B', description='Collect supplies', address='456 Elm St', pickup_time='11:00 AM', team=team1)
            db.session.add(store1)
            db.session.add(store2)
            
            user1 = User(email='volunteer@example.com', password=generate_password_hash('password'), role='volunteer', team=team1)
            user2 = User(email='admin@example.com', password=generate_password_hash('password'), role='admin', team=team1)
            db.session.add(user1)
            db.session.add(user2)
            db.session.commit()
    app.run(debug=True)