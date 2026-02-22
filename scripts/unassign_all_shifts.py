from app import create_app
from app.extensions import db
from app.models import Shift

# Create the app context
app = create_app()
app.app_context().push()

# Unassign all shifts
shifts = Shift.query.all()
for shift in shifts:
    shift.volunteer_id = None

db.session.commit()

print("All shifts have been unassigned.")
