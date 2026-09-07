import sqlalchemy as sa
from alembic import op

revision = "728f8c87b179"
down_revision = "2f6a45fdaf5e"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "carts",
        "status",
        existing_type=sa.TEXT(),
        type_=sa.Enum(
            "active", "checked_out", "abandoned", name="cartstatus", native_enum=False
        ),
        existing_nullable=False,
        existing_server_default=sa.text("'active'::text"),
    )
    op.alter_column(
        "payments",
        "status",
        existing_type=sa.TEXT(),
        type_=sa.Enum(
            "pending", "succeeded", "failed", name="paymentstatus", native_enum=False
        ),
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        "payments",
        "status",
        existing_type=sa.Enum(
            "pending", "succeeded", "failed", name="paymentstatus", native_enum=False
        ),
        type_=sa.TEXT(),
        existing_nullable=False,
    )
    op.alter_column(
        "carts",
        "status",
        existing_type=sa.Enum(
            "active", "checked_out", "abandoned", name="cartstatus", native_enum=False
        ),
        type_=sa.TEXT(),
        existing_nullable=False,
        existing_server_default=sa.text("'active'::text"),
    )
