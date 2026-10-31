import hashlib
import json
import logging
import re
import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload
from .auth import router as auth_router, require_customer
from .catalog import list_products, seed_products
from .config import settings
from .database import Base, engine, get_db
from .models import Customer, Order, OrderItem, Payment, PaymentEvent, Product, SupportTicket
from .payments import get_payment_adapter, verify_checkout_signature, verify_webhook_signature
from .schemas import ChatRequest, CreateOrderRequest

app = FastAPI(title="HARIZON Commerce API", version="0.1.0")
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, session_cookie="harizon_session",
                   same_site="lax", https_only=settings.app_env != "development", max_age=60 * 60 * 24 * 7)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_url], allow_credentials=True,
                   allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type", "Idempotency-Key", "X-Razorpay-Signature"])
app.include_router(auth_router)
voice_assertions = URLSafeTimedSerializer(settings.session_secret, salt="harizon-livekit-actions")
logger = logging.getLogger("harizon.api")


def money(value):
    return float(value or 0)


def parse_order_date(value: str | None) -> date | None:
    """Accept ISO, common Indian numeric dates, and spoken month names."""
    if not value:
        return None
    raw = re.sub(r"\s+", " ", value.strip())
    raw = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", raw, flags=re.I).replace(",", "")
    raw = re.sub(r"\bof\b", " ", raw, flags=re.I)
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%m/%Y", "%d/%m-%Y",
                "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    return None


def order_reference_from_text(value: str) -> str:
    raw = value.strip().lower()
    raw = re.sub(r"\b(order|number|reference|ref|id|is|ending|ends)\b", " ", raw)
    raw = raw.replace("#", " ").strip()
    compact = re.sub(r"[\s-]", "", raw)
    digits = {"zero":"0", "oh":"0", "one":"1", "two":"2", "three":"3", "four":"4",
              "five":"5", "six":"6", "seven":"7", "eight":"8", "nine":"9"}
    words = re.findall(r"[a-z]+", raw)
    if len(words) == 6 and all(word in digits for word in words):
        return "".join(digits[word] for word in words)
    return compact


def find_customer_orders(db: Session, customer_id: str, reference: str | None = None,
                         placed_on: date | None = None, limit: int = 6):
    statement = select(Order).options(selectinload(Order.items)).where(Order.customer_id == customer_id)
    if reference:
        ref = order_reference_from_text(reference)
        if ref.isdigit():
            statement = statement.where(Order.order_reference == ref)
        elif re.fullmatch(r"(?:ord_)?[a-f0-9]{20}", ref):
            exact_id = ref if ref.startswith("ord_") else f"ord_{ref}"
            statement = statement.where(func.lower(Order.id) == exact_id)
        else:
            return []
    if placed_on:
        statement = statement.where(func.date(Order.created_at) == placed_on.isoformat())
    return list(db.scalars(statement.order_by(Order.created_at.desc()).limit(limit)))


def create_order_reference(db: Session) -> str:
    for _ in range(20):
        reference = str(100000 + secrets.randbelow(900000))
        if not db.scalar(select(Order.id).where(Order.order_reference == reference)):
            return reference
    raise HTTPException(503, "Could not assign an order number; please retry checkout")


def product_json(product: Product):
    return {"id": product.id, "name": product.name, "category": product.category, "brand": product.brand,
            "tagline": product.tagline, "description": product.description, "price": money(product.price),
            "compare_at": money(product.compare_at) if product.compare_at else None, "stock": product.stock,
            "rating": money(product.rating), "review_count": product.review_count, "image_key": product.image_key,
            "color": product.color, "specs": product.specs, "featured": product.featured}


def order_json(order: Order):
    return {"id": order.id, "order_reference": order.order_reference, "status": order.status, "payment_status": order.payment_status,
            "subtotal": money(order.subtotal), "shipping": money(order.shipping), "total": money(order.total),
            "currency": order.currency, "created_at": order.created_at.isoformat(),
            "items": [{"product_id": item.product_id, "product_name": item.product_name,
                       "quantity": item.quantity, "unit_price": money(item.unit_price)} for item in order.items]}


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    with next(get_db()) as db:
        seed_products(db)


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "environment": settings.app_env}


