# app/db.py

import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

# Explicitly load .env from project root
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing Supabase credentials in environment")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def create_meeting(user_id: str, client_id: str, session_id: str, title: str = ""):
    record = {
        "user_id": user_id,
        "client_id": client_id,
        "session_id": session_id,
        "title": title,
        "started_at": datetime.utcnow().isoformat()
    }

    res = supabase.table("meetings").insert(record).execute()

    if res.data is None:
        raise RuntimeError("Supabase meeting insert failed: No data returned.")

async def save_summary(user_id: str, client_id: str, session_id: str, summary: str):
    """Insert a summary into the summaries table."""
    record = {
        "user_id": user_id,
        "client_id": client_id,
        "session_id": session_id,
        "summary": summary,
        "created_at": datetime.utcnow().isoformat()
    }
    res = supabase.table("summaries").insert(record).execute()
    if not res.data:
        raise RuntimeError("Supabase summary insert error")



async def save_transcript(
    user_id: str,
    client_id: str,
    session_id: str,
    source: str,
    speaker_tag: str,
    transcript: str
):
    """Insert a transcript record into Supabase, raising on error."""
    record = {
        "user_id": user_id,
        "client_id": client_id,
        "session_id": session_id,
        "source": source,
        "speaker_tag": speaker_tag,
        "transcript": transcript,
        "timestamp": datetime.utcnow().isoformat()
    }

    res = supabase.table("conversations").insert(record).execute()
    if not res.data:
        raise RuntimeError("Supabase transcript insert error")


async def save_openai_response(
    user_id: str,
    client_id: str,
    session_id: str,
    response_text: str
):
    """Insert an OpenAI response record into Supabase, raising on error."""
    record = {
        "user_id": user_id,
        "client_id": client_id,
        "session_id": session_id,
        "openai_response": response_text,
        "timestamp": datetime.utcnow().isoformat()
    }

    res = supabase.table("openai_responses").insert(record).execute()
    if not res.data:
        raise RuntimeError("Supabase OpenAI insert error")

