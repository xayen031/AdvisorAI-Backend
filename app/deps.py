# app/deps.py
from fastapi import Query, Depends
from typing import Dict

async def get_user_session(
    userId: str = Query(..., alias="userId"),
    clientId: str = Query(..., alias="clientId"),
    sessionId: str = Query(..., alias="sessionId")
) -> Dict[str, str]:
    return {
        "user_id": userId,
        "client_id": clientId,
        "session_id": sessionId
    }
