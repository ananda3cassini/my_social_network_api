from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from .db import get_db
from .models import Group, User
from .schemas import GroupCreate, GroupPublic, GroupUpdate, UserPublic
from .security import get_current_user

router = APIRouter(prefix="/groups", tags=["groups"])


def require_group_admin(group: Group, user: User):
    if user not in group.admins:
        raise HTTPException(status_code=403, detail="Admin permissions required")


@router.post("", response_model=GroupPublic, status_code=201)
def create_group(
    payload: GroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group = Group(**payload.model_dump())
    # créateur = admin + membre
    group.members.append(current_user)
    group.admins.append(current_user)

    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.get("", response_model=list[GroupPublic])
def list_groups(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)

    groups = db.execute(select(Group).offset(offset).limit(limit)).scalars().all()
    return groups


@router.get("/{group_id}", response_model=GroupPublic)
def get_group(group_id: int, db: Session = Depends(get_db)):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


@router.patch("/{group_id}", response_model=GroupPublic)
def update_group(
    group_id: int,
    payload: GroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    require_group_admin(group, current_user)

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(group, k, v)

    db.commit()
    db.refresh(group)
    return group


# ----- Collections : members -----
@router.get("/{group_id}/members", response_model=list[UserPublic])
def list_members(group_id: int, db: Session = Depends(get_db)):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group.members


@router.post("/{group_id}/members/{user_id}", status_code=204)
def add_member(
    group_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    require_group_admin(group, current_user)

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user not in group.members:
        group.members.append(user)
        db.commit()
    return


@router.delete("/{group_id}/members/{user_id}", status_code=204)
def remove_member(
    group_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    require_group_admin(group, current_user)

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user in group.members:
        group.members.remove(user)

    # si on retire un membre qui est admin, on le retire aussi des admins
    if user in group.admins:
        group.admins.remove(user)

    db.commit()
    return


# ----- Collections : admins -----
@router.get("/{group_id}/admins", response_model=list[UserPublic])
def list_admins(group_id: int, db: Session = Depends(get_db)):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group.admins


@router.post("/{group_id}/admins/{user_id}", status_code=204)
def add_admin(
    group_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    require_group_admin(group, current_user)

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user not in group.members:
        raise HTTPException(status_code=400, detail="User must be a member before becoming admin")

    if user not in group.admins:
        group.admins.append(user)
        db.commit()
    return


@router.delete("/{group_id}/admins/{user_id}", status_code=204)
def remove_admin(
    group_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    require_group_admin(group, current_user)

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user in group.admins:
        # évite de laisser un groupe sans admin
        if len(group.admins) == 1:
            raise HTTPException(status_code=400, detail="Group must have at least one admin")
        group.admins.remove(user)
        db.commit()

    return
