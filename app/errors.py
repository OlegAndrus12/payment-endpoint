from flask import Flask, jsonify

from app.models import Payment


class PaymentError(Exception):
    pass


class CartNotFound(PaymentError):
    pass


class CartAlreadyPaid(PaymentError):
    def __init__(self, payment: Payment) -> None:
        self.payment = payment


class CartAbandoned(PaymentError):
    pass


class EmptyCart(PaymentError):
    pass


class NoDefaultPaymentMethod(PaymentError):
    pass


class ProviderUnavailable(PaymentError):
    pass


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(CartNotFound)
    def handle_cart_not_found(_: CartNotFound):
        return jsonify(error="cart_not_found"), 404

    @app.errorhandler(CartAlreadyPaid)
    def handle_cart_already_paid(exc: CartAlreadyPaid):
        return jsonify(error="cart_already_paid", payment=exc.payment.to_dict()), 409

    @app.errorhandler(CartAbandoned)
    def handle_cart_abandoned(_: CartAbandoned):
        return jsonify(error="cart_abandoned"), 409

    @app.errorhandler(EmptyCart)
    def handle_empty_cart(_: EmptyCart):
        return jsonify(error="cart_empty"), 422

    @app.errorhandler(NoDefaultPaymentMethod)
    def handle_no_default_payment_method(_: NoDefaultPaymentMethod):
        return jsonify(error="no_default_payment_method"), 422

    @app.errorhandler(ProviderUnavailable)
    def handle_provider_unavailable(_: ProviderUnavailable):
        return jsonify(error="provider_unavailable"), 502
