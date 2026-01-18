from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from .db import get_db
from .models import Event, TicketType, TicketPurchase, User, event_organizers
from .schemas import (
    TicketTypeCreate,
    TicketTypePublic,
    TicketPurchaseCreate,
    TicketPurchasePublic,
)
from .security import get_current_user

router = APIRouter(prefix="/events", tags=["tickets"])


def _ensure_event_exists(db: Session, event_id: int) -> Event:
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def _ensure_event_is_public(event: Event):
    if not event.is_public:
        raise HTTPException(status_code=403, detail="Ticketing is only available for public events")


def _ensure_current_user_is_organizer(db: Session, event_id: int, user_id: int):
    is_org = db.execute(
        select(event_organizers.c.user_id).where(
            (event_organizers.c.event_id == event_id)
            & (event_organizers.c.user_id == user_id)
        )
    ).first()
    if not is_org:
        raise HTTPException(status_code=403, detail="Only organizers can manage ticketing")


# A) Create ticket type (organizer only)
@router.post("/{event_id}/tickets/types", response_model=TicketTypePublic, status_code=201)
def create_ticket_type(
    event_id: int,
    payload: TicketTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = _ensure_event_exists(db, event_id)
    _ensure_event_is_public(event)
    _ensure_current_user_is_organizer(db, event_id, current_user.id)

    tt = TicketType(
        event_id=event_id,
        name=payload.name,
        amount=payload.amount,
        quantity_limit=payload.quantity_limit,
    )
    db.add(tt)
    db.commit()
    db.refresh(tt)
    return tt


# B) List ticket types (public for public events)
@router.get("/{event_id}/tickets/types", response_model=list[TicketTypePublic])
def list_ticket_types(event_id: int, db: Session = Depends(get_db)):
    event = _ensure_event_exists(db, event_id)
    _ensure_event_is_public(event)

    items = db.execute(select(TicketType).where(TicketType.event_id == event_id)).scalars().all()
    return items


# C) Purchase (no auth) - 1 purchase per email per event
@router.post("/{event_id}/tickets/purchase", response_model=TicketPurchasePublic, status_code=201)
def purchase_ticket(
    event_id: int,
    payload: TicketPurchaseCreate,
    db: Session = Depends(get_db),
):
    event = _ensure_event_exists(db, event_id)
    _ensure_event_is_public(event)

    tt = db.execute(
        select(TicketType).where(
            (TicketType.id == payload.ticket_type_id) & (TicketType.event_id == event_id)
        )
    ).scalar_one_or_none()
    if tt is None:
        raise HTTPException(status_code=404, detail="Ticket type not found for this event")

    # already purchased?
    already = db.execute(
        select(TicketPurchase.id).where(
            (TicketPurchase.event_id == event_id) & (TicketPurchase.email == payload.email)
        )
    ).first()
    if already:
        raise HTTPException(status_code=409, detail="This email already purchased a ticket for this event")

    # stock check
    sold = db.execute(
        select(func.count(TicketPurchase.id)).where(TicketPurchase.ticket_type_id == tt.id)
    ).scalar_one()
    if sold >= tt.quantity_limit:
        raise HTTPException(status_code=409, detail="Sold out")

    purchase = TicketPurchase(
        event_id=event_id,
        ticket_type_id=tt.id,
        email=str(payload.email),
        first_name=payload.first_name,
        last_name=payload.last_name,
        address=payload.address,
        purchased_at=datetime.utcnow(),
    )
    db.add(purchase)
    db.commit()
    db.refresh(purchase)
    return purchase


# D) List purchases (organizer only)
@router.get("/{event_id}/tickets/purchases", response_model=list[TicketPurchasePublic])
def list_purchases(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = _ensure_event_exists(db, event_id)
    _ensure_event_is_public(event)
    _ensure_current_user_is_organizer(db, event_id, current_user.id)

    items = db.execute(
        select(TicketPurchase).where(TicketPurchase.event_id == event_id)
    ).scalars().all()
    return items
