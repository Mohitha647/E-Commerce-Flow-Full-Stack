from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# --- Auth ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = ""


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    is_admin: bool
    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Catalog ---
class CategoryOut(BaseModel):
    id: str
    name: str
    slug: str
    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    sku: str
    name: str
    description: str = ""
    price: float = Field(gt=0, description="Price in dollars, e.g. 19.99")
    category_id: Optional[str] = None
    stock_quantity: int = Field(ge=0, default=0)


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0)
    category_id: Optional[str] = None
    is_active: Optional[bool] = None


class ProductOut(BaseModel):
    id: str
    sku: str
    name: str
    description: str
    price: float
    category_id: Optional[str]
    stock_quantity: int
    is_active: bool
    avg_rating: Optional[float] = None
    review_count: int = 0
    model_config = {"from_attributes": True}


class RestockRequest(BaseModel):
    quantity: int = Field(gt=0)
    reason: str = "restock"


# --- Reviews ---
class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = ""


class ReviewOut(BaseModel):
    id: str
    user_id: str
    product_id: str
    rating: int
    comment: str
    created_at: datetime
    model_config = {"from_attributes": True}


# --- Cart ---
class CartItemAdd(BaseModel):
    product_id: str
    quantity: int = Field(gt=0, default=1)


class CartItemOut(BaseModel):
    product_id: str
    product_name: str
    unit_price: float
    quantity: int
    line_total: float


class CartOut(BaseModel):
    items: list[CartItemOut]
    subtotal: float


# --- Orders ---
class CheckoutRequest(BaseModel):
    idempotency_key: Optional[str] = Field(
        default=None, description="Optional client-generated key to prevent duplicate checkouts on retry"
    )


class OrderItemOut(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    line_total: float


class OrderOut(BaseModel):
    id: str
    status: str
    total: float
    created_at: datetime
    items: list[OrderItemOut]


# --- Recommendations ---
class RecommendationOut(BaseModel):
    product: ProductOut
    reason: str
    score: float
