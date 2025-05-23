import sys
import os

# Add project root to path so `import app` works
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest
import pytest_asyncio
import asyncio
import json
import websockets
import soundfile as sf
import numpy as np
from dotenv import load_dotenv

# Stub out Supabase persistence so it can't block transcription
import app.db
app.db.save_transcript = lambda *args, **kwargs: None
app.db.save_openai_response = lambda *args, **kwargs: None

load_dotenv()

WS_URL = "ws://127.0.0.1:8000"

@pytest_asyncio.fixture(autouse=True)
def _event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.mark.asyncio
async def test_mic_and_speaker_text_flow():
    uri = f"{WS_URL}/mic_and_speaker?userId=u&clientId=c&sessionId=s"
    async with websockets.connect(uri) as ws:
        payload = {"type": "text_input", "content": "Hello world"}
        await ws.send(json.dumps(payload))

        msg1 = await asyncio.wait_for(ws.recv(), timeout=5)
        data1 = json.loads(msg1)
        assert data1["type"] == "openai_assistant_delta"

        msg2 = await asyncio.wait_for(ws.recv(), timeout=5)
        data2 = json.loads(msg2)
        assert data2["type"] == "openai_assistant_completed"

@pytest.mark.asyncio
async def test_mic_real_audio_flow():
    uri = f"{WS_URL}/mic?userId=u&clientId=c&sessionId=s"
    wav_path = os.path.join(os.path.dirname(__file__), "fixtures", "test.wav")
    data, samplerate = sf.read(wav_path, dtype='int16')

    # Resample to 16kHz if necessary
    target_rate = 16000
    if samplerate != target_rate:
        duration = data.shape[0] / samplerate
        num_samples = int(duration * target_rate)
        data = np.interp(
            np.linspace(0, len(data), num=num_samples, endpoint=False),
            np.arange(len(data)),
            data
        ).astype('int16')

    raw_bytes = data.tobytes()

    async with websockets.connect(uri) as ws:
        received = []

        async def reader():
            try:
                while True:
                    msg = await ws.recv()
                    payload = json.loads(msg)
                    if payload.get("type", "").endswith("_transcription"):
                        received.append(payload["content"])
                        break
            except:
                pass

        read_task = asyncio.create_task(reader())

        chunk_size = target_rate * 2 // 10
        for i in range(0, len(raw_bytes), chunk_size):
            await ws.send(raw_bytes[i:i+chunk_size])
            await asyncio.sleep(0.05)

        await ws.close()
        await asyncio.wait_for(read_task, timeout=10)

        assert received, "No transcription received from /mic with real audio"
