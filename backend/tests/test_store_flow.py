import os
import json
from datetime import date
from base64 import b64encode
from itsdangerous import TimestampSigner
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("AUTH_MODE", "dev")
os.environ.setdefault("DATABASE_URL", "sqlite:///./.data/test-commerce.db")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-change-me")

from fastapi.testclient import TestClient
from app.main import app, voice_assertions
from app.database import Base, SessionLocal, engine
from app.config import settings
from app.models import Customer
import pytest


@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as api_client:
        yield api_client


def test_complete_local_shopping_flow(client):
    catalog = client.get("/api/products").json()
    assert len(catalog) >= 10
    product = catalog[0]

    assert client.get("/api/orders").status_code == 401
    assert client.get("/api/voice/orders").status_code == 401
    login = client.post("/api/auth/dev-login")
    assert login.status_code == 200
    assert login.json()["email_verified"] is True
    assert login.json()["name"] == "Local Shopper"
    assert client.get("/api/auth/me").json()["name"] == "Local Shopper"
    voice_token = client.post("/api/voice/token")
    assert voice_token.status_code == 200
    assert voice_token.json()["customer_authenticated"] is True

    address = {"full_name":"Test Shopper", "line1":"12 Market Road", "line2":"", "city":"Pune", "state":"Maharashtra", "postal_code":"411001"}
    payload = {"items":[{"product_id":product["id"],"quantity":1}],"shipping_address":address}
    headers = {"Idempotency-Key":"checkout-flow-0001"}
    created = client.post("/api/checkout/orders", json=payload, headers=headers)
    assert created.status_code == 201, created.text
    order = created.json()["order"]
    assert order["status"] == "pending_payment"
    assert order["order_reference"].isdigit() and len(order["order_reference"]) == 6
    assert order["items"][0]["product_id"] == product["id"]

    assertion = voice_assertions.dumps({"customer_id":"cus_local_01", "scope":"commerce_support"})
    voice_headers = {"X-Voice-Assertion": assertion}
    unclear = client.get("/api/voice/orders", headers=voice_headers).json()
    assert unclear["needs_clarification"] is True
    detail = client.get("/api/voice/orders", params={"order_reference":f"order number {order['order_reference']}"}, headers=voice_headers)
    assert detail.status_code == 200
    assert detail.json()["order"]["order_reference"] == order["order_reference"]
    assert detail.json()["order"]["items"][0]["product_name"] == product["name"]
    parsed_date = date.fromisoformat(order["created_at"][:10]).strftime("%d-%m/%Y")
    by_date = client.get("/api/voice/orders", params={"order_date":parsed_date}, headers=voice_headers)
    assert by_date.status_code == 200 and by_date.json()["found"] is True
    spoken_date = client.get("/api/voice/orders", params={"order_date":"26-10/2026"}, headers=voice_headers)
    assert spoken_date.status_code == 200
    assert spoken_date.json().get("needs_clarification") is not True
    legacy_detail = client.get("/api/voice/orders", params={"order_reference":order["id"]}, headers=voice_headers)
    assert legacy_detail.json()["found"] is True

    repeated = client.post("/api/checkout/orders", json=payload, headers=headers)
    assert repeated.status_code == 201
    assert repeated.json()["order"]["id"] == order["id"]
    different_cart = {"items":[{"product_id":catalog[1]["id"],"quantity":1}],"shipping_address":address}
    assert client.post("/api/checkout/orders", json=different_cart, headers=headers).status_code == 409

    assert client.post(f"/api/payments/mock/complete/{order['id']}").status_code == 200
    owned_order = client.get(f"/api/orders/{order['id']}")
    assert owned_order.status_code == 200
    assert owned_order.json()["payment_status"] == "paid"
    assert owned_order.json()["status"] == "processing"
    history = client.get("/api/orders")
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["id"] == order["id"]
    assert history.json()[0]["created_at"]
    assert history.json()[0]["total"] == order["total"]
    assert history.json()[0]["items"][0]["product_name"] == product["name"]
    order_answer = client.post("/api/assistant/chat", json={"message":f"What is the status of order {order['order_reference']}?"})
    assert order_answer.status_code == 200
    assert "processing" in order_answer.json()["reply"]
    assert order["order_reference"] in order_answer.json()["reply"]
    latest_answer = client.post("/api/assistant/chat", json={"message":"Where is my order?"})
    assert "processing" in latest_answer.json()["reply"]
    date_answer = client.post("/api/assistant/chat", json={"message":f"What is the status of my order placed on {parsed_date}?"})
    assert "processing" in date_answer.json()["reply"]

    no_confirmation = client.post("/api/support/tickets", json={"subject":"Delivery", "summary":"Need help"})
    assert no_confirmation.status_code == 409
    ticket = client.post("/api/support/tickets", json={"subject":"Delivery", "summary":"Please help with delivery", "confirmed":True})
    assert ticket.status_code == 201
    assert ticket.json()["reference"].startswith("AU-")


def test_product_search_and_policy_assistant(client):
    protected_answer = client.post("/api/assistant/chat", json={"message":"Can you track my order?"})
    assert protected_answer.json()["requires_auth"] is True
    result = client.get("/api/products", params={"q":"headphones"})
    assert result.status_code == 200
    assert any("Headphones" in p["name"] for p in result.json())
    reply = client.post("/api/assistant/chat", json={"message":"What is the return policy?"})
    assert "7 days" in reply.json()["reply"]
    assert reply.json()["transcript_persisted"] is False
    token = client.post("/api/voice/token")
    assert token.status_code == 200
    assert token.json()["room"].startswith("harizon-")
    assert token.json()["token"]
    assert token.json()["customer_authenticated"] is False


def test_orders_are_isolated_by_authenticated_customer(client):
    products = client.get("/api/products").json()
    assert client.post("/api/auth/dev-login").status_code == 200
    address = {"full_name":"First Shopper", "line1":"12 Market Road", "line2":"", "city":"Pune", "state":"Maharashtra", "postal_code":"411001"}
    created = client.post("/api/checkout/orders", json={"items":[{"product_id":products[0]["id"],"quantity":1}],"shipping_address":address}, headers={"Idempotency-Key":"customer-a-order-0001"})
    assert created.status_code == 201, created.text
    first_order_id = created.json()["order"]["id"]

    with SessionLocal() as db:
        db.add(Customer(id="cus_local_02", auth_subject="local|customer-two", email="second@example.test", email_verified=True))
        db.commit()

    # Sign a separate local test session exactly as Starlette's session middleware does.
    session_data = b64encode(json.dumps({"customer_id":"cus_local_02"}).encode())
    client.cookies.set("harizon_session", TimestampSigner(settings.session_secret).sign(session_data).decode())
    assert client.get("/api/orders").json() == []
    assert client.get(f"/api/orders/{first_order_id}").status_code == 404
    other_assertion = voice_assertions.dumps({"customer_id":"cus_local_02", "scope":"commerce_support"})
    other_lookup = client.get("/api/voice/orders", params={"order_reference":first_order_id},
                              headers={"X-Voice-Assertion":other_assertion})
    assert other_lookup.status_code == 200
    assert other_lookup.json()["found"] is False
    assert "account" in other_lookup.json()["message"]
    private_chat = client.post("/api/assistant/chat", json={"message":f"What is the status of order {created.json()['order']['order_reference']}?"})
    assert "couldn't find" in private_chat.json()["reply"]

