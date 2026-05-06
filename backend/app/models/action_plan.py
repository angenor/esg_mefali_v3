"""Modeles SQLAlchemy pour le module Plan d'Action et Dashboard."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


# --- Enumerations ---


class PlanTimeframe(int, enum.Enum):
    """Horizon du plan d'action en mois."""

    six_months = 6
    twelve_months = 12
    twenty_four_months = 24


class PlanStatus(str, enum.Enum):
    """Statut du plan d'action."""

    active = "active"
    archived = "archived"


class ActionItemCategory(str, enum.Enum):
    """Categorie d'une action."""

    environment = "environment"
    social = "social"
    governance = "governance"
    financing = "financing"
    carbon = "carbon"
    intermediary_contact = "intermediary_contact"


class ActionItemStatus(str, enum.Enum):
    """Statut d'une action."""

    todo = "todo"
    in_progress = "in_progress"
    on_hold = "on_hold"
    completed = "completed"
    cancelled = "cancelled"


# Transitions de statut valides
VALID_STATUS_TRANSITIONS: dict[ActionItemStatus, set[ActionItemStatus]] = {
    ActionItemStatus.todo: {
        ActionItemStatus.in_progress,
        ActionItemStatus.cancelled,
    },
    ActionItemStatus.in_progress: {
        ActionItemStatus.completed,
        ActionItemStatus.on_hold,
        ActionItemStatus.cancelled,
    },
    ActionItemStatus.on_hold: {
        ActionItemStatus.in_progress,
        ActionItemStatus.cancelled,
    },
    ActionItemStatus.completed: set(),
    ActionItemStatus.cancelled: set(),
}


class ActionItemPriority(str, enum.Enum):
    """Priorite d'une action."""

    high = "high"
    medium = "medium"
    low = "low"


class ReminderType(str, enum.Enum):
    """Type de rappel."""

    action_due = "action_due"
    assessment_renewal = "assessment_renewal"
    fund_deadline = "fund_deadline"
    intermediary_followup = "intermediary_followup"
    custom = "custom"


class BadgeType(str, enum.Enum):
    """Type de badge de gamification."""

    first_carbon = "first_carbon"
    esg_above_50 = "esg_above_50"
    first_application = "first_application"
    first_intermediary_contact = "first_intermediary_contact"
    full_journey = "full_journey"


# --- Modeles ---


class ActionPlan(UUIDMixin, TimestampMixin, Base):
    """Plan d'action personnalise d'un utilisateur."""

    __tablename__ = "action_plans"
    __table_args__ = (
        Index(
            "uq_active_plan_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # F02 — multi-tenant
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    timeframe: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PlanStatus] = mapped_column(
        Enum(PlanStatus, name="plan_status_enum"),
        nullable=False,
        server_default="active",
    )
    total_actions: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    completed_actions: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )

    # Relations
    user = relationship("User", backref="action_plans")
    items: Mapped[list["ActionItem"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="ActionItem.sort_order",
        lazy="selectin",
    )


class ActionItem(UUIDMixin, TimestampMixin, Base):
    """Action concrete d'un plan d'action."""

    __tablename__ = "action_items"
    __table_args__ = (
        CheckConstraint(
            "completion_percentage >= 0 AND completion_percentage <= 100",
            name="ck_completion_percentage_range",
        ),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    # F02 — multi-tenant
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[ActionItemCategory] = mapped_column(
        Enum(ActionItemCategory, name="action_item_category_enum"),
        nullable=False,
    )
    priority: Mapped[ActionItemPriority] = mapped_column(
        Enum(ActionItemPriority, name="action_item_priority_enum"),
        nullable=False,
        server_default="medium",
    )
    status: Mapped[ActionItemStatus] = mapped_column(
        Enum(ActionItemStatus, name="action_item_status_enum"),
        nullable=False,
        server_default="todo",
    )
    due_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    estimated_cost_xof: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_benefit: Mapped[str | None] = mapped_column(String(500), nullable=True)
    completion_percentage: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    related_fund_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("funds.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_intermediary_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intermediaries.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Snapshot coordonnees intermediaire
    intermediary_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    intermediary_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    intermediary_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    intermediary_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Relations
    plan: Mapped["ActionPlan"] = relationship(back_populates="items")
    fund = relationship("Fund", lazy="selectin")
    intermediary = relationship("Intermediary", lazy="selectin")
    reminders: Mapped[list["Reminder"]] = relationship(
        back_populates="action_item",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Reminder(UUIDMixin, Base):
    """Rappel programme lie a une action."""

    __tablename__ = "reminders"
    __table_args__ = (
        Index("idx_reminders_upcoming", "user_id", "sent", "scheduled_at"),
        Index("idx_reminders_account_id", "account_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # F02 — multi-tenant
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    action_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("action_items.id", ondelete="CASCADE"),
        nullable=True,
    )
    type: Mapped[ReminderType] = mapped_column(
        Enum(ReminderType, name="reminder_type_enum"),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    sent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relations
    user = relationship("User", backref="reminders")
    action_item: Mapped["ActionItem | None"] = relationship(back_populates="reminders")


class Badge(UUIDMixin, Base):
    """Recompense de gamification."""

    __tablename__ = "badges"
    __table_args__ = (
        UniqueConstraint("user_id", "badge_type", name="uq_user_badge"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    badge_type: Mapped[BadgeType] = mapped_column(
        Enum(BadgeType, name="badge_type_enum"),
        nullable=False,
    )
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relations
    user = relationship("User", backref="badges")
