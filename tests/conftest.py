import pytest
from flask_migrate import upgrade as migrate_upgrade
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app import create_app
from app.config import settings
from app.models import db
from tests.factories import CartFactory, CartItemFactory, UserPaymentMethodFactory

_APP_TABLES = (
    "payments",
    "cart_items",
    "carts",
    "user_payment_methods",
    "products",
    "users",
)


def _ensure_database_exists(database_url: str) -> None:
    url = make_url(database_url)
    admin_engine = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    with admin_engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": url.database},
        ).scalar()
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin_engine.dispose()


@pytest.fixture(scope="session")
def app():
    _ensure_database_exists(settings.test_database_url)
    test_app = create_app(database_url=settings.test_database_url)
    with test_app.app_context():
        migrate_upgrade()
    return test_app


@pytest.fixture(autouse=True)
def db_session(app):
    with app.app_context():
        yield db.session

        db.session.rollback()
        db.session.execute(
            text(f"TRUNCATE TABLE {', '.join(_APP_TABLES)} RESTART IDENTITY CASCADE")
        )
        db.session.commit()
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def payable_cart(db_session):
    cart = CartFactory()
    CartItemFactory(cart=cart, quantity=2)
    UserPaymentMethodFactory(user=cart.user)
    return cart
