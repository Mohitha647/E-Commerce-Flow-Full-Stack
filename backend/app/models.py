from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OrderStatus(str, Enum):
    pending = "pending"
    paid = "paid"
    shipped = "shipped"
    cancelled = "cancelled"


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255), default="")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    orders: Mapped[list["Order"]] = relationship(back_populates="user")
    cart_items: Mapped[list["CartItem"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    reviews: Mapped[list["Review"]] = relationship(back_populates="user")


# --------------------------------------------------------------------------
# Catalog
# --------------------------------------------------------------------------
class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)

    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    price_cents: Mapped[int] = mapped_column(Integer)  # store money as integer cents
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    category: Mapped[Category | None] = relationship(back_populates="products")
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="product")
    reviews: Mapped[list["Review"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    inventory_logs: Mapped[list["InventoryLog"]] = relationship(back_populates="product", cascade="all, delete-orphan")

    @property
    def price(self) -> float:
        return self.price_cents / 100


class InventoryLog(Base):
    """Audit trail for every stock change (order placed, restock, manual adjustment)."""
    __tablename__ = "inventory_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    delta: Mapped[int] = mapped_column(Integer)  # negative = decrement (sale), positive = restock
    reason: Mapped[str] = mapped_column(String(120))
    resulting_quantity: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    product: Mapped[Product] = relationship(back_populates="inventory_logs")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_review_user_product"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    rating: Mapped[int] = mapped_column(Integer)  # 1..5
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=_now)

    user: Mapped[User] = relationship(back_populates="reviews")
    product: Mapped[Product] = relationship(back_populates="reviews")


# --------------------------------------------------------------------------
# Cart
# --------------------------------------------------------------------------
class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    added_at: Mapped[datetime] = mapped_column(default=_now)

    user: Mapped[User] = relationship(back_populates="cart_items")
    product: Mapped[Product] = relationship()


# --------------------------------------------------------------------------
# Orders
# --------------------------------------------------------------------------
class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_order_user_idempotency"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default=OrderStatus.pending.value)
    total_cents: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    user: Mapped[User] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")

    @property
    def total(self) -> float:
        return self.total_cents / 100


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_cents: Mapped[int] = mapped_column(Integer)  # price snapshot at purchase time

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(back_populates="order_items")
