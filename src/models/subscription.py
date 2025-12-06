from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DECIMAL

from .base import Base
from .user import FreeUser


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plan"

    subscription_plan_id: Mapped[int] = mapped_column(primary_key=True)
    plan_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text)
    price: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    billing_interval: Mapped[str] = mapped_column(sa.String(255), nullable=False)


class SubscriptionStatus(Base):
    __tablename__ = "subscription_status"

    subscription_status_id: Mapped[int] = mapped_column(primary_key=True)
    subscription_status_name: Mapped[str] = mapped_column(
        sa.String(50), nullable=False
    )


class Subscription(Base):
    __tablename__ = "subscription"

    subscription_id: Mapped[int] = mapped_column(primary_key=True)
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    subscription_status_id: Mapped[int] = mapped_column(
        sa.ForeignKey("subscription_status.subscription_status_id")
    )
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("free_user.user_id"))
    subscription_plan_id: Mapped[int] = mapped_column(
        sa.ForeignKey("subscription_plan.subscription_plan_id")
    )

    status: Mapped["SubscriptionStatus"] = relationship()
    user: Mapped["FreeUser"] = relationship(back_populates="subscriptions")
    plan: Mapped["SubscriptionPlan"] = relationship()


FreeUser.subscriptions = relationship(
    "Subscription", order_by=Subscription.subscription_id, back_populates="user"
)
