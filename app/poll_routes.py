from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from .db import get_db
from .security import get_current_user, get_current_user_optional
from .models import (
    User, Event,
    Poll, PollQuestion, PollOption, PollVote,
    event_participants, event_organizers,
)
from .schemas import PollCreate, PollPublic, PollVoteCreate

router = APIRouter(prefix="/polls", tags=["polls"])


# ---------- Helpers ----------
def _is_event_member(db: Session, event_id: int, user_id: int) -> bool:
    is_participant = db.execute(
        select(event_participants.c.user_id).where(
            event_participants.c.event_id == event_id,
            event_participants.c.user_id == user_id,
        )
    ).first() is not None

    is_organizer = db.execute(
        select(event_organizers.c.user_id).where(
            event_organizers.c.event_id == event_id,
            event_organizers.c.user_id == user_id,
        )
    ).first() is not None

    return is_participant or is_organizer


def _is_event_organizer(db: Session, event_id: int, user_id: int) -> bool:
    return db.execute(
        select(event_organizers.c.user_id).where(
            event_organizers.c.event_id == event_id,
            event_organizers.c.user_id == user_id,
        )
    ).first() is not None


def _can_view_event(db: Session, event: Event, current_user: User | None) -> bool:
    if event.is_public:
        return True
    if current_user is None:
        return False
    return _is_event_member(db, event.id, current_user.id)


# ---------- Routes ----------
@router.post("", response_model=PollPublic, status_code=201)
def create_poll(
    payload: PollCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.execute(select(Event).where(Event.id == payload.event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # Seul un organizer peut créer un sondage
    if not _is_event_organizer(db, payload.event_id, current_user.id):
        raise HTTPException(status_code=403, detail="Only organizers can create polls")

    poll = Poll(
        event_id=payload.event_id,
        creator_id=current_user.id,
        title=payload.title,
    )
    db.add(poll)
    db.commit()
    db.refresh(poll)

    # Créer questions + options
    for q in payload.questions:
        question = PollQuestion(poll_id=poll.id, question=q.question)
        db.add(question)
        db.commit()
        db.refresh(question)

        for opt in q.options:
            option = PollOption(question_id=question.id, label=opt.label)
            db.add(option)

        db.commit()

    db.refresh(poll)
    return poll


@router.get("/by-event/{event_id}", response_model=list[PollPublic])
def list_polls_by_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if not _can_view_event(db, event, current_user):
        raise HTTPException(status_code=403, detail="Not allowed to view polls for this event")

    polls = db.execute(
        select(Poll).where(Poll.event_id == event_id).order_by(Poll.created_at.desc())
    ).scalars().all()

    return polls


@router.get("/{poll_id}", response_model=PollPublic)
def get_poll(
    poll_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    poll = db.execute(select(Poll).where(Poll.id == poll_id)).scalar_one_or_none()
    if poll is None:
        raise HTTPException(status_code=404, detail="Poll not found")

    event = db.execute(select(Event).where(Event.id == poll.event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if not _can_view_event(db, event, current_user):
        raise HTTPException(status_code=403, detail="Not allowed to view this poll")

    return poll


@router.post("/questions/{question_id}/vote", status_code=204)
def vote_question(
    question_id: int,
    payload: PollVoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = db.execute(select(PollQuestion).where(PollQuestion.id == question_id)).scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    poll = db.execute(select(Poll).where(Poll.id == question.poll_id)).scalar_one_or_none()
    if poll is None:
        raise HTTPException(status_code=404, detail="Poll not found")

    event = db.execute(select(Event).where(Event.id == poll.event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # seuls participants/organizers peuvent voter
    if not _is_event_member(db, event.id, current_user.id):
        raise HTTPException(status_code=403, detail="Only event participants/organizers can vote")

    # option doit appartenir à cette question
    option = db.execute(
        select(PollOption).where(
            PollOption.id == payload.option_id,
            PollOption.question_id == question_id,
        )
    ).scalar_one_or_none()
    if option is None:
        raise HTTPException(status_code=400, detail="Option does not belong to this question")

    vote = PollVote(
        question_id=question_id,
        option_id=payload.option_id,
        user_id=current_user.id,
    )
    db.add(vote)

    # UniqueConstraint(question_id,user_id) => empêche double vote
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="User already voted for this question")

    return


@router.get("/{poll_id}/results")
def poll_results(
    poll_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    poll = db.execute(select(Poll).where(Poll.id == poll_id)).scalar_one_or_none()
    if poll is None:
        raise HTTPException(status_code=404, detail="Poll not found")

    event = db.execute(select(Event).where(Event.id == poll.event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if not _can_view_event(db, event, current_user):
        raise HTTPException(status_code=403, detail="Not allowed to view results")

    # Résultats: nb de votes par option, regroupés par question
    questions = db.execute(select(PollQuestion).where(PollQuestion.poll_id == poll_id)).scalars().all()

    results = []
    for q in questions:
        options = db.execute(select(PollOption).where(PollOption.question_id == q.id)).scalars().all()

        option_counts = db.execute(
            select(PollVote.option_id, func.count(PollVote.id))
            .where(PollVote.question_id == q.id)
            .group_by(PollVote.option_id)
        ).all()
        counts_map = {opt_id: count for opt_id, count in option_counts}

        results.append({
            "question_id": q.id,
            "question": q.question,
            "options": [
                {"option_id": o.id, "label": o.label, "votes": counts_map.get(o.id, 0)}
                for o in options
            ],
        })

    return {
        "poll_id": poll.id,
        "title": poll.title,
        "results": results,
    }
