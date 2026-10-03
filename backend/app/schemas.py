from datetime import date
from enum import Enum
from math import ceil
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


KNOWN_AGENT_IDS = {
    "validator", "travel_planner", "weather", "transportation", "hotel",
    "tour_guide", "health", "dietitian", "document", "insurance",
    "fashion_designer", "finance",
}


class TravelMode(str, Enum):
    flight = "flight"
    train = "train"
    bus = "bus"
    car = "car"
    multi = "multi"


class PaymentMethod(str, Enum):
    credit_card = "Credit Card"
    debit_card = "Debit Card"
    upi = "UPI"
    cash = "Cash"
    bank_transfer = "Bank Transfer"
    google_pay = "Google Pay"
    other = "Other"


class TripRequest(BaseModel):
    origin: str
    destination: str
    adults: int = Field(ge=1)
    children: int = Field(ge=0, default=0)
    child_ages: list[int] = Field(default_factory=list)
    travel_mode: TravelMode = TravelMode.flight
    start_date: date
    end_date: date
    hotel_category: str = "5 Star"
    room_occupancy: int = Field(default=2, ge=1)
    food_preference: str = "Jain"
    payment_method: PaymentMethod = PaymentMethod.credit_card
    hotel_cancellation_required: bool = True
    max_airport_distance_km: float = Field(default=30, gt=0)
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)
    currency: str = "INR"
    special_requirements: list[str] = Field(default_factory=list)
    include_agents: list[str] | None = None
    exclude_agents: list[str] = Field(default_factory=list)

    @field_validator("origin", "destination")
    @classmethod
    def strip_places(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("place is required")
        return v.strip()

    @field_validator("child_ages")
    @classmethod
    def valid_child_ages(cls, ages: list[int]) -> list[int]:
        if any(age < 0 or age > 17 for age in ages):
            raise ValueError("child ages must be between 0 and 17")
        return ages

    @field_validator("include_agents", "exclude_agents")
    @classmethod
    def known_agents_only(cls, agents: list[str] | None) -> list[str] | None:
        if agents is not None:
            unknown = sorted(set(agents) - KNOWN_AGENT_IDS)
            if unknown:
                raise ValueError(f"unknown agent id(s): {', '.join(unknown)}")
        return agents

    @model_validator(mode="after")
    def derived_and_rules(self) -> "TripRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.children and len(self.child_ages) != self.children:
            raise ValueError("child_ages count must equal children")
        if not self.children and self.child_ages:
            raise ValueError("child_ages must be empty when children is 0")
        if self.budget_min is not None and self.budget_max is not None and self.budget_min > self.budget_max:
            raise ValueError("budget_min must be <= budget_max")
        return self

    @property
    def total_travelers(self) -> int:
        return self.adults + self.children

    @property
    def duration_nights(self) -> int:
        return (self.end_date - self.start_date).days

    @property
    def duration_days(self) -> int:
        return self.duration_nights + 1

    @property
    def required_rooms(self) -> int:
        return ceil(self.total_travelers / self.room_occupancy)

    def public_dict(self) -> dict[str, Any]:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "adults": self.adults,
            "children": self.children,
            "child_ages": self.child_ages,
            "total_travelers": self.total_travelers,
            "travel_mode": self.travel_mode.value,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "duration_days": self.duration_days,
            "duration_nights": self.duration_nights,
            "hotel_category": self.hotel_category,
            "room_occupancy": self.room_occupancy,
            "required_rooms": self.required_rooms,
            "food_preference": self.food_preference,
            "payment_method": self.payment_method.value,
            "hotel_cancellation_required": self.hotel_cancellation_required,
            "max_airport_distance_km": self.max_airport_distance_km,
            "budget_min": self.budget_min,
            "budget_max": self.budget_max,
            "currency": self.currency,
            "special_requirements": self.special_requirements,
        }


class AgentEnvelope(BaseModel):
    agent: str
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    data_status: str = "ESTIMATED"


class CreatePlanBody(BaseModel):
    user_display_name: str = "Guest"
    user_email: str | None = None
    raw_text: str | None = None
    trip: TripRequest
