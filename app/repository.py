import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cart, CartStatus, Payment, PaymentStatus, UserPaymentMethod


class Repository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_cart_for_update(self, cart_id: uuid.UUID) -> Cart | None:
        return self.session.execute(
            select(Cart).where(Cart.id == cart_id).with_for_update()
        ).scalar_one_or_none()

    def get_active_payment_for_cart(self, cart_id: uuid.UUID) -> Payment:
        return self.session.execute(
            select(Payment).where(
                Payment.cart_id == cart_id, Payment.status != PaymentStatus.FAILED
            )
        ).scalar_one()

    def get_default_payment_method(
        self, user_id: uuid.UUID
    ) -> UserPaymentMethod | None:
        return self.session.execute(
            select(UserPaymentMethod).where(
                UserPaymentMethod.user_id == user_id,
                UserPaymentMethod.is_default.is_(True),
            )
        ).scalar_one_or_none()

    def save_payment(
        self, payment: Payment, cart: Cart, mark_checked_out: bool
    ) -> None:
        self.session.add(payment)
        if mark_checked_out:
            cart.status = CartStatus.CHECKED_OUT
