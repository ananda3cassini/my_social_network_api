from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Table, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base


# User
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# Association tables
group_members = Table(
    "group_members",
    Base.metadata,
    Column("group_id", ForeignKey("groups.id"), primary_key=True),
    Column("user_id", ForeignKey("users.id"), primary_key=True),
)

group_admins = Table(
    "group_admins",
    Base.metadata,
    Column("group_id", ForeignKey("groups.id"), primary_key=True),
    Column("user_id", ForeignKey("users.id"), primary_key=True),
)

event_participants = Table(
    "event_participants",
    Base.metadata,
    Column("event_id", ForeignKey("events.id"), primary_key=True),
    Column("user_id", ForeignKey("users.id"), primary_key=True),
)

event_organizers = Table(
    "event_organizers",
    Base.metadata,
    Column("event_id", ForeignKey("events.id"), primary_key=True),
    Column("user_id", ForeignKey("users.id"), primary_key=True),
)

# Group
class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    icon_url = Column(String, nullable=True)
    cover_url = Column(String, nullable=True)

    # public / private / secret
    group_type = Column(String, nullable=False, default="public")

    allow_member_posts = Column(Boolean, nullable=False, default=True)
    allow_member_events = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    members = relationship("User", secondary=group_members, backref="member_groups")
    admins = relationship("User", secondary=group_admins, backref="admin_groups")

# Event
class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    location = Column(String(255), nullable=False)
    cover_url = Column(String(500), nullable=True)
    is_public = Column(Boolean, nullable=False, default=True)

    # optionnel pour rattacher un event à un groupe
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)

    organizers = relationship("User", secondary=event_organizers, backref="organized_events")
    participants = relationship("User", secondary=event_participants, backref="participating_events")
