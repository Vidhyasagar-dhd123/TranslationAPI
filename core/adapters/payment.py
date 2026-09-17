"""
Payment Adapter module.
Provides an extensible adapter pattern for payment gateways with a DummyPaymentAdapter.
Upon successful payment, grants 5,000,000 tokens to the tenant.
"""
from abc import ABC, abstractmethod
import uuid
from typing import Dict, Any


DEFAULT_PAYMENT_TOKENS = 5_000_000
DEFAULT_PAYMENT_AMOUNT = 49.99
DEFAULT_PAYMENT_CURRENCY = "USD"


class PaymentAdapterBase(ABC):
    @abstractmethod
    def create_order(self, tenant_id: int, amount: float = DEFAULT_PAYMENT_AMOUNT, currency: str = DEFAULT_PAYMENT_CURRENCY) -> Dict[str, Any]:
        """Creates a payment order/session."""
        pass

    @abstractmethod
    def verify_and_credit(self, tenant, transaction_id: str, order_id: str = None) -> Dict[str, Any]:
        """Verifies payment and returns transaction result dict with tokens granted."""
        pass


class DummyPaymentAdapter(PaymentAdapterBase):
    """
    Dummy payment gateway simulation for development & testing.
    Instantly verifies payment and awards 5M tokens to the tenant.
    """
    def create_order(self, tenant_id: int, amount: float = DEFAULT_PAYMENT_AMOUNT, currency: str = DEFAULT_PAYMENT_CURRENCY) -> Dict[str, Any]:
        order_id = f"ORDER-DUMMY-{uuid.uuid4().hex[:12].upper()}"
        return {
            "order_id": order_id,
            "amount": amount,
            "currency": currency,
            "tokens_granted": DEFAULT_PAYMENT_TOKENS,
            "status": "created",
            "provider": "dummy_payment_gateway",
            "checkout_url": f"/api/payment/confirm/?order_id={order_id}",
        }

    def verify_and_credit(self, tenant, transaction_id: str = None, order_id: str = None) -> Dict[str, Any]:
        txn_id = transaction_id or f"TXN-DUMMY-{uuid.uuid4().hex[:12].upper()}"
        
        # Credit tokens to tenant
        tenant.token_balance += DEFAULT_PAYMENT_TOKENS
        tenant.save(update_fields=['token_balance', 'updated_at'])

        return {
            "transaction_id": txn_id,
            "order_id": order_id or f"ORDER-{txn_id}",
            "amount": DEFAULT_PAYMENT_AMOUNT,
            "currency": DEFAULT_PAYMENT_CURRENCY,
            "tokens_credited": DEFAULT_PAYMENT_TOKENS,
            "new_balance": tenant.token_balance,
            "status": "completed",
            "message": f"Successfully credited {DEFAULT_PAYMENT_TOKENS:,} tokens to tenant {tenant.name}.",
        }
