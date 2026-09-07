import uuid

from flask import Blueprint, jsonify

from app.models import PaymentStatus
from app.payment_service import start_payment

payments_bp = Blueprint("payments", __name__)


@payments_bp.post("/carts/<uuid:cart_id>/payments")
def create_payment(cart_id: uuid.UUID):
    payment = start_payment(cart_id)
    status_code = 201 if payment.status == PaymentStatus.SUCCEEDED else 402
    return jsonify(payment.to_dict()), status_code