@app.post("/api/voice/token")
def voice_token(request: Request, db: Session = Depends(get_db)):
    """Issue a short-lived LiveKit token; pass only a signed, scoped customer claim to the worker."""
    from livekit import api
    room = f"harizon-{secrets.token_hex(10)}"
    identity = f"visitor-{secrets.token_hex(8)}"
    customer_id = request.session.get("customer_id")
    customer = db.get(Customer, customer_id) if customer_id else None
    assertion = None
    if customer and customer.email_verified:
        assertion = voice_assertions.dumps({"customer_id": customer.id, "scope": "commerce_support"})
    logger.info("voice.token.issued authenticated=%s", bool(assertion))
    dispatch_metadata = json.dumps({"assertion": assertion})
    token = (api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
             .with_identity(identity).with_name("Store visitor")
             .with_ttl(timedelta(minutes=30))
             .with_grants(api.VideoGrants(room_join=True, room=room, can_publish=True, can_subscribe=True))
             .with_room_config(api.RoomConfiguration(agents=[api.RoomAgentDispatch(
                 agent_name="harizon-shop-assistant", metadata=dispatch_metadata)])))
    return {"token": token.to_jwt(), "room": room, "url": settings.livekit_url,
            "customer_authenticated": bool(assertion)}


def voice_customer(assertion: str | None, db: Session) -> Customer:
    if not assertion:
        logger.info("voice.order_lookup.denied reason=missing_assertion")
        raise HTTPException(401, "Sign in with a verified email to use customer support actions")
    try:
        claims = voice_assertions.loads(assertion, max_age=1800)
    except (BadSignature, TypeError):
        logger.info("voice.order_lookup.denied reason=expired_or_invalid_assertion")
        raise HTTPException(401, "Voice support authorization expired; reconnect to continue")
    if claims.get("scope") != "commerce_support":
        raise HTTPException(403, "Voice support action is not allowed")
    customer = db.get(Customer, claims.get("customer_id"))
    if not customer or not customer.email_verified:
        raise HTTPException(401, "Verified customer account not found")
    return customer


@app.get("/api/voice/orders")
def voice_order_lookup(order_reference: str | None = Query(default=None, min_length=1, max_length=80),
                       order_date: str | None = Query(default=None, max_length=80),
                       x_voice_assertion: str | None = Header(default=None, alias="X-Voice-Assertion"),
                       db: Session = Depends(get_db)):
    """Find an order only within the verified customer's own account."""
    customer = voice_customer(x_voice_assertion, db)
    logger.info("voice.order_lookup.authorized reference_supplied=%s date_supplied=%s",
                bool(order_reference), bool(order_date))
    placed_on = parse_order_date(order_date)
    if order_date and not placed_on:
        return {"found": False, "needs_clarification": True,
                "message": "I couldn't understand that date. Please say the day, month, and year, for example 26 October 2026."}
    if not order_reference and not placed_on:
        return {"found": False, "needs_clarification": True,
                "message": "Ask for the order reference or the date the order was placed."}

    matches = find_customer_orders(db, customer.id, order_reference, placed_on)
    if not matches:
        return {"found": False, "message": "I could not find an order with those details in this account."}

    def safe_summary(order: Order):
        return {"order_reference": order.order_reference, "order_date": order.created_at.date().isoformat(),
                "status": order.status.replace("_", " "),
                "payment_status": order.payment_status.replace("_", " "),
                "subtotal": money(order.subtotal), "shipping": money(order.shipping),
                "total": money(order.total), "currency": order.currency,
                "items": [{"product_name": item.product_name, "quantity": item.quantity,
                           "unit_price": money(item.unit_price)} for item in order.items]}

    if len(matches) > 1:
        return {"found": False, "needs_clarification": True,
                "orders": [safe_summary(order) for order in matches[:5]],
                "message": "More than one order matches. Ask which date or masked reference they mean."}
    return {"found": True, "order": safe_summary(matches[0])}


@app.get("/api/products")
def products(q: str = "", category: str = "", sort: str = "featured", db: Session = Depends(get_db)):
    return [product_json(item) for item in list_products(db, q[:100], category[:80], sort)]


