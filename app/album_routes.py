from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from .db import get_db
from .security import get_current_user, get_current_user_optional
from .models import (
    User, Event, PhotoAlbum, Photo, PhotoComment,
    event_participants, event_organizers,
)
from .schemas import (
    AlbumCreate, AlbumPublic,
    PhotoCreate, PhotoPublic,
    PhotoCommentCreate, PhotoCommentPublic,
)

router = APIRouter(prefix="/albums", tags=["albums"])


# ---------- Helpers (droits d'accès event) ----------
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


def _can_view_event(db: Session, event: Event, current_user: User | None) -> bool:
    # event public -> visible à tous
    if event.is_public:
        return True
    # event privé -> seulement membres
    if current_user is None:
        return False
    return _is_event_member(db, event.id, current_user.id)


# ---------- Albums ----------
@router.post("", response_model=AlbumPublic, status_code=201)
def create_album(
    payload: AlbumCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.execute(select(Event).where(Event.id == payload.event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # seuls participants / organizers peuvent créer un album
    if not _is_event_member(db, payload.event_id, current_user.id):
        raise HTTPException(status_code=403, detail="Only event participants/organizers can create an album")

    album = PhotoAlbum(
        event_id=payload.event_id,
        title=payload.title,
        description=payload.description,
    )
    db.add(album)
    db.commit()
    db.refresh(album)
    return album


@router.get("/{album_id}", response_model=AlbumPublic)
def get_album(
    album_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    album = db.execute(select(PhotoAlbum).where(PhotoAlbum.id == album_id)).scalar_one_or_none()
    if album is None:
        raise HTTPException(status_code=404, detail="Album not found")

    event = db.execute(select(Event).where(Event.id == album.event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if not _can_view_event(db, event, current_user):
        raise HTTPException(status_code=403, detail="Not allowed to view this album")

    return album


@router.get("/by-event/{event_id}", response_model=list[AlbumPublic])
def list_albums_by_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
    limit: int = 50,
    offset: int = 0,
):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")

    event = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if not _can_view_event(db, event, current_user):
        raise HTTPException(status_code=403, detail="Not allowed to view albums for this event")

    albums = db.execute(
        select(PhotoAlbum)
        .where(PhotoAlbum.event_id == event_id)
        .order_by(PhotoAlbum.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()

    return albums


# ---------- Photos ----------
@router.post("/{album_id}/photos", response_model=PhotoPublic, status_code=201)
def add_photo(
    album_id: int,
    payload: PhotoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    album = db.execute(select(PhotoAlbum).where(PhotoAlbum.id == album_id)).scalar_one_or_none()
    if album is None:
        raise HTTPException(status_code=404, detail="Album not found")

    # retrouver l'event via l'album
    event = db.execute(select(Event).where(Event.id == album.event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # seuls participants/organizers peuvent poster des photos
    if not _is_event_member(db, event.id, current_user.id):
        raise HTTPException(status_code=403, detail="Only event participants/organizers can post photos")

    photo = Photo(
        album_id=album_id,
        uploader_id=current_user.id,
        url=str(payload.url),
        caption=payload.caption,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


@router.get("/{album_id}/photos", response_model=list[PhotoPublic])
def list_photos(
    album_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
    limit: int = 50,
    offset: int = 0,
):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")

    album = db.execute(select(PhotoAlbum).where(PhotoAlbum.id == album_id)).scalar_one_or_none()
    if album is None:
        raise HTTPException(status_code=404, detail="Album not found")

    event = db.execute(select(Event).where(Event.id == album.event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if not _can_view_event(db, event, current_user):
        raise HTTPException(status_code=403, detail="Not allowed to view photos for this album")

    photos = db.execute(
        select(Photo)
        .where(Photo.album_id == album_id)
        .order_by(Photo.created_at.asc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()

    return photos


# ---------- Comments ----------
@router.post("/photos/{photo_id}/comments", response_model=PhotoCommentPublic, status_code=201)
def add_comment(
    photo_id: int,
    payload: PhotoCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    photo = db.execute(select(Photo).where(Photo.id == photo_id)).scalar_one_or_none()
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    album = db.execute(select(PhotoAlbum).where(PhotoAlbum.id == photo.album_id)).scalar_one_or_none()
    if album is None:
        raise HTTPException(status_code=404, detail="Album not found")

    event = db.execute(select(Event).where(Event.id == album.event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # seuls participants/organizers peuvent commenter
    if not _is_event_member(db, event.id, current_user.id):
        raise HTTPException(status_code=403, detail="Only event participants/organizers can comment photos")

    comment = PhotoComment(
        photo_id=photo_id,
        author_id=current_user.id,
        content=payload.content,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.get("/photos/{photo_id}/comments", response_model=list[PhotoCommentPublic])
def list_comments(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
    limit: int = 50,
    offset: int = 0,
):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")

    photo = db.execute(select(Photo).where(Photo.id == photo_id)).scalar_one_or_none()
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    album = db.execute(select(PhotoAlbum).where(PhotoAlbum.id == photo.album_id)).scalar_one_or_none()
    if album is None:
        raise HTTPException(status_code=404, detail="Album not found")

    event = db.execute(select(Event).where(Event.id == album.event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if not _can_view_event(db, event, current_user):
        raise HTTPException(status_code=403, detail="Not allowed to view comments for this photo")

    comments = db.execute(
        select(PhotoComment)
        .where(PhotoComment.photo_id == photo_id)
        .order_by(PhotoComment.created_at.asc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()

    return comments
