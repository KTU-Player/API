from datetime import datetime
from pydantic import BaseModel, ConfigDict

from .subscription_schema import Subscription


class TransactionStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_status_id: int
    transaction_status_name: str


class PaymentMethodBase(BaseModel):
    owner_name: str
    card_brand: str
    last_4_digits: str
    expiration_date: str  # MM/YY


class PaymentMethodCreate(PaymentMethodBase):
    payment_gateway_token: str  # Token from Stripe, etc.
    user_id: int


class PaymentMethod(PaymentMethodBase):
    model_config = ConfigDict(from_attributes=True)

    payment_method_id: int


class Transaction(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_id: int
    timestamp: datetime
    amount: float
    status: TransactionStatus
    payment_method: PaymentMethod
    subscription: Subscription
