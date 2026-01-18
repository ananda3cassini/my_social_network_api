from fastapi import FastAPI
from app.db import Base, engine
from app import models  
from app.auth_routes import router as auth_router

app = FastAPI(title="My Social Networks API")

Base.metadata.create_all(bind=engine)

app.include_router(auth_router)

@app.get("/")
def root():
    return {"message": "My Social Networks API is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

from app.group_routes import router as group_router
app.include_router(group_router)

from app.event_routes import router as event_router
app.include_router(event_router)

from app.discussion_routes import router as discussion_router
app.include_router(discussion_router)

from app.album_routes import router as album_router
app.include_router(album_router)

from app.poll_routes import router as poll_router
app.include_router(poll_router)

from app.ticket_routes import router as ticket_router
app.include_router(ticket_router)

from app.shopping_routes import router as shopping_router
app.include_router(shopping_router)