@app.get("/api/products/{product_id}")
def product_detail(product_id: str, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product or not product.active:
        raise HTTPException(404, "Product not found")
    return product_json(product)


@app.post("/api/checkout/orders", status_code=201)
async def create_order(payload: CreateOrderRequest, request: Request,
                       idempotency_key: str = Header(alias="Idempotency-Key", min_length=12, max_length=120),
                       customer: Customer = Depends(require_customer), db: Session = Depends(get_db)):
    normalized = {}
    for item in payload.items:
        normalized[item.product_id] = normalized.get(item.product_id, 0) + item.quantity
        if normalized[item.product_id] > 10:
            raise HTTPException(422, "Maximum quantity per product is 10")
    body_hash = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    existing = db.scalar(select(Order).options(selectinload(Order.items)).where(
        Order.customer_id == customer.id, Order.idempotency_key == idempotency_key))
    if existing:
        if existing.request_hash != body_hash:
            raise HTTPException(409, "Idempotency key was already used for a different cart")
        payment = db.scalar(select(Payment).where(Payment.order_id == existing.id))
        return {"order": order_json(existing), "payment": {"provider": payment.provider,
                "provider_order_id": payment.provider_order_id,
                "checkout_key": settings.razorpay_key_id if payment.provider == "razorpay" else None,
                "mode": payment.provider, "status": payment.status}}

    product_rows = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(normalized.keys())))}
    if len(product_rows) != len(normalized):
        raise HTTPException(422, "One or more products are unavailable")
    subtotal = Decimal("0.00")
    for product_id, quantity in normalized.items():
        product = product_rows[product_id]
        if not product.active or product.stock < quantity:
            raise HTTPException(409, f"{product.name} is out of stock")
        subtotal += Decimal(product.price) * quantity

    order_id = f"ord_{secrets.token_hex(10)}"
    order_reference = create_order_reference(db)
    total = subtotal + (Decimal("0.00") if subtotal >= Decimal("5000.00") else Decimal("99.00"))
    adapter = get_payment_adapter()
    provider_order = await adapter.create_order(int(total * 100), order_id)
    try:
        for product_id, quantity in normalized.items():
            changed = db.execute(update(Product).where(Product.id == product_id, Product.stock >= quantity)
                                 .values(stock=Product.stock - quantity))
            if changed.rowcount != 1:
                raise HTTPException(409, f"{product_rows[product_id].name} just went out of stock")
        order = Order(id=order_id, order_reference=order_reference, customer_id=customer.id, subtotal=subtotal,
                      shipping=total - subtotal, total=total, idempotency_key=idempotency_key,
                      request_hash=body_hash, shipping_address=payload.shipping_address.model_dump())
        db.add(order)
        for product_id, quantity in normalized.items():
            product = product_rows[product_id]
            db.add(OrderItem(order_id=order_id, product_id=product.id, product_name=product.name,
                             quantity=quantity, unit_price=product.price))
        payment = Payment(id=f"pay_{secrets.token_hex(10)}", order_id=order_id,
                          provider=settings.payment_provider, provider_order_id=provider_order["provider_order_id"],
                          amount=total, status="created")
        db.add(payment)
        db.commit()
    except Exception:
        db.rollback()
        raise
    order = db.scalar(select(Order).options(selectinload(Order.items)).where(Order.id == order_id))
    return {"order": order_json(order), "payment": {**provider_order, "status": "created"}}


@app.get("/api/orders")
def my_orders(customer: Customer = Depends(require_customer), db: Session = Depends(get_db)):
    rows = db.scalars(select(Order).options(selectinload(Order.items)).where(Order.customer_id == customer.id)
                      .order_by(Order.created_at.desc()).limit(50))
    return [order_json(row) for row in rows]


@app.get("/api/orders/{order_id}")
def order_detail(order_id: str, customer: Customer = Depends(require_customer), db: Session = Depends(get_db)):
    order = db.scalar(select(Order).options(selectinload(Order.items)).where(
        Order.id == order_id, Order.customer_id == customer.id))
    if not order:
        raise HTTPException(404, "Order not found")
    return order_json(order)


def settle_payment(db: Session, provider_order_id: str, event_id: str, event_type: str):
    if db.get(PaymentEvent, event_id):
        return False
    payment = db.scalar(select(Payment).where(Payment.provider_order_id == provider_order_id).with_for_update())
    if not payment:
        raise HTTPException(404, "Payment not found")
    order = db.scalar(select(Order).where(Order.id == payment.order_id).with_for_update())
    if event_type in {"payment.captured", "order.paid"}:
        payment.status = "paid"
        order.payment_status = "paid"
        order.status = "processing"
    elif event_type == "payment.authorized" and payment.status == "created":
        payment.status = "authorized"
        order.payment_status = "authorized"
    elif event_type in {"payment.failed", "order.payment_failed"} and payment.status != "paid":
        payment.status = "failed"
        order.payment_status = "failed"
        order.status = "payment_failed"
    db.add(PaymentEvent(id=event_id, event_type=event_type))
    db.commit()
    return True


