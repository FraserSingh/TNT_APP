"""make pickup time nullable time

Revision ID: 9d9d0f5d6d2d
Revises: aa05721dfca4
Create Date: 2026-04-06 00:00:00.000000

"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9d9d0f5d6d2d"
down_revision = "aa05721dfca4"
branch_labels = None
depends_on = None


def _parse_pickup_time(value):
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    for time_format in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.strptime(text, time_format).time()
        except ValueError:
            continue

    return None


def _format_pickup_time(value):
    parsed = _parse_pickup_time(value)
    return parsed.strftime("%H:%M:%S") if parsed else None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {column["name"] for column in inspector.get_columns("store")}

    if "pickup_time_tmp" not in columns:
        op.add_column("store", sa.Column("pickup_time_tmp", sa.Time(), nullable=True))
        columns.add("pickup_time_tmp")

    if "pickup_time" in columns:
        rows = list(
            connection.execute(sa.text("SELECT id, pickup_time FROM store")).mappings()
        )

        for row in rows:
            parsed_time = _format_pickup_time(row["pickup_time"])
            connection.execute(
                sa.text(
                    "UPDATE store SET pickup_time_tmp = :pickup_time WHERE id = :id"
                ),
                {"pickup_time": parsed_time, "id": row["id"]},
            )

    if "pickup_time_tmp" in columns:
        with op.batch_alter_table("store", schema=None) as batch_op:
            if "pickup_time" in columns:
                batch_op.drop_column("pickup_time")
            batch_op.alter_column(
                "pickup_time_tmp",
                existing_type=sa.Time(),
                nullable=True,
                new_column_name="pickup_time",
            )


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {column["name"] for column in inspector.get_columns("store")}

    if "pickup_time_tmp" not in columns:
        op.add_column(
            "store", sa.Column("pickup_time_tmp", sa.String(length=50), nullable=True)
        )
        columns.add("pickup_time_tmp")

    if "pickup_time" in columns:
        rows = list(
            connection.execute(sa.text("SELECT id, pickup_time FROM store")).mappings()
        )

        for row in rows:
            value = _format_pickup_time(row["pickup_time"])
            connection.execute(
                sa.text(
                    "UPDATE store SET pickup_time_tmp = :pickup_time WHERE id = :id"
                ),
                {"pickup_time": value, "id": row["id"]},
            )

    if "pickup_time_tmp" in columns:
        with op.batch_alter_table("store", schema=None) as batch_op:
            if "pickup_time" in columns:
                batch_op.drop_column("pickup_time")
            batch_op.alter_column(
                "pickup_time_tmp",
                existing_type=sa.String(length=50),
                nullable=True,
                new_column_name="pickup_time",
            )
