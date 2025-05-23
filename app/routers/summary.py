# app/routers/summary.py
import logging, os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from openai import AsyncOpenAI
from app.db import save_summary
from app.deps import get_user_session

router = APIRouter()
logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class Message(BaseModel):
    speaker: str
    text: str

class SummaryRequest(BaseModel):
    messages: List[Message]

@router.post("/summarize")
async def summarize_conversation(
    payload: SummaryRequest,
    session_info=Depends(get_user_session)
):
    # Compose conversation as plain text
    text = "\n".join([f"{m.speaker}: {m.text}" for m in payload.messages])

    prompt = f"Summarize the following conversation in a concise and professional tone:\n\n{text}"

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a professional summarizer for business meetings."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=512,
            temperature=0.5
        )
        summary = response.choices[0].message.content.strip()

        await save_summary(
            user_id=session_info["user_id"],
            client_id=session_info["client_id"],
            session_id=session_info["session_id"],
            summary=summary
        )

        return {"summary": summary}

    except Exception as e:
        logger.error(f"Failed to summarize conversation: {e}")
        raise HTTPException(status_code=500, detail="Summarization failed.")
