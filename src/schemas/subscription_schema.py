from datetime import date
from pydantic import BaseModel, ConfigDict, Field


class CardDetails(BaseModel):
    card_number: str = Field(..., max_length=16)
    card_holder_name: str = Field(..., max_length=255)
    expiration_date: str = Field(..., max_length=5)  # MM/YY
    cvc: str = Field(..., max_length=4)


class SubscriptionPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subscription_plan_id: int
    plan_name: str
    description: str | None
    price: float
    currency: str
    billing_interval: str


class SubscriptionStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subscription_status_id: int
    subscription_status_name: str


class SubscriptionBase(BaseModel):
    pass


class SubscriptionCreate(SubscriptionBase):
    subscription_plan_id: int
    user_id: int


class Subscription(SubscriptionBase):
    model_config = ConfigDict(from_attributes=True)

    subscription_id: int
    start_date: date
    end_date: date
    plan: SubscriptionPlan
    status: SubscriptionStatus


class SubscriptionUpgrade(BaseModel):
    subscription_plan_id: int
    card_details: CardDetails