@app.post("/api/payments/mock/complete/{order_id}")
def mock_complete(order_id: str, customer: Customer = Depends(require_customer), db: Session = Depends(get_db)):
    if settings.app_env != "development" or settings.payment_provider != "mock":
        raise HTTPException(404, "Not found")
    order = db.scalar(select(Order).where(Order.id == order_id, Order.customer_id == customer.id))
    payment = db.scalar(select(Payment).where(Payment.order_id == order_id))
    if not order or not payment:
        raise HTTPException(404, "Order not found")
    settle_payment(db, payment.provider_order_id, f"dev_{order_id}", "payment.captured")
    return {"ok": True}


@app.post("/api/payments/verify")
def verify_payment(payload: dict, customer: Customer = Depends(require_customer), db: Session = Depends(get_db)):
    if settings.payment_provider != "razorpay":
        raise HTTPException(404, "Not found")
    order_id = payload.get("order_id", "")
    payment_id = payload.get("payment_id", "")
    signature = payload.get("signature", "")
    order = db.scalar(select(Order).where(Order.id == order_id, Order.customer_id == customer.id))
    payment = db.scalar(select(Payment).where(Payment.order_id == order_id))
    if not order or not payment or not verify_checkout_signature(payment.provider_order_id, payment_id, signature):
        raise HTTPException(400, "Payment verification failed")
    settle_payment(db, payment.provider_order_id, f"checkout_{payment_id}", "payment.captured")
    return {"ok": True}


@app.post("/api/payments/razorpay/webhook")
async def razorpay_webhook(request: Request, signature: str = Header(alias="X-Razorpay-Signature"),
                           db: Session = Depends(get_db)):
    body = await request.body()
    if not verify_webhook_signature(body, signature):
        raise HTTPException(400, "Invalid webhook signature")
    try:
        event = json.loads(body)
        event_id = event.get("event_id") or hashlib.sha256(body).hexdigest()
        event_type = event.get("event", "")
        entity = event.get("payload", {}).get("payment", {}).get("entity", {})
        provider_order_id = entity.get("order_id") or event.get("payload", {}).get("order", {}).get("entity", {}).get("id")
        if provider_order_id and event_type in {"payment.captured", "order.paid", "payment.failed", "order.payment_failed", "payment.authorized"}:
            applied = settle_payment(db, provider_order_id, event_id, event_type)
        else:
            applied = False
        return {"received": True, "applied": applied}
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid webhook event")


@app.post("/api/support/tickets", status_code=201)
def create_ticket(payload: dict, customer: Customer = Depends(require_customer), db: Session = Depends(get_db)):
    if payload.get("confirmed") is not True:
        raise HTTPException(409, "Customer confirmation is required before creating a ticket")
    subject = str(payload.get("subject", "Shopping support"))[:180]
    summary = str(payload.get("summary", ""))[:2000].strip()
    if not summary:
        raise HTTPException(422, "Please provide a short summary")
    ticket = SupportTicket(id=f"tkt_{secrets.token_hex(8)}", reference=f"AU-{secrets.token_hex(3).upper()}",
                          customer_id=customer.id, subject=subject, summary=summary, confirmed=True)
    db.add(ticket)
    db.commit()
    return {"reference": ticket.reference, "status": ticket.status, "message": "Your support request is with our team."}


@app.get("/api/support/tickets")
def my_tickets(customer: Customer = Depends(require_customer), db: Session = Depends(get_db)):
    rows = db.scalars(select(SupportTicket).where(SupportTicket.customer_id == customer.id).order_by(SupportTicket.created_at.desc()))
    return [{"reference": row.reference, "subject": row.subject, "status": row.status,
             "created_at": row.created_at.isoformat()} for row in rows]


POLICIES = {
    "shipping": "Orders over ₹5,000 ship free. Standard delivery usually takes 3–6 business days across India. You’ll receive tracking after dispatch.",
    "returns": "Unused products can be returned within 7 days of delivery in their original packaging. Contact support with your order reference to start a return.",
    "warranty": "Products include a 1-year limited manufacturer warranty unless the product page says otherwise.",
}


