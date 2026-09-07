from dataclasses import dataclass
from uuid import uuid4

DECLINE_TOKEN = "tok_test_decline"


@dataclass(frozen=True)
class ChargeResult:
    success: bool
    provider_reference: str | None
    failure_reason: str | None


def charge(provider_token: str) -> ChargeResult:
    if provider_token == DECLINE_TOKEN:
        return ChargeResult(
            success=False, provider_reference=None, failure_reason="card_declined"
        )
    return ChargeResult(
        success=True, provider_reference=f"mock_txn_{uuid4()}", failure_reason=None
    )
