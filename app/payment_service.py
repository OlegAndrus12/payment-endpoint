import uuid
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app import payment_provider
from app.errors import (
    CartAbandoned,
    CartAlreadyPaid,
    CartNotFound,
    EmptyCart,
    NoDefaultPaymentMethod,
    ProviderUnavailable,
)
from app.models import CartStatus, Payment, PaymentStatus
from app.repository import Repository
from app.session import session_scope


def start_payment(cart_id: uuid.UUID) -> Payment:
    try:
        with session_scope() as session:
            repo = Repository(session)

            cart = repo.get_cart_for_update(cart_id)

            if cart is None:
                raise CartNotFound

            if cart.status == CartStatus.CHECKED_OUT:
                raise CartAlreadyPaid(repo.get_active_payment_for_cart(cart.id))

            if cart.status == CartStatus.ABANDONED:
                raise CartAbandoned

            if not cart.items:
                raise EmptyCart

            amount = sum(
                (item.quantity * item.unit_price for item in cart.items), Decimal(0)
            )
            currency = cart.items[0].product.currency

            payment_method = repo.get_default_payment_method(cart.user_id)

            if payment_method is None:
                raise NoDefaultPaymentMethod

            try:
                result = payment_provider.charge(payment_method.provider_token)
            except Exception as exc:
                raise ProviderUnavailable from exc

            payment = Payment(
                cart_id=cart.id,
                user_id=cart.user_id,
                payment_method_id=payment_method.id,
                amount=amount,
                currency=currency,
                status=(
                    PaymentStatus.SUCCEEDED if result.success else PaymentStatus.FAILED
                ),
                provider_reference=result.provider_reference,
                failure_reason=result.failure_reason,
            )
            repo.save_payment(payment, cart, mark_checked_out=result.success)
    except IntegrityError:
        raise CartAlreadyPaid(repo.get_active_payment_for_cart(cart_id))

    return payment