@app.post("/api/assistant/chat")
async def assistant_chat(payload: ChatRequest, request: Request, db: Session = Depends(get_db)):
    message = payload.message.strip()
    lower = message.lower()
    legacy_ref = re.search(r"\bord_[a-f0-9]{4,40}\b|\b[a-f0-9]{20}\b", lower)
    numeric_ref = re.search(r"\b\d{6}\b", lower)
    order_topic = bool(re.search(r"\b(order|orders|track|tracking|shipment|delivery status)\b", lower))
    number_words = {"zero":"0", "oh":"0", "one":"1", "two":"2", "three":"3", "four":"4",
                    "five":"5", "six":"6", "seven":"7", "eight":"8", "nine":"9"}
    words = re.findall(r"[a-z]+", lower)
    spoken_ref = next(("".join(number_words[word] for word in words[i:i + 6])
                       for i in range(len(words) - 5)
                       if all(word in number_words for word in words[i:i + 6])), None)
    if order_topic or legacy_ref or numeric_ref:
        customer_id = request.session.get("customer_id")
        customer = db.get(Customer, customer_id) if customer_id else None
        if not customer or not customer.email_verified:
            return {"reply": "Please sign in with your verified email first. Then ask me to check your order.", "requires_auth": True, "transcript_persisted": False}
        date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b|\b\d{1,2}[-/]\d{1,2}/\d{4}\b", message)
        if not date_match:
            date_match = re.search(r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{4}\b|\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?[,]?\s+\d{4}\b", message, re.I)
        raw_date = date_match.group(0) if date_match else None
        raw_date = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", raw_date, flags=re.I) if raw_date else None
        placed_on = parse_order_date(raw_date)
        if raw_date and not placed_on:
            return {"reply": "I couldn't read that date. Please say it as day, month, and year, for example 26 October 2026.", "transcript_persisted": False}
        reference = legacy_ref.group(0) if legacy_ref else numeric_ref.group(0) if numeric_ref else spoken_ref
        matches = find_customer_orders(db, customer.id, reference, placed_on, limit=1 if not reference and not placed_on else 6)
        if not matches:
            reply = ("I couldn't find an order with that number or date on your account. Please check the number or date and try again."
                     if reference or placed_on else "There are no orders on your account yet. I can still help with product or policy questions.")
            return {"reply": reply, "transcript_persisted": False}
        if len(matches) > 1:
            refs = ", ".join(f"{row.order_reference} placed {row.created_at.date().isoformat()}" for row in matches[:5])
            return {"reply": f"I found several matching orders: {refs}. Which order number should I check?", "transcript_persisted": False}
        order = matches[0]
        items = ", ".join(f"{item.quantity} {item.product_name}" for item in order.items)
        return {"reply": f"Order {order.order_reference}, placed {order.created_at.date().isoformat()}, is {order.status.replace('_', ' ')}. Payment is {order.payment_status.replace('_', ' ')}. Total {order.currency} {money(order.total):.2f}. Items: {items}.", "transcript_persisted": False}
    if any(word in lower for word in ("human", "agent", "support ticket", "talk to someone")):
        return {"reply": "I can hand this to our support team. Use the ‘Need a human?’ button below to review the summary and confirm before I create a ticket.", "transcript_persisted": False}
    if any(word in lower for word in ("return", "refund", "exchange")):
        return {"reply": POLICIES["returns"], "transcript_persisted": False}
    if any(word in lower for word in ("shipping", "delivery", "deliver", "ship")):
        return {"reply": POLICIES["shipping"], "transcript_persisted": False}
    if "warranty" in lower:
        return {"reply": POLICIES["warranty"], "transcript_persisted": False}
    products_found = list_products(db, message, "", "featured")
    if products_found:
        p = products_found[0]
        specs = ", ".join(f"{key}: {value}" for key, value in list(p.specs.items())[:3])
        return {"reply": f"{p.name} is ₹{int(p.price):,}. {p.tagline} Key details: {specs}. Would you like to compare it with another product?", "product_id": p.id, "transcript_persisted": False}
    if settings.openai_api_key:
        import httpx
        context = "\n".join(f"{x.name}: ₹{int(x.price)}. {x.description} Specifications: {x.specs}" for x in list_products(db)[:12])
        async with httpx.AsyncClient(timeout=18) as client:
            response = await client.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={"model": settings.openai_model, "temperature": 0.2,
                      "messages": [{"role": "system", "content": f"You are HARIZON, a concise electronics shopping assistant. Answer only from this catalog and policy context. If uncertain, say so. Never claim to place orders, change payments, or create a ticket.\n{context}\nPolicies: {POLICIES}"}, {"role": "user", "content": message}]})
        if response.is_success:
            return {"reply": response.json()["choices"][0]["message"]["content"], "transcript_persisted": False}
    return {"reply": "I can help with product details, shipping, returns, and warranty questions. What product or policy would you like to know about?", "transcript_persisted": False}

