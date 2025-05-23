# app/routers/advisor_chat.py

import uuid, logging, os
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List
from openai import AsyncOpenAI
from app.db import supabase
from gotrue.types import UserResponse

router = APIRouter()
logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are a UK financial advisor assistant. Respond concisely, professionally, and in British English. Avoid unnecessary detail.
"""

async def get_user_id(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.removeprefix("Bearer ").strip()

    try:
        auth_resp: UserResponse = supabase.auth.get_user(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Failed to validate token: {e}")

    if not auth_resp or not auth_resp.user:
        raise HTTPException(status_code=401, detail="User not found or token invalid")

    return auth_resp.user.id

class CreateChatRequest(BaseModel):
    title: str = ""

class ChatSession(BaseModel):
    id: str
    title: str
    created_at: str

class Message(BaseModel):
    role: str
    content: str
    timestamp: str

class UserMessage(BaseModel):
    prompt: str
    contact: dict | None = None

@router.post("/advisor-chats", response_model=ChatSession)
async def create_chat(payload: CreateChatRequest, user_id: str = Depends(get_user_id)):
    chat_id = str(uuid.uuid4())
    res = supabase.table("advisor_chats").insert({
        "id": chat_id,
        "user_id": user_id,
        "title": payload.title,
    }).execute()

    if not res.data:
        raise HTTPException(status_code=500, detail="Chat creation failed")

    return res.data[0]

@router.get("/advisor-chats", response_model=List[ChatSession])
async def list_chats(user_id: str = Depends(get_user_id)):
    res = supabase.table("advisor_chats") \
        .select("*") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .execute()
    if res.data is None:
        raise HTTPException(status_code=500, detail="Failed to load chats")
    return res.data

@router.get("/advisor-chats/{chat_id}", response_model=List[Message])
async def get_chat_messages(chat_id: str, user_id: str = Depends(get_user_id)):
    res = supabase.table("advisor_messages") \
        .select("*") \
        .eq("chat_id", chat_id) \
        .order("timestamp") \
        .execute()

    if res.data is None:
        raise HTTPException(status_code=500, detail="Failed to load messages")

    return res.data  # May return []

@router.post("/advisor-chats/{chat_id}", response_model=Message)
async def send_message(chat_id: str, payload: UserMessage, user_id: str = Depends(get_user_id)):
    # ✅ 1. prompt'ı her zamanki gibi mesaj olarak kaydet
    supabase.table("advisor_messages").insert({
        "chat_id": chat_id,
        "role": "user",
        "content": payload.prompt,
    }).execute()

    # ✅ 2. contact varsa, ikinci bir mesaj olarak JSON dump ile kaydet
    if payload.contact:
        import json
        supabase.table("advisor_messages").insert({
            "chat_id": chat_id,
            "role": "user",
            "content": f"[Contact Attached]\n{json.dumps(payload.contact, indent=2)}",
        }).execute()

    # ✅ 3. tüm geçmişi çek
    hist = supabase.table("advisor_messages") \
        .select("role, content") \
        .eq("chat_id", chat_id) \
        .order("timestamp") \
        .execute()

    if hist.data is None:
        raise HTTPException(status_code=500, detail="Failed to fetch chat history")

    # ✅ 4. sistem prompt + geçmiş + yeni mesaj
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + hist.data

    try:
        comp = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=msgs,
            max_tokens=800,
            temperature=0.6
        )
        reply = comp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        raise HTTPException(status_code=500, detail="LLM generation failed")

    sv = supabase.table("advisor_messages").insert({
        "chat_id": chat_id,
        "role": "assistant",
        "content": reply,
    }).execute()

    if not sv.data:
        raise HTTPException(status_code=500, detail="Could not save assistant message")

    # ✅ 5. ilk mesajsa başlık ata
    existing_msgs = [m for m in hist.data if m["role"] == "user"]
    assistant_msgs = [m for m in hist.data if m["role"] == "assistant"]

    if len(existing_msgs) == 1 and len(assistant_msgs) == 0:
        supabase.table("advisor_chats").update({
            "title": payload.prompt[:50]
        }).eq("id", chat_id).execute()

    return {
        "role": "assistant",
        "content": reply,
        "timestamp": sv.data[0]["timestamp"]
    }


@router.delete("/advisor-chats/{chat_id}")
async def delete_chat(chat_id: str, user_id: str = Depends(get_user_id)):
    supabase.table("advisor_messages").delete().eq("chat_id", chat_id).execute()
    res = supabase.table("advisor_chats").delete().eq("id", chat_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to delete chat")
    return {"success": True}
