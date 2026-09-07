from app import payment_provider
from app.models import Cart, CartStatus, Payment, db
from app.payment_provider import DECLINE_TOKEN
from tests.factories import CartFactory, CartItemFactory, UserPaymentMethodFactory


def test_successful_payment_charges_default_method_and_checks_out_cart(
    client, payable_cart
):
    response = client.post(f"/carts/{payable_cart.id}/payments")

    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] == "succeeded"
    assert body["amount"] == "20.00"
    assert db.session.get(Cart, payable_cart.id).status == CartStatus.CHECKED_OUT


def test_cart_not_found_returns_404(client):
    response = client.post("/carts/00000000-0000-0000-0000-000000000000/payments")

    assert response.status_code == 404
    assert response.get_json() == {"error": "cart_not_found"}


def test_already_checked_out_cart_returns_409_with_existing_payment(
    client, payable_cart
):
    first = client.post(f"/carts/{payable_cart.id}/payments")
    assert first.status_code == 201

    second = client.post(f"/carts/{payable_cart.id}/payments")

    assert second.status_code == 409
    body = second.get_json()
    assert body["error"] == "cart_already_paid"
    assert body["payment"]["id"] == first.get_json()["id"]


def test_abandoned_cart_returns_409(client):
    cart = CartFactory(status=CartStatus.ABANDONED)

    response = client.post(f"/carts/{cart.id}/payments")

    assert response.status_code == 409
    assert response.get_json() == {"error": "cart_abandoned"}


def test_empty_cart_returns_422(client):
    cart = CartFactory()

    response = client.post(f"/carts/{cart.id}/payments")

    assert response.status_code == 422
    assert response.get_json() == {"error": "cart_empty"}


def test_no_default_payment_method_returns_422(client):
    cart = CartFactory()
    CartItemFactory(cart=cart)

    response = client.post(f"/carts/{cart.id}/payments")

    assert response.status_code == 422
    assert response.get_json() == {"error": "no_default_payment_method"}


def test_provider_decline_returns_402_and_records_failed_payment(client):
    cart = CartFactory()
    CartItemFactory(cart=cart)
    UserPaymentMethodFactory(user=cart.user, provider_token=DECLINE_TOKEN)

    response = client.post(f"/carts/{cart.id}/payments")

    assert response.status_code == 402
    body = response.get_json()
    assert body["status"] == "failed"
    assert body["failure_reason"] == "card_declined"
    assert db.session.get(Cart, cart.id).status == CartStatus.ACTIVE


def test_failed_payment_does_not_block_retry(client):
    cart = CartFactory()
    CartItemFactory(cart=cart)
    method = UserPaymentMethodFactory(user=cart.user, provider_token=DECLINE_TOKEN)

    declined = client.post(f"/carts/{cart.id}/payments")
    assert declined.status_code == 402

    method.provider_token = "tok_test_visa"
    db.session.commit()

    retried = client.post(f"/carts/{cart.id}/payments")
    assert retried.status_code == 201


def test_provider_exception_returns_502_and_leaves_cart_untouched(
    client, payable_cart, monkeypatch
):
    def _broken_charge(provider_token):
        raise RuntimeError("provider is down")

    monkeypatch.setattr(payment_provider, "charge", _broken_charge)

    response = client.post(f"/carts/{payable_cart.id}/payments")

    assert response.status_code == 502
    assert response.get_json() == {"error": "provider_unavailable"}
    assert db.session.get(Cart, payable_cart.id).status == CartStatus.ACTIVE
    assert db.session.query(Payment).filter_by(cart_id=payable_cart.id).count() == 0
