from datetime import date
from pydantic import BaseModel, ConfigDict


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
