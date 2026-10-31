import hashlib
import hmac
import httpx
from fastapi import HTTPException
from .config import settings


class PaymentAdapter:
    async def create_order(self, amount_paise: int, receipt: str) -> dict:
        raise NotImplementedError


class MockPaymentAdapter(PaymentAdapter):
    async def create_order(self, amount_paise: int, receipt: str) -> dict:
        return {"provider_order_id": f"mock_{receipt}", "checkout_key": None, "mode": "mock"}


class RazorpayAdapter(PaymentAdapter):
    async def create_order(self, amount_paise: int, receipt: str) -> dict:
        if not settings.razorpay_key_id or not settings.razorpay_key_secret:
            raise HTTPException(503, "Razorpay test credentials are missing")
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post("https://api.razorpay.com/v1/orders",
                auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
                json={"amount": amount_paise, "currency": "INR", "receipt": receipt})
        if response.is_error:
            raise HTTPException(502, "Payment provider could not create checkout")
        data = response.json()
        return {"provider_order_id": data["id"], "checkout_key": settings.razorpay_key_id, "mode": "razorpay"}


def get_payment_adapter() -> PaymentAdapter:
    return RazorpayAdapter() if settings.payment_provider == "razorpay" else MockPaymentAdapter()


def verify_checkout_signature(provider_order_id: str, payment_id: str, signature: str) -> bool:
    expected = hmac.new(settings.razorpay_key_secret.encode(), f"{provider_order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    if not settings.razorpay_webhook_secret:
        return False
    expected = hmac.new(settings.razorpay_webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
