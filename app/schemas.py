from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator, HttpUrl
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


# Schema Discussions
class DiscussionCreate(BaseModel):
    group_id: int | None = None
    event_id: int | None = None

    @model_validator(mode="after")
    def check_exactly_one_parent(self):
        # interdit: aucun lien
        if self.group_id is None and self.event_id is None:
            raise ValueError("A discussion must be linked to a group or an event")
        # interdit: les deux
        if self.group_id is not None and self.event_id is not None:
            raise ValueError("A discussion cannot be linked to both a group and an event")
        return self


class DiscussionPublic(BaseModel):
    id: int
    group_id: int | None
    event_id: int | None
    created_at: datetime

    class Config:
        from_attributes = True


#Schema Message
class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def strip_and_validate(self):
        # évite les messages "   "
        cleaned = self.content.strip()
        if not cleaned:
            raise ValueError("content must not be empty")
        self.content = cleaned
        return self


class MessagePublic(BaseModel):
    id: int
    discussion_id: int
    author_id: int
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


# Schema album
class AlbumCreate(BaseModel):
    event_id: int
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def strip_title(self):
        self.title = self.title.strip()
        if not self.title:
            raise ValueError("title must not be empty")
        return self


class AlbumPublic(BaseModel):
    id: int
    event_id: int
    title: str
    description: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# Schema photos
class PhotoCreate(BaseModel):
    url: HttpUrl
    caption: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def clean_caption(self):
        if self.caption is not None:
            self.caption = self.caption.strip()
            if self.caption == "":
                self.caption = None
        return self


class PhotoPublic(BaseModel):
    id: int
    album_id: int
    uploader_id: int
    url: str
    caption: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# Schema commentaires
class PhotoCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def clean_content(self):
        self.content = self.content.strip()
        if not self.content:
            raise ValueError("content must not be empty")
        return self


class PhotoCommentPublic(BaseModel):
    id: int
    photo_id: int
    author_id: int
    content: str
    created_at: datetime

    class Config:
        from_attributes = True
