# app/processors/transcript_manager.py

import json
import logging
from datetime import datetime
from typing import Dict
from fastapi import WebSocket
from .audio_processor import AudioProcessor
from app.db import save_transcript

logger = logging.getLogger(__name__)

class TranscriptManager:
    def __init__(self, source_name: str):
        self.source_name = source_name
        self.sentence_endings = {'.', '?', '!'}

    async def process_google_response(
        self,
        response,
        websocket: WebSocket,
        session_info: Dict[str, str]
    ):
        """Parse Google response, persist safely, forward to client, return segments."""
        segments = []
        for result in response.results:
            if not result.is_final or not result.alternatives:
                continue

            text = result.alternatives[0].transcript.strip()
            if not text:
                continue

            text = text[0].upper() + text[1:]
            if text[-1] not in self.sentence_endings:
                text += '.'

            speaker_tag = (
                result.alternatives[0].words[0].speaker_tag
                if result.alternatives[0].words else 1
            )

            # --- Safe persistence ---
            try:
                resp = await save_transcript(
                    user_id=session_info["user_id"],
                    client_id=session_info["client_id"],
                    session_id=session_info["session_id"],
                    source=self.source_name,
                    speaker_tag=f"Speaker_{speaker_tag}",
                    transcript=text
                )
                if getattr(resp, "error", None):
                    logger.error(f"Supabase insert error: {resp.error}")
            except Exception as e:
                logger.error(f"Failed to save transcript: {e}")

            # Forward to client
            try:
                await websocket.send_text(json.dumps({
                    "type": f"{self.source_name}_transcription",
                    "content": text,
                    "timestamp": datetime.utcnow().isoformat()
                }))
            except Exception as e:
                logger.error(f"Failed to send transcription: {e}")

            segments.append({
                "role": self.source_name,
                "speaker": speaker_tag,
                "content": text,
                "timestamp": datetime.utcnow().isoformat()
            })

        return segments
