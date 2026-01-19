from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Table, Text, UniqueConstraint, Float 
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base
from datetime import datetime



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

    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)

    organizers = relationship("User", secondary=event_organizers, backref="organized_events")
    participants = relationship("User", secondary=event_participants, backref="participating_events")

    shopping_list_enabled = Column(Boolean, nullable=False, default=False)
    carpool_enabled = Column(Boolean, nullable=False, default=False)  # pour plus tard



# Discussion
class Discussion(Base):
    __tablename__ = "discussions"

    id = Column(Integer, primary_key=True, index=True)

    # lien exclusif : groupe OU event
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    messages = relationship("Message", back_populates="discussion", cascade="all, delete-orphan")


# Message
class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)

    discussion_id = Column(Integer, ForeignKey("discussions.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # thread / reply
    parent_message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)

    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    discussion = relationship("Discussion", back_populates="messages")
    author = relationship("User")

    # self-referential relationships
    parent = relationship("Message", remote_side=[id], backref="replies")



# Album
class PhotoAlbum(Base):
    __tablename__ = "photo_albums"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    event = relationship("Event")
    photos = relationship("Photo", back_populates="album", cascade="all, delete-orphan")


# Photo
class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, index=True)
    album_id = Column(Integer, ForeignKey("photo_albums.id"), nullable=False)
    uploader_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    url = Column(String(500), nullable=False)
    caption = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    album = relationship("PhotoAlbum", back_populates="photos")
    uploader = relationship("User")
    comments = relationship("PhotoComment", back_populates="photo", cascade="all, delete-orphan")


# Commentaire photo
class PhotoComment(Base):
    __tablename__ = "photo_comments"

    id = Column(Integer, primary_key=True, index=True)
    photo_id = Column(Integer, ForeignKey("photos.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    photo = relationship("Photo", back_populates="comments")
    author = relationship("User")


# Sondage
class Poll(Base):
    __tablename__ = "polls"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    event = relationship("Event")
    creator = relationship("User")
    questions = relationship("PollQuestion", back_populates="poll", cascade="all, delete-orphan")

# Question de sondage
class PollQuestion(Base):
    __tablename__ = "poll_questions"

    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey("polls.id"), nullable=False)

    question = Column(Text, nullable=False)

    poll = relationship("Poll", back_populates="questions")
    options = relationship("PollOption", back_populates="question", cascade="all, delete-orphan")


# Réponses possibles 
class PollOption(Base):
    __tablename__ = "poll_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("poll_questions.id"), nullable=False)

    label = Column(String(255), nullable=False)

    question = relationship("PollQuestion", back_populates="options")


# Vote d'un participant
class PollVote(Base):
    __tablename__ = "poll_votes"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("poll_questions.id"), nullable=False)
    option_id = Column(Integer, ForeignKey("poll_options.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        # 1 vote max par question et par utilisateur
        UniqueConstraint("question_id", "user_id", name="uq_vote_question_user"),
    )

    question = relationship("PollQuestion")
    option = relationship("PollOption")
    user = relationship("User")


# Billetterie
class TicketType(Base):
    __tablename__ = "ticket_types"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)

    name = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False, default=0.0)  # prix
    quantity_limit = Column(Integer, nullable=False)     # stock dispo

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    event = relationship("Event", backref="ticket_types")


class TicketPurchase(Base):
    __tablename__ = "ticket_purchases"

    id = Column(Integer, primary_key=True, index=True)

    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    ticket_type_id = Column(Integer, ForeignKey("ticket_types.id"), nullable=False)

    email = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    address = Column(Text, nullable=False)

    purchased_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("event_id", "email", name="uq_ticket_purchase_event_email"),
    )

    event = relationship("Event", backref="ticket_purchases")
    ticket_type = relationship("TicketType", backref="purchases")

# Shopping item
from sqlalchemy import UniqueConstraint
from datetime import datetime

class ShoppingItem(Base):
    __tablename__ = "shopping_items"
    __table_args__ = (
        UniqueConstraint("event_id", "name", name="uq_shopping_item_event_name"),
    )

    id = Column(Integer, primary_key=True, index=True)

    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    name = Column(String(100), nullable=False)
    quantity = Column(Integer, nullable=False)
    arrival_time = Column(DateTime, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    event = relationship("Event", backref="shopping_items")
    user = relationship("User", backref="shopping_items")
