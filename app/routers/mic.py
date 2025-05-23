# app/routers/mic.py
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.deps import get_user_session
from app.processors.audio_processor import AudioProcessor
from app.processors.transcript_manager import TranscriptManager

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/mic")
async def mic_endpoint(
    websocket: WebSocket,
    session_info=Depends(get_user_session)
):
    await websocket.accept()
    loop = asyncio.get_running_loop()
    proc = AudioProcessor("mic")
    proc.start(loop)
    tm = TranscriptManager("mic")

    async def reader():
        while True:
            resp = await proc.response_queue.get()
            await tm.process_google_response(resp, websocket, session_info)

    task = asyncio.create_task(reader())
    try:
        while True:
            data = await websocket.receive_bytes()
            proc.add_audio(data)
    except WebSocketDisconnect:
        logger.info("Mic disconnected.")
    finally:
        proc.stop()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
