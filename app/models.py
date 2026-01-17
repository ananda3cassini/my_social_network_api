from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, ForeignKey, Table, Text
)
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
