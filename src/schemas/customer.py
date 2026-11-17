from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class CustomerBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    country: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 code")
    city: Optional[str] = Field(None, max_length=100)
    consent_email: bool = Field(default=False)
    consent_sms: bool = Field(default=False)


class CustomerCreate(CustomerBase):
    email: EmailStr


class CustomerUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    consent_email: Optional[bool] = None
    consent_sms: Optional[bool] = None


class CustomerResponse(CustomerBase):
    id: int
    email: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
