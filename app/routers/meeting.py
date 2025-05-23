# app/routers/meeting.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.deps import get_user_session
from app.db import create_meeting
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class MeetingCreatePayload(BaseModel):
    title: str = ""

@router.post("/meetings/start")
async def start_meeting(
    payload: MeetingCreatePayload,
    session_info=Depends(get_user_session)
):
    try:
        await create_meeting(
            user_id=session_info["user_id"],
            client_id=session_info["client_id"],
            session_id=session_info["session_id"],
            title=payload.title
        )
        return {"status": "success", "message": "Meeting started."}
    except Exception as e:
        logger.error(f"Error creating meeting: {e}")
        raise HTTPException(status_code=500, detail="Could not create meeting.")
