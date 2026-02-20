from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import Team, User

app = create_app()
app.app_context().push()
admin = User.query.filter_by(email="admin@example.com").first()
if admin:
    db.session.delete(admin)
    db.session.commit()

team = Team.query.first()  # or create a new team if needed

new_admin = User(
    email="admin@example.com",
    password=generate_password_hash("newpassword123"),
    role="admin",
    team=team,
)
db.session.add(new_admin)
db.session.commit()
