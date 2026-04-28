from app.routes.auth import router as auth_router 
from app.routes.interview import router as interview_router
from app.routes.interview import ws_router as interview_ws_router
from app.routes.resume import router as resume_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="IntervAI Backend API", version="1.0")

# Add CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing (restrict in production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(interview_router)
app.include_router(interview_ws_router)
app.include_router(resume_router)

@app.get("/")
async def root():
    return {"message": "Welcome to the IntervAI Backend API"}