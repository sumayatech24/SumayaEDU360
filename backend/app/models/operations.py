"""Store/inventory, activities, meals, communication and CMS models."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID


# --------------------------------------------------------------------- Inventory / Store
class InventoryItem(BaseEntity, Base):
    __tablename__ = "inventory_item"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), default="pcs", nullable=False)
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reorder_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)


class StockMovement(BaseEntity, Base):
    __tablename__ = "stock_movement"

    item_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("inventory_item.id"), index=True)
    movement_type: Mapped[str] = mapped_column(String(10), default="in", nullable=False)  # in / out
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    movement_date: Mapped[date | None] = mapped_column(Date, nullable=True)


# --------------------------------------------------------------------- Activities & Events
class Activity(BaseEntity, Base):
    __tablename__ = "activity"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    activity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # club/sport/competition
    coordinator: Mapped[str | None] = mapped_column(String(150), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ActivityRegistration(BaseEntity, Base):
    __tablename__ = "activity_registration"

    activity_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("activity.id"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    registration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    registration_status: Mapped[str] = mapped_column(String(20), default="registered", nullable=False)
    # registered / cancelled / attended


# --------------------------------------------------------------------- Meal & Cafeteria
class MealPlan(BaseEntity, Base):
    __tablename__ = "meal_plan"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    meal_type: Mapped[str] = mapped_column(String(30), default="lunch", nullable=False)  # breakfast/lunch/snacks
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)


class MealMenu(BaseEntity, Base):
    __tablename__ = "meal_menu"

    meal_plan_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("meal_plan.id"), nullable=True)
    day_of_week: Mapped[str] = mapped_column(String(12), nullable=False)
    items: Mapped[str | None] = mapped_column(Text, nullable=True)
    calories: Mapped[int | None] = mapped_column(Integer, nullable=True)


# --------------------------------------------------------------------- Communication
class Announcement(BaseEntity, Base):
    __tablename__ = "announcement"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    audience: Mapped[str] = mapped_column(String(30), default="all", nullable=False)
    # all / students / parents / teachers / staff
    channel: Mapped[str] = mapped_column(String(20), default="in_app", nullable=False)
    publish_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    announcement_status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    # draft / published / archived


# --------------------------------------------------------------------- Public Website / CMS
class CmsPage(BaseEntity, Base):
    __tablename__ = "cms_page"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), nullable=False)
    page_type: Mapped[str] = mapped_column(String(30), default="page", nullable=False)  # page/news/event
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(__import__("sqlalchemy").Boolean, default=False, nullable=False)
    publish_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class Banner(BaseEntity, Base):
    __tablename__ = "banner"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(__import__("sqlalchemy").Boolean, default=True, nullable=False)
