from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def now_utc():
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    brand: Mapped[str] = mapped_column(String(80), nullable=False)
    tagline: Mapped[str] = mapped_column(String(240), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    compare_at: Mapped[float | None] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(Integer, default=20)
    rating: Mapped[float] = mapped_column(Numeric(2, 1), default=4.5)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    image_key: Mapped[str] = mapped_column(String(40), default="device")
    color: Mapped[str] = mapped_column(String(40), default="#d9e3f1")
    specs: Mapped[dict] = mapped_column(JSON, default=dict)
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    auth_subject: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str] = mapped_column(String(254), index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    order_reference: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending_payment", index=True)
    payment_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    shipping: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    shipping_address: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    items: Mapped[list["OrderItem"]] = relationship(cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("customer_id", "idempotency_key", name="uq_customer_idempotency"),)


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[str] = mapped_column(String(80), nullable=False)
    product_name: Mapped[str] = mapped_column(String(180), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_order_id: Mapped[str | None] = mapped_column(String(120), unique=True)
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    subject: Mapped[str] = mapped_column(String(180), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="open")
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
