from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from .db import get_db
from .models import Event, Group, User, event_participants, event_organizers, group_members, group_admins
from .schemas import EventCreate, EventPublic
from .security import get_current_user, get_current_user_optional

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventPublic, status_code=201)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Si l'event est rattaché à un groupe : vérifier que le groupe existe
    if payload.group_id is not None:
        group = db.execute(select(Group).where(Group.id == payload.group_id)).scalar_one_or_none()
        if group is None:
            raise HTTPException(status_code=404, detail="Group not found")

    # doit être membre du groupe
        is_member = db.execute(
            select(group_members.c.user_id).where(
                group_members.c.group_id == payload.group_id,
                group_members.c.user_id == current_user.id,
            )
        ).first() is not None
        if not is_member:
            raise HTTPException(status_code=403, detail="Only group members can create events for this group")

    # si les membres ne peuvent pas créer d'event => admin only
        if not group.allow_member_events:
            is_admin = db.execute(
                select(group_admins.c.user_id).where(
                    group_admins.c.group_id == payload.group_id,
                    group_admins.c.user_id == current_user.id,
                )
            ).first() is not None
            if not is_admin:
                raise HTTPException(status_code=403, detail="Only group admins can create events for this group")


    event = Event(
        name=payload.name,
        description=payload.description,
        start_date=payload.start_date,
        end_date=payload.end_date,
        location=payload.location,
        cover_url=payload.cover_url,
        is_public=payload.is_public,
        group_id=payload.group_id,
        shopping_list_enabled=payload.shopping_list_enabled,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    # Par choix produit: le créateur devient automatiquement organisateur
    db.execute(
        event_organizers.insert().values(event_id=event.id, user_id=current_user.id)
    )
    db.commit()

    db.refresh(event)
    return event



@router.post("/{event_id}/join", status_code=204)
def join_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # évite doublon
    exists = db.execute(
        select(event_participants.c.user_id).where(
            (event_participants.c.event_id == event_id)
            & (event_participants.c.user_id == current_user.id)
        )
    ).first()

    if exists:
        return  # déjà participant --> idempotent

    db.execute(
        event_participants.insert().values(event_id=event_id, user_id=current_user.id)
    )
    db.commit()
    return


@router.get("/{event_id}/participants", response_model=list[dict])
def list_participants(event_id: int, db: Session = Depends(get_db)):
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # on renvoie une liste simplifiée (id, email, full_name)
    participants = db.execute(
        select(User).join(event_participants, User.id == event_participants.c.user_id)
        .where(event_participants.c.event_id == event_id)
    ).scalars().all()

    return [{"id": u.id, "email": u.email, "full_name": u.full_name} for u in participants]


@router.post("/{event_id}/organizers/{user_id}", status_code=204)
def add_organizer(
    event_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1) event existe ?
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # 2) seul un organisateur peut ajouter un autre organisateur
    is_org = db.execute(
        select(event_organizers.c.user_id).where(
            event_organizers.c.event_id == event_id,
            event_organizers.c.user_id == current_user.id,
        )
    ).first() is not None
    if not is_org:
        raise HTTPException(status_code=403, detail="Only organizers can add organizers")

    # 3) user cible existe ?
    target = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    # 4) règle métier: target doit être participant
    is_participant = db.execute(
        select(event_participants.c.user_id).where(
            event_participants.c.event_id == event_id,
            event_participants.c.user_id == user_id,
        )
    ).first() is not None
    if not is_participant:
        raise HTTPException(status_code=400, detail="User must be a participant before becoming organizer")

    # 5) éviter doublon
    already = db.execute(
        select(event_organizers.c.user_id).where(
            event_organizers.c.event_id == event_id,
            event_organizers.c.user_id == user_id,
        )
    ).first() is not None
    if already:
        return

    db.execute(event_organizers.insert().values(event_id=event_id, user_id=user_id))
    db.commit()
    return



@router.get("/{event_id}/organizers", response_model=list[dict])
def list_organizers(event_id: int, db: Session = Depends(get_db)):
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    organizers = db.execute(
        select(User)
        .join(event_organizers, User.id == event_organizers.c.user_id)
        .where(event_organizers.c.event_id == event_id)
    ).scalars().all()

    return [{"id": u.id, "email": u.email, "full_name": u.full_name} for u in organizers]


@router.get("/{event_id}", response_model=EventPublic)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # 1) Event public -> accessible à tous
    if event.is_public:
        return event

    # 2) Event privé -> il faut être connecté
    if current_user is None:
        raise HTTPException(status_code=403, detail="Event is private")

    # 3) Organisateur ?
    is_organizer = db.execute(
        select(event_organizers.c.user_id).where(
            event_organizers.c.event_id == event_id,
            event_organizers.c.user_id == current_user.id,
        )
    ).first() is not None
    if is_organizer:
        return event

    # 4) Participant ?
    is_participant = db.execute(
        select(event_participants.c.user_id).where(
            event_participants.c.event_id == event_id,
            event_participants.c.user_id == current_user.id,
        )
    ).first() is not None
    if is_participant:
        return event

    # 5) Event lié à un groupe : membre du groupe ?
    if event.group_id is not None:
        is_group_member = db.execute(
            select(group_members.c.user_id).where(
                group_members.c.group_id == event.group_id,
                group_members.c.user_id == current_user.id,
            )
        ).first() is not None

        if is_group_member:
            return event

    raise HTTPException(status_code=403, detail="Not allowed to view this event")


@router.delete("/{event_id}/organizers/{user_id}", status_code=204)
def remove_organizer(
    event_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1) event existe ?
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # 2) seul un organisateur peut retirer un organisateur
    is_org = db.execute(
        select(event_organizers.c.user_id).where(
            event_organizers.c.event_id == event_id,
            event_organizers.c.user_id == current_user.id,
        )
    ).first() is not None
    if not is_org:
        raise HTTPException(status_code=403, detail="Only organizers can remove organizers")

    # 3) vérifier que la cible est bien organisateur
    target_is_org = db.execute(
        select(event_organizers.c.user_id).where(
            event_organizers.c.event_id == event_id,
            event_organizers.c.user_id == user_id,
        )
    ).first() is not None
    if not target_is_org:
        return  # idempotent : rien à faire

    # 4) ne pas supprimer le dernier organisateur
    org_count = db.execute(
        select(event_organizers.c.user_id).where(event_organizers.c.event_id == event_id)
    ).all()
    if len(org_count) <= 1:
        raise HTTPException(status_code=400, detail="Event must have at least one organizer")

    # 5) suppression
    db.execute(
        event_organizers.delete().where(
            event_organizers.c.event_id == event_id,
            event_organizers.c.user_id == user_id,
        )
    )
    db.commit()
    return


@router.delete("/{event_id}/participants/me", status_code=204)
def leave_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # event existe ?
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # si l'utilisateur est organisateur, on interdit de quitter en tant que participant
    # (sinon incohérent: organizer mais plus participant)
    is_organizer = db.execute(
        select(event_organizers.c.user_id).where(
            event_organizers.c.event_id == event_id,
            event_organizers.c.user_id == current_user.id,
        )
    ).first() is not None
    if is_organizer:
        raise HTTPException(status_code=400, detail="Organizers cannot leave the event (remove organizer role first)")

    # suppression participation (idempotent: si pas présent, ça fait rien)
    db.execute(
        event_participants.delete().where(
            event_participants.c.event_id == event_id,
            event_participants.c.user_id == current_user.id,
        )
    )
    db.commit()
    return

from sqlalchemy import or_

@router.get("", response_model=list[EventPublic])
def list_events(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
    limit: int = 20,
    offset: int = 0,
):
    # sécuriser limit (évite qu'un client demande 1 million d'items)
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")

    # Cas 1 : non connecté -> uniquement events publics
    if current_user is None:
        events = db.execute(
            select(Event)
            .where(Event.is_public == True)  # noqa: E712
            .order_by(Event.start_date.desc())
            .limit(limit)
            .offset(offset)
        ).scalars().all()
        return events

    # Cas 2 : connecté -> publics + privés où je suis participant/organizer
    # On récupère les ids des events où je suis participant
    participant_ids = db.execute(
        select(event_participants.c.event_id).where(event_participants.c.user_id == current_user.id)
    ).scalars().all()

    # ids des events où je suis organizer
    organizer_ids = db.execute(
        select(event_organizers.c.event_id).where(event_organizers.c.user_id == current_user.id)
    ).scalars().all()

    allowed_private_ids = set(participant_ids) | set(organizer_ids)

    query = select(Event).where(
        or_(
            Event.is_public == True,  # noqa: E712
            Event.id.in_(allowed_private_ids) if allowed_private_ids else False,
        )
    ).order_by(Event.start_date.desc()).limit(limit).offset(offset)

    events = db.execute(query).scalars().all()
    return events


@router.post("/{event_id}/invite-group-members", status_code=204)
def invite_group_members(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.group_id is None:
        raise HTTPException(status_code=400, detail="This event is not linked to a group")

    # autorisation: organizer de l'event (simple)
    is_org = db.execute(
        select(event_organizers.c.user_id).where(
            event_organizers.c.event_id == event_id,
            event_organizers.c.user_id == current_user.id,
        )
    ).first() is not None
    if not is_org:
        raise HTTPException(status_code=403, detail="Only organizers can invite group members")

    # récupérer tous les membres du groupe
    member_ids = db.execute(
        select(group_members.c.user_id).where(group_members.c.group_id == event.group_id)
    ).scalars().all()

    if not member_ids:
        return

    # récupérer les participants déjà inscrits
    existing_ids = set(db.execute(
        select(event_participants.c.user_id).where(event_participants.c.event_id == event_id)
    ).scalars().all())

    to_add = [uid for uid in member_ids if uid not in existing_ids]
    if not to_add:
        return

    db.execute(
        event_participants.insert(),
        [{"event_id": event_id, "user_id": uid} for uid in to_add]
    )
    db.commit()
    return
