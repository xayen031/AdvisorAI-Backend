# app/main.py
import logging, os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import mic, speaker, combined
from app.routers.meeting import router as meeting
from app.routers.summary import router as summary
from app.routers import advisor_chat
from app.routers import extract_contact
from dotenv import load_dotenv

# Load .env at startup
load_dotenv()

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Real-Time Transcription API")

# ✅ CORS fix: Allow frontend (React/Vite) to talk to this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["20.247.40.175"],  # or ["*"] in dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Include routers AFTER middleware
app.include_router(mic)
app.include_router(speaker)
app.include_router(combined)
app.include_router(summary)
app.include_router(advisor_chat.router)
app.include_router(meeting)
app.include_router(extract_contact.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True
    )
