from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DECIMAL, TIMESTAMP

from .base import Base
from .user import FreeUser
from .subscription import Subscription


class TransactionStatus(Base):
    __tablename__ = "transaction_status"

    transaction_status_id: Mapped[int] = mapped_column(primary_key=True)
    transaction_status_name: Mapped[str] = mapped_column(sa.String(50), nullable=False)


class PaymentMethod(Base):
    __tablename__ = "payment_method"

    payment_method_id: Mapped[int] = mapped_column(primary_key=True)
    payment_gateway_token: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    last_4_digits: Mapped[str] = mapped_column(sa.String(4), nullable=False)
    card_brand: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    expiration_date: Mapped[str] = mapped_column(sa.String(5), nullable=False)
    owner_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("free_user.user_id"))

    user: Mapped["FreeUser"] = relationship(back_populates="payment_methods")


FreeUser.payment_methods = relationship(
    "PaymentMethod", order_by=PaymentMethod.payment_method_id, back_populates="user"
)


class Transaction(Base):
    __tablename__ = "transaction"

    transaction_id: Mapped[int] = mapped_column(primary_key=True)
    transaction_timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    amount: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    transaction_status_id: Mapped[int] = mapped_column(
        sa.ForeignKey("transaction_status.transaction_status_id")
    )
    payment_method_id: Mapped[int] = mapped_column(
        sa.ForeignKey("payment_method.payment_method_id")
    )
    subscription_id: Mapped[int] = mapped_column(
        sa.ForeignKey("subscription.subscription_id"), unique=True
    )

    status: Mapped["TransactionStatus"] = relationship()
    payment_method: Mapped["PaymentMethod"] = relationship(
        back_populates="transactions"
    )
    subscription: Mapped["Subscription"] = relationship(back_populates="transaction")


PaymentMethod.transactions = relationship(
    "Transaction", order_by=Transaction.transaction_id, back_populates="payment_method"
)


Subscription.transaction = relationship(
    "Transaction", uselist=False, back_populates="subscription"
)
