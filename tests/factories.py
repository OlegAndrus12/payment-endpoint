from decimal import Decimal

import factory
from faker import Faker

from app.models import Cart, CartItem, CartStatus, Product, User, UserPaymentMethod, db

fake = Faker()


class BaseFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session_factory = lambda: db.session
        sqlalchemy_session_persistence = "commit"


class UserFactory(BaseFactory):
    class Meta:
        model = User

    email = factory.LazyFunction(fake.unique.email)
    name = factory.LazyFunction(fake.name)


class ProductFactory(BaseFactory):
    class Meta:
        model = Product

    name = factory.LazyFunction(lambda: fake.word().capitalize())
    price = Decimal("10.00")
    currency = "USD"
    stock_quantity = 100


class CartFactory(BaseFactory):
    class Meta:
        model = Cart

    user = factory.SubFactory(UserFactory)
    status = CartStatus.ACTIVE


class CartItemFactory(BaseFactory):
    class Meta:
        model = CartItem

    cart = factory.SubFactory(CartFactory)
    product = factory.SubFactory(ProductFactory)
    quantity = 1
    unit_price = factory.LazyAttribute(lambda o: o.product.price)


class UserPaymentMethodFactory(BaseFactory):
    class Meta:
        model = UserPaymentMethod

    user = factory.SubFactory(UserFactory)
    provider_token = factory.LazyFunction(lambda: f"tok_test_{fake.word()}")
    is_default = True
