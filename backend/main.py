from app.routes.auth import router as auth_router
from fastapi import FastAPI

app = FastAPI(title="IntervAI Backend API", version="1.0")
app.include_router(auth_router)

@app.get("/")
async def root():
    return {"message": "Welcome to the IntervAI Backend API"}