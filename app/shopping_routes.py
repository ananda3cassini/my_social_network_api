from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from .db import get_db
from .models import Event, User, ShoppingItem, event_participants, event_organizers
from .schemas import ShoppingItemCreate, ShoppingItemUpdate, ShoppingItemPublic
from .security import get_current_user

router = APIRouter(prefix="/events/{event_id}/shopping-items", tags=["shopping"])


def is_event_member(db: Session, event_id: int, user_id: int) -> bool:
    is_org = db.execute(
        select(event_organizers.c.user_id).where(
            (event_organizers.c.event_id == event_id) &
            (event_organizers.c.user_id == user_id)
        )
    ).first() is not None

    if is_org:
        return True

    is_participant = db.execute(
        select(event_participants.c.user_id).where(
            (event_participants.c.event_id == event_id) &
            (event_participants.c.user_id == user_id)
        )
    ).first() is not None

    return is_participant


@router.post("", response_model=ShoppingItemPublic, status_code=201)
def create_item(
    event_id: int,
    payload: ShoppingItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if not event.shopping_list_enabled:
        raise HTTPException(status_code=400, detail="Shopping list is not enabled for this event")

    if not is_event_member(db, event_id, current_user.id):
        raise HTTPException(status_code=403, detail="You must be a participant or organizer")

    # Unicité par event (check applicatif en plus de la contrainte DB)
    existing = db.execute(
        select(ShoppingItem).where(
            (ShoppingItem.event_id == event_id) &
            (ShoppingItem.name == payload.name)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="This item already exists for this event")

    item = ShoppingItem(
        event_id=event_id,
        user_id=current_user.id,
        name=payload.name,
        quantity=payload.quantity,
        arrival_time=payload.arrival_time,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return {
        "id": item.id,
        "event_id": item.event_id,
        "name": item.name,
        "quantity": item.quantity,
        "arrival_time": item.arrival_time,
        "created_at": item.created_at,
        "created_by": {"id": current_user.id, "email": current_user.email, "full_name": current_user.full_name},
    }


@router.get("", response_model=list[ShoppingItemPublic])
def list_items(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if not event.shopping_list_enabled:
        raise HTTPException(status_code=400, detail="Shopping list is not enabled for this event")

    if not is_event_member(db, event_id, current_user.id):
        raise HTTPException(status_code=403, detail="You must be a participant or organizer")

    items = db.execute(
        select(ShoppingItem).where(ShoppingItem.event_id == event_id).order_by(ShoppingItem.created_at.desc())
    ).scalars().all()

    result = []
    for it in items:
        u = db.execute(select(User).where(User.id == it.user_id)).scalar_one_or_none()
        result.append({
            "id": it.id,
            "event_id": it.event_id,
            "name": it.name,
            "quantity": it.quantity,
            "arrival_time": it.arrival_time,
            "created_at": it.created_at,
            "created_by": {"id": u.id, "email": u.email, "full_name": u.full_name} if u else None,
        })
    return result


# update item
@router.patch("/{item_id}", response_model=ShoppingItemPublic)
def update_item(
    event_id: int,
    item_id: int,
    payload: ShoppingItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if not event.shopping_list_enabled:
        raise HTTPException(status_code=400, detail="Shopping list is not enabled for this event")

    item = db.execute(
        select(ShoppingItem).where(
            ShoppingItem.id == item_id,
            ShoppingItem.event_id == event_id,
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Shopping item not found")

    # droits : créateur OU organizer
    is_organizer = db.execute(
        select(event_organizers.c.user_id).where(
            event_organizers.c.event_id == event_id,
            event_organizers.c.user_id == current_user.id,
        )
    ).first() is not None

    if item.user_id != current_user.id and not is_organizer:
        raise HTTPException(status_code=403, detail="Not allowed to update this item")

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(item, k, v)

    db.commit()
    db.refresh(item)

    return {
        "id": item.id,
        "event_id": item.event_id,
        "name": item.name,
        "quantity": item.quantity,
        "arrival_time": item.arrival_time,
        "created_at": item.created_at,
        "created_by": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
        },
    }


# delete item
@router.delete("/{item_id}", status_code=204)
def delete_item(
    event_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if not event.shopping_list_enabled:
        raise HTTPException(status_code=400, detail="Shopping list is not enabled for this event")

    item = db.execute(
        select(ShoppingItem).where(
            ShoppingItem.id == item_id,
            ShoppingItem.event_id == event_id,
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Shopping item not found")

    is_organizer = db.execute(
        select(event_organizers.c.user_id).where(
            event_organizers.c.event_id == event_id,
            event_organizers.c.user_id == current_user.id,
        )
    ).first() is not None

    if item.user_id != current_user.id and not is_organizer:
        raise HTTPException(status_code=403, detail="Not allowed to delete this item")

    db.delete(item)
    db.commit()
    return
