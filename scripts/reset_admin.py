from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import Team, User

app = create_app()
with app.app_context():
    admin = User.query.filter_by(email="admin@example.com").first()
    if not admin:
        team = Team.query.first()
        admin = User(email="admin@example.com", role="admin", team=team)
        db.session.add(admin)
    admin.password = generate_password_hash(
        "newpassword123"
    )  # SET YOUR NEW PASSWORD HERE
    db.session.commit()
    print("Admin password reset!")
