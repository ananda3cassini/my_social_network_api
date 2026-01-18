from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Literal
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# Ajout des schémas
GroupType = Literal["public", "private", "secret"]


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    icon_url: str | None = None
    cover_url: str | None = None
    group_type: GroupType = "public"
    allow_member_posts: bool = True
    allow_member_events: bool = False

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    icon_url: str | None = None
    cover_url: str | None = None
    group_type: GroupType | None = None
    allow_member_posts: bool | None = None
    allow_member_events: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v


class GroupPublic(BaseModel):
    id: int
    name: str
    description: str | None
    icon_url: str | None
    cover_url: str | None
    group_type: str
    allow_member_posts: bool
    allow_member_events: bool

    class Config:
        from_attributes = True


class EventCreate(BaseModel):
    name: str = Field(..., min_length=3)
    description: str | None = None

    start_date: datetime
    end_date: datetime

    location: str
    cover_url: str | None = None

    is_public: bool = True
    group_id: int | None = None

    @model_validator(mode="after")
    def check_dates(self):
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        return self

class EventPublic(BaseModel):
    id: int
    name: str
    description: str | None
    start_date: datetime
    end_date: datetime
    location: str
    cover_url: str | None
    is_public: bool
    group_id: int | None

    class Config:
        from_attributes = True
