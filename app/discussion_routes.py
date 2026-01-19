from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from .db import get_db
from .models import Discussion, Message, Group, Event, User, group_members, event_participants, event_organizers
from .schemas import DiscussionCreate, DiscussionPublic, MessageCreate, MessagePublic
from .security import get_current_user

router = APIRouter(prefix="/discussions", tags=["discussions"])


# ---------- Helpers (droits d'accès) ----------
def _can_access_discussion(db: Session, discussion: Discussion, user: User) -> bool:
    """
    Règles d'accès:
    - Discussion liée à un groupe: user doit être membre du groupe
    - Discussion liée à un event: user doit être participant ou organisateur de l'event
    """
    if discussion.group_id is not None:
        is_member = db.execute(
            select(group_members.c.user_id).where(
                group_members.c.group_id == discussion.group_id,
                group_members.c.user_id == user.id,
            )
        ).first() is not None
        return is_member

    if discussion.event_id is not None:
        is_participant = db.execute(
            select(event_participants.c.user_id).where(
                event_participants.c.event_id == discussion.event_id,
                event_participants.c.user_id == user.id,
            )
        ).first() is not None

        is_organizer = db.execute(
            select(event_organizers.c.user_id).where(
                event_organizers.c.event_id == discussion.event_id,
                event_organizers.c.user_id == user.id,
            )
        ).first() is not None

        return is_participant or is_organizer

    return False


