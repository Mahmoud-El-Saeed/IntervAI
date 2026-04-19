from app.routes.auth import router as auth_router 
from app.routes.interview import router as interview_router
from app.routes.resume import router as resume_router
from fastapi import FastAPI

app = FastAPI(title="IntervAI Backend API", version="1.0")
app.include_router(auth_router)
app.include_router(interview_router)
app.include_router(resume_router)

@app.get("/")
async def root():
    return {"message": "Welcome to the IntervAI Backend API"}