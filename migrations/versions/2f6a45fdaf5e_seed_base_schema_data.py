from alembic import op
from faker import Faker

from app.models import Cart, CartItem, CartStatus, Product, User, UserPaymentMethod

revision = "2f6a45fdaf5e"
down_revision = "8cdb939b7c74"
branch_labels = None
depends_on = None

fake = Faker()
Faker.seed(0)

USER_ID = fake.uuid4(cast_to=None)
PRODUCT_ID = fake.uuid4(cast_to=None)
CART_ID = fake.uuid4(cast_to=None)
PAYMENT_METHOD_ID = fake.uuid4(cast_to=None)


def upgrade():
    op.bulk_insert(
        User.__table__,
        [{"id": USER_ID, "email": fake.email(), "name": fake.name()}],
    )

    price = fake.pydecimal(
        left_digits=3, right_digits=2, positive=True, min_value=5, max_value=200
    )

    op.bulk_insert(
        Product.__table__,
        [
            {
                "id": PRODUCT_ID,
                "name": fake.word().capitalize(),
                "price": price,
                "currency": "USD",
                "stock_quantity": fake.random_int(min=1, max=100),
            }
        ],
    )

    op.bulk_insert(
        Cart.__table__,
        [{"id": CART_ID, "user_id": USER_ID, "status": CartStatus.ACTIVE.value}],
    )

    op.bulk_insert(
        CartItem.__table__,
        [
            {
                "cart_id": CART_ID,
                "product_id": PRODUCT_ID,
                "quantity": fake.random_int(min=1, max=3),
                "unit_price": price,
            }
        ],
    )

    op.bulk_insert(
        UserPaymentMethod.__table__,
        [
            {
                "id": PAYMENT_METHOD_ID,
                "user_id": USER_ID,
                "provider_token": f"tok_test_{fake.word()}",
                "last_four": fake.credit_card_number()[-4:],
                "is_default": True,
            }
        ],
    )


def downgrade():
    op.execute(
        UserPaymentMethod.__table__.delete().where(
            UserPaymentMethod.__table__.c.id == PAYMENT_METHOD_ID
        )
    )
    op.execute(
        CartItem.__table__.delete().where(CartItem.__table__.c.cart_id == CART_ID)
    )
    op.execute(Cart.__table__.delete().where(Cart.__table__.c.id == CART_ID))
    op.execute(Product.__table__.delete().where(Product.__table__.c.id == PRODUCT_ID))
    op.execute(User.__table__.delete().where(User.__table__.c.id == USER_ID))