# ---------- Discussions ----------
@router.post("", response_model=DiscussionPublic, status_code=201)
def create_discussion(
    payload: DiscussionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Vérifier que le groupe/event existe
    if payload.group_id is not None:
        group = db.execute(select(Group).where(Group.id == payload.group_id)).scalar_one_or_none()
        if group is None:
            raise HTTPException(status_code=404, detail="Group not found")

        # l'utilisateur doit être membre du groupe pour créer la discussion
        is_member = db.execute(
            select(group_members.c.user_id).where(
                group_members.c.group_id == payload.group_id,
                group_members.c.user_id == current_user.id,
            )
        ).first() is not None
        if not is_member:
            raise HTTPException(status_code=403, detail="Only group members can create the discussion")

    if payload.event_id is not None:
        event = db.execute(select(Event).where(Event.id == payload.event_id)).scalar_one_or_none()
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")

        # l'utilisateur doit être participant ou organisateur
        is_participant = db.execute(
            select(event_participants.c.user_id).where(
                event_participants.c.event_id == payload.event_id,
                event_participants.c.user_id == current_user.id,
            )
        ).first() is not None

        is_organizer = db.execute(
            select(event_organizers.c.user_id).where(
                event_organizers.c.event_id == payload.event_id,
                event_organizers.c.user_id == current_user.id,
            )
        ).first() is not None

        if not (is_participant or is_organizer):
            raise HTTPException(status_code=403, detail="Only event participants/organizers can create the discussion")

    # Option produit : 1 discussion par groupe / event (évite doublons)
    existing = None
    if payload.group_id is not None:
        existing = db.execute(
            select(Discussion).where(Discussion.group_id == payload.group_id)
        ).scalar_one_or_none()
    if payload.event_id is not None:
        existing = db.execute(
            select(Discussion).where(Discussion.event_id == payload.event_id)
        ).scalar_one_or_none()

    if existing:
        return existing

    discussion = Discussion(group_id=payload.group_id, event_id=payload.event_id)
    db.add(discussion)
    db.commit()
    db.refresh(discussion)
    return discussion


@router.get("/{discussion_id}", response_model=DiscussionPublic)
def get_discussion(
    discussion_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    discussion = db.execute(select(Discussion).where(Discussion.id == discussion_id)).scalar_one_or_none()
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if not _can_access_discussion(db, discussion, current_user):
        raise HTTPException(status_code=403, detail="Not allowed to access this discussion")

    return discussion


# ---------- Messages ----------
@router.post("/{discussion_id}/messages", response_model=MessagePublic, status_code=201)
def post_message(
    discussion_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    discussion = db.execute(
        select(Discussion).where(Discussion.id == discussion_id)
    ).scalar_one_or_none()
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if not _can_access_discussion(db, discussion, current_user):
        raise HTTPException(status_code=403, detail="Not allowed to post in this discussion")

    parent_id = payload.parent_message_id

    # Si c'est une réponse, vérifier que le parent existe et appartient à la même discussion
    if parent_id is not None:
        parent_msg = db.execute(
            select(Message).where(Message.id == parent_id)
        ).scalar_one_or_none()
        if parent_msg is None:
            raise HTTPException(status_code=404, detail="Parent message not found")

        if parent_msg.discussion_id != discussion_id:
            raise HTTPException(
                status_code=400,
                detail="Parent message must belong to the same discussion",
            )

    msg = Message(
        discussion_id=discussion_id,
        author_id=current_user.id,
        content=payload.content,
        parent_message_id=parent_id,  # NEW
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg



@router.get("/{discussion_id}/messages", response_model=list[MessagePublic])
def list_messages(
    discussion_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")

    discussion = db.execute(select(Discussion).where(Discussion.id == discussion_id)).scalar_one_or_none()
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if not _can_access_discussion(db, discussion, current_user):
        raise HTTPException(status_code=403, detail="Not allowed to read messages in this discussion")

    messages = db.execute(
        select(Message)
        .where(Message.discussion_id == discussion_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()

    return messages

# Discussion d'un groupe
@router.get("/by-group/{group_id}", response_model=DiscussionPublic)
def get_discussion_by_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group = db.execute(select(Group).where(Group.id == group_id)).scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")

    # accès: membre du groupe
    is_member = db.execute(
        select(group_members.c.user_id).where(
            group_members.c.group_id == group_id,
            group_members.c.user_id == current_user.id,
        )
    ).first() is not None
    if not is_member:
        raise HTTPException(status_code=403, detail="Not allowed to access this group discussion")

    discussion = db.execute(select(Discussion).where(Discussion.group_id == group_id)).scalar_one_or_none()
    if discussion is None:
        # Option produit: on crée automatiquement si absent
        discussion = Discussion(group_id=group_id)
        db.add(discussion)
        db.commit()
        db.refresh(discussion)

    return discussion


# Discussion d'un évnénement
@router.get("/by-event/{event_id}", response_model=DiscussionPublic)
def get_discussion_by_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # accès: participant OU organizer (comme d'hab)
    is_participant = db.execute(
        select(event_participants.c.user_id).where(
            event_participants.c.event_id == event_id,
            event_participants.c.user_id == current_user.id,
        )
    ).first() is not None

    is_organizer = db.execute(
        select(event_organizers.c.user_id).where(
            event_organizers.c.event_id == event_id,
            event_organizers.c.user_id == current_user.id,
        )
    ).first() is not None

    if not (is_participant or is_organizer):
        raise HTTPException(status_code=403, detail="Not allowed to access this event discussion")

    discussion = db.execute(select(Discussion).where(Discussion.event_id == event_id)).scalar_one_or_none()
    if discussion is None:
        discussion = Discussion(event_id=event_id)
        db.add(discussion)
        db.commit()
        db.refresh(discussion)

    return discussion


# Supression message
@router.delete("/{discussion_id}/messages/{message_id}", status_code=204)
def delete_message(
    discussion_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # discussion existe ?
    discussion = db.execute(select(Discussion).where(Discussion.id == discussion_id)).scalar_one_or_none()
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    # accès au fil
    if not _can_access_discussion(db, discussion, current_user):
        raise HTTPException(status_code=403, detail="Not allowed to access this discussion")

    # message existe et appartient à cette discussion ?
    msg = db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.discussion_id == discussion_id,
        )
    ).scalar_one_or_none()
    if msg is None:
        raise HTTPException(status_code=404, detail="Message not found")

    # 1) auteur => ok
    if msg.author_id == current_user.id:
        db.delete(msg)
        db.commit()
        return

    # 2) si discussion liée à un event => organizer peut supprimer
    if discussion.event_id is not None:
        is_organizer = db.execute(
            select(event_organizers.c.user_id).where(
                event_organizers.c.event_id == discussion.event_id,
                event_organizers.c.user_id == current_user.id,
            )
        ).first() is not None
        if is_organizer:
            db.delete(msg)
            db.commit()
            return

    # 3) si discussion liée à un groupe => admin peut supprimer
    if discussion.group_id is not None:
        # IMPORTANT: adapte le nom si ta table s'appelle différemment (ex: group_admins)
        from .models import group_admins  # import local pour éviter erreurs si non utilisé ailleurs

        is_admin = db.execute(
            select(group_admins.c.user_id).where(
                group_admins.c.group_id == discussion.group_id,
                group_admins.c.user_id == current_user.id,
            )
        ).first() is not None
        if is_admin:
            db.delete(msg)
            db.commit()
            return

    raise HTTPException(status_code=403, detail="Not allowed to delete this message")


# lister les replies
@router.get("/{discussion_id}/messages/{message_id}/replies", response_model=list[MessagePublic])
def list_replies(
    discussion_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    discussion = db.execute(select(Discussion).where(Discussion.id == discussion_id)).scalar_one_or_none()
    if discussion is None:
        raise HTTPException(status_code=404, detail="Discussion not found")

    if not _can_access_discussion(db, discussion, current_user):
        raise HTTPException(status_code=403, detail="Not allowed")

    parent = db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.discussion_id == discussion_id,
        )
    ).scalar_one_or_none()
    if parent is None:
        raise HTTPException(status_code=404, detail="Message not found")

    replies = db.execute(
        select(Message)
        .where(
            Message.discussion_id == discussion_id,
            Message.parent_message_id == message_id,
        )
        .order_by(Message.created_at.asc())
    ).scalars().all()

    return replies
