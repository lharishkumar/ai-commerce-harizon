from pydantic import BaseModel, Field


class CheckoutItem(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=10)


class ShippingAddress(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    line1: str = Field(min_length=4, max_length=180)
    line2: str = Field(default="", max_length=180)
    city: str = Field(min_length=2, max_length=80)
    state: str = Field(min_length=2, max_length=80)
    postal_code: str = Field(min_length=6, max_length=10)


class CreateOrderRequest(BaseModel):
    items: list[CheckoutItem] = Field(min_length=1, max_length=30)
    shipping_address: ShippingAddress


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1200)
