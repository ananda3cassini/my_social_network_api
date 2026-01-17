from fastapi import FastAPI
from app.db import Base, engine
from app.auth_routes import router as auth_router

app = FastAPI(title="My Social Networks API")

# Crée les tables au démarrage 
Base.metadata.create_all(bind=engine)

app.include_router(auth_router)

@app.get("/")
def root():
    return {"message": "My Social Networks API is running"}

@app.get("/health")
def health():
    return {"status": "ok"}
